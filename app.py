"""app.py — Flask 应用入口。

- 模块级暴露 `app`，可 `from app import app`
- 也提供工厂 `create_app()`
- `python app.py` 时启动开发服务器，监听 0.0.0.0:5010
"""

import logging
import os
import sys

from flask import Flask, render_template

import auth
import config
import db

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


def _register_web_blueprints(app):
    """自动注册 web/ 包下所有暴露 `bp` 的蓝图模块（Wave 3: T13-T19）。

    每个 Wave 3 任务只创建自己的 web/<name>.py + 模板，无需改动 app.py，
    从而避免并行任务在共享文件上的写冲突。
    """
    import importlib
    import pkgutil

    import web

    registered = 0
    for mod in pkgutil.iter_modules(web.__path__):
        try:
            module = importlib.import_module(f"web.{mod.name}")
        except Exception as exc:
            app.logger.warning("web.%s 暂不可用: %s", mod.name, exc)
            continue
        bp = getattr(module, "bp", None)
        if bp is not None:
            app.register_blueprint(bp)
            registered += 1
    if registered:
        app.logger.info("registered %d web blueprint(s)", registered)


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

    # Wave 3 页面蓝图（web/*.py，自动发现）
    _register_web_blueprints(app)

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
        """角色专属首页仪表盘（T20）。

        按当前角色统计简单计数（全部经 db DAL 参数化查询），渲染
        dashboard.html。仅计数 + 快捷入口，不做图表。
        """
        user = auth.current_user()
        role = user["role"]

        def _count(sql, params=()):
            row = db.query_one(sql, params)
            return row[0] if row is not None else 0

        stats = {}
        if role == auth.ROLE_FRONT:
            stats["imported_batches"] = _count(
                "SELECT COUNT(*) FROM import_batches"
            )
        elif role == auth.ROLE_SOCIAL:
            stats["enroll_batches"] = _count(
                "SELECT COUNT(*) FROM import_batches WHERE batch_type = 'enroll'"
            )
            stats["reduce_batches"] = _count(
                "SELECT COUNT(*) FROM import_batches WHERE batch_type = 'reduce'"
            )
            stats["province_injury_count"] = _count(
                "SELECT COUNT(*) FROM province_injury"
            )
        elif role == auth.ROLE_MEDICAL:
            stats["enroll_batches"] = _count(
                "SELECT COUNT(*) FROM import_batches WHERE batch_type = 'enroll'"
            )
            stats["reduce_batches"] = _count(
                "SELECT COUNT(*) FROM import_batches WHERE batch_type = 'reduce'"
            )
        elif role == auth.ROLE_ADMIN:
            stats["user_count"] = _count("SELECT COUNT(*) FROM users")
            stats["enroll_batches"] = _count(
                "SELECT COUNT(*) FROM import_batches WHERE batch_type = 'enroll'"
            )
            stats["reduce_batches"] = _count(
                "SELECT COUNT(*) FROM import_batches WHERE batch_type = 'reduce'"
            )
            stats["total_batches"] = _count(
                "SELECT COUNT(*) FROM import_batches"
            )

        return render_template("dashboard.html", stats=stats)

    return app


app = create_app()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    host, port = config.HOST, config.PORT
    print(f"Listening on {host}:{port}", flush=True)
    app.run(host=host, port=port, debug=False)