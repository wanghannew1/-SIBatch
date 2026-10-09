"""app.py — Flask 应用入口。

- 模块级暴露 `app`，可 `from app import app`
- 也提供工厂 `create_app()`
- `python app.py` 时启动开发服务器，监听 0.0.0.0:5000
"""

import logging
import os
import sys

from flask import Flask, render_template

import auth
import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def _import_packages():
    """容错导入 parser / generator 包（骨架阶段可能还是空的）。"""
    imported = {}
    for name in ("parser", "generator"):
        try:
            imported[name] = __import__(name)
        except Exception as exc:  # 骨架期允许包尚未就绪
            logging.getLogger(__name__).warning(
                "package %s 暂不可用: %s", name, exc
            )
            imported[name] = None
    return imported


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )
    app.config.from_object(config)
    app.secret_key = config.SECRET_KEY

    packages = _import_packages()
    app.extensions["si_batch_packages"] = packages

    # 认证：注册蓝图并幂等写入种子账号（admin / front1 / social1 / medical1）
    app.register_blueprint(auth.auth_bp)
    auth.ensure_seed_users()

    @app.get("/healthz")
    def healthz():
        ready = {k: v is not None for k, v in packages.items()}
        return {
            "status": "ok",
            "app": app.name,
            "packages": ready,
        }

    @app.get("/")
    @auth.login_required
    def index():
        # 占位首页；真正的仪表盘由 T20 提供，这里刻意保持最简。
        return render_template("index.html")

    return app


app = create_app()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    host, port = config.HOST, config.PORT
    print(f"Listening on {host}:{port}", flush=True)
    app.run(host=host, port=port, debug=False)