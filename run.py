"""开发入口：python run.py 或 flask --app run:app run。"""

from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv

# 必须在导入 app 之前加载 .env：Config 的 SECRET_KEY / DATABASE_URL 等都是 import 期读环境变量，
# 晚一步就白配。find_dotenv(usecwd=True) = 从当前工作目录向上找 .env（在项目根目录运行即命中
# 项目根的 .env）；不用 override=True，已有环境变量与 shell export 优先，避免污染 CI。
load_dotenv(find_dotenv(usecwd=True))

from app import create_app  # noqa: E402  必须放在 load_dotenv() 之后
from app.config import debug_enabled_by_env  # noqa: E402

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        # 只有 FLASK_DEBUG 取 1/true/yes 才开启调试；未设置或其它取值为关闭
        debug=debug_enabled_by_env(),
    )
