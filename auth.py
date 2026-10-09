"""auth.py — 认证 + 角色访问控制（T3）。

提供：
- 4 个角色常量 + ``ROLE_LABELS`` 中文标签
- Flask ``Blueprint``（``auth_bp``）：``/login``、``/logout``
- ``login_required`` / ``require_role(*roles)`` 装饰器 + ``current_user()`` 辅助
- ``ensure_seed_users()``：建表并幂等插入种子账号（密码只存哈希）

密码永远只以 ``werkzeug.security`` 的哈希形式落库；明文仅存在于本模块的
``SEED_USERS`` 常量里（仅供首次建号）。
"""

import functools
import sqlite3
import time

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import db

# ---------------------------------------------------------------------------
# 角色
# ---------------------------------------------------------------------------
ROLE_FRONT = "front"
ROLE_SOCIAL = "social"
ROLE_MEDICAL = "medical"
ROLE_ADMIN = "admin"

#: 角色 -> 中文标签
ROLE_LABELS = {
    ROLE_FRONT: "前台业务员",
    ROLE_SOCIAL: "社保管理员",
    ROLE_MEDICAL: "医保管理员",
    ROLE_ADMIN: "系统管理员",
}

#: 种子账号（用户名, 明文密码, 角色, 显示名）。明文仅用于首次生成哈希。
SEED_USERS = (
    ("admin", "admin123", ROLE_ADMIN, "系统管理员"),
    ("front1", "123456", ROLE_FRONT, "前台业务员"),
    ("social1", "123456", ROLE_SOCIAL, "社保管理员"),
    ("medical1", "123456", ROLE_MEDICAL, "医保管理员"),
)

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# DB 锁重试（T4 等并发写共享 sqlite 时容错）
# ---------------------------------------------------------------------------
def _with_locked_retry(fn, *args, **kwargs):
    """执行 ``fn``，遇 ``database is locked`` 时短暂 sleep 后重试。"""
    delay = 0.2
    attempts = 5
    for attempt in range(attempts):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
    # 不会到达
    return fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# 当前用户
# ---------------------------------------------------------------------------
def current_user():
    """从 session 读取当前登录用户；未登录返回 ``None``。"""
    if not session.get("user_id"):
        return None
    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role"),
        "display_name": session.get("display_name") or session.get("username"),
    }


# ---------------------------------------------------------------------------
# 装饰器
# ---------------------------------------------------------------------------
def login_required(view):
    """未登录 -> 重定向到 ``/login``。"""

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


def require_role(*roles):
    """要求已登录且角色属于 ``roles``；未登录 -> ``/login``，越权 -> 403。"""

    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("auth.login"))
            if session.get("role") not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


# 角色 -> 登录后落地 endpoint。角色专属仪表盘在 T20 提供，当前统一落到首页。
_LANDING_ENDPOINTS = {
    ROLE_FRONT: "index",
    ROLE_SOCIAL: "index",
    ROLE_MEDICAL: "index",
    ROLE_ADMIN: "index",
}


def landing_endpoint(role):
    """返回该角色登录后应跳转的 endpoint 名（当前均为首页）。"""
    return _LANDING_ENDPOINTS.get(role, "index")


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = _with_locked_retry(
            db.query_one,
            "SELECT * FROM users WHERE username = ?",
            (username,),
        )
        if user is not None and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["display_name"] = user["display_name"] or user["username"]
            return redirect(url_for(landing_endpoint(user["role"])))
        flash("用户名或密码错误", "danger")
    return render_template("login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.app_context_processor
def inject_auth_context():
    """把当前用户与角色标签注入所有模板。"""
    return {
        "current_user": current_user(),
        "ROLE_LABELS": ROLE_LABELS,
    }


# ---------------------------------------------------------------------------
# 种子账号
# ---------------------------------------------------------------------------
def ensure_seed_users():
    """建表后幂等插入种子账号。密码以哈希存储。"""
    _with_locked_retry(db.init_db)
    for username, password, role, display_name in SEED_USERS:
        exists = _with_locked_retry(
            db.query_one,
            "SELECT id FROM users WHERE username = ?",
            (username,),
        )
        if exists:
            continue
        password_hash = generate_password_hash(password)
        _with_locked_retry(
            db.execute,
            "INSERT INTO users (username, password_hash, role, display_name) "
            "VALUES (?, ?, ?, ?)",
            (username, password_hash, role, display_name),
        )
