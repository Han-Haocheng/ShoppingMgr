"""开发入口：python run.py 或 flask --app run:app run。"""

from __future__ import annotations

import os

from app import create_app
from app.config import debug_enabled_by_env

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        # 只有 FLASK_DEBUG 取 1/true/yes 才开启调试；未设置或其它取值为关闭
        debug=debug_enabled_by_env(),
    )
