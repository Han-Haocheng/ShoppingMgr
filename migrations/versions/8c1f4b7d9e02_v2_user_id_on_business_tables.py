"""v2: 5 张业务表加 user_id（数据归属）

Revision ID: 8c1f4b7d9e02
Revises: 0554acb803f0
Create Date: 2026-11-25 19:05:00.000000

SPEC 第 10 节的「加 user_id 三步」，SQLite 一律走 op.batch_alter_table 重建表：
1. 加可空列（存量行还没值，先放开）；
2. 回填：全部归到 id 最小的用户；products.barcode 的空串一并归一为 NULL，
   否则 (user_id, barcode) 唯一约束会在第二行空条码上撞车；
3. 改 NOT NULL + 建 user_id 索引 + 换唯一约束（categories 改 (user_id, name)，
   products 加 (user_id, barcode) 并把 barcode 放开为可空）。

「users 表为空就报错」的前置检查放在所有 DDL 之前：失败时库还是 v1 原样，不留半成品。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c1f4b7d9e02'
down_revision = '0554acb803f0'
branch_labels = None
depends_on = None

BUSINESS_TABLES = (
    'categories',
    'products',
    'shopping_lists',
    'shopping_items',
    'expenses',
)

# v1 的 categories.name 全局唯一约束没起名字，SQLite 又没法按名字删无名约束；
# 靠 naming_convention 把反射出来的无名 UNIQUE / FK 命名成确定值，才能按名字 drop。
# fk 规则同时保证 downgrade 能删掉 upgrade 建的外键
# （SQLite 的 PRAGMA foreign_key_list 不返回约束名，只能靠约定推）。
NAMING_CONVENTION = {
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
}

INIT_ADMIN_HINT = (
    '回填 user_id 需要至少一个归属用户，但 users 表为空。'
    '请先运行 flask --app run:app init-admin --username X --password Y 建好账号，再执行迁移。'
)


def _owner_id():
    """取归属用户（id 最小的用户）；有数据要回填但 users 为空则直接失败。

    空库（5 张表都没有行）不需要归属用户，返回 None —— 否则全新库连
    flask db upgrade 都建不出来，与「空库 upgrade 应得到 head 全表」的既有用例冲突。
    """
    bind = op.get_bind()
    pending = sum(
        bind.execute(sa.text(f'SELECT COUNT(*) FROM {table}')).scalar() or 0
        for table in BUSINESS_TABLES
    )
    if pending == 0:
        return None
    owner = bind.execute(sa.text('SELECT MIN(id) FROM users')).scalar()
    if owner is None:
        raise RuntimeError(INIT_ADMIN_HINT)
    return int(owner)


def upgrade():
    # 前置检查：必须在任何 DDL 之前，保证失败不留半成品（SPEC 第 10 节）
    owner = _owner_id()

    # —— 第一步：加可空列（products.barcode 顺带放开为可空，否则第二步写不进 NULL）
    for table in BUSINESS_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
    with op.batch_alter_table('products') as batch:
        batch.alter_column('barcode', existing_type=sa.String(length=64), nullable=True)

    # —— 第二步：回填存量数据（owner 为 None 说明表本来就是空的，无数据可回填）
    if owner is not None:
        for table in BUSINESS_TABLES:
            op.execute(
                sa.text(f'UPDATE {table} SET user_id = :owner').bindparams(owner=owner)
            )
    op.execute(sa.text("UPDATE products SET barcode = NULL WHERE barcode = ''"))

    # —— 第三步：NOT NULL + 外键 + 唯一约束
    for table in BUSINESS_TABLES:
        with op.batch_alter_table(table, naming_convention=NAMING_CONVENTION) as batch:
            batch.alter_column('user_id', existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(
                f'fk_{table}_user_id_users', 'users', ['user_id'], ['id']
            )
            if table == 'categories':
                batch.drop_constraint('uq_categories_name', type_='unique')
                batch.create_unique_constraint(
                    'uq_categories_user_name', ['user_id', 'name']
                )
            elif table == 'products':
                batch.create_unique_constraint(
                    'uq_products_user_barcode', ['user_id', 'barcode']
                )

    for table in BUSINESS_TABLES:
        op.create_index(f'ix_{table}_user_id', table, ['user_id'])


def downgrade():
    for table in BUSINESS_TABLES:
        op.drop_index(f'ix_{table}_user_id', table_name=table)

    # 先拆 v2 才有的约束（外键 + 同用户唯一）并降掉 user_id，再恢复 v1 约定：
    # 顺序反了会在「同一用户多条空条码」这类 v2 合法数据上撞新唯一约束。
    for table in BUSINESS_TABLES:
        with op.batch_alter_table(table, naming_convention=NAMING_CONVENTION) as batch:
            batch.drop_constraint(f'fk_{table}_user_id_users', type_='foreignkey')
            if table == 'categories':
                batch.drop_constraint('uq_categories_user_name', type_='unique')
                # v1 的 UNIQUE(name) 本身没名字；batch 模式要求显式命名
                batch.create_unique_constraint('uq_categories_name', ['name'])
            elif table == 'products':
                batch.drop_constraint('uq_products_user_barcode', type_='unique')
            batch.drop_column('user_id')

    # 恢复 v1 的「barcode NOT NULL 且空值为空串」约定（此时唯一约束已拆掉，不会撞车）
    op.execute(sa.text("UPDATE products SET barcode = '' WHERE barcode IS NULL"))
    with op.batch_alter_table('products') as batch:
        batch.alter_column(
            'barcode', existing_type=sa.String(length=64), nullable=False
        )
