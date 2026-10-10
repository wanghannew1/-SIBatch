"""web/admin_users.py — admin 用户管理页面 + 路由（T17）。

系统管理员（``admin``）在此对 ``users`` 表进行 CRUD：新增账号、编辑角色与显示名、
（可选）重置密码、删除账号。登录账号本身由 T3 的种子机制与登录流程负责，本模块
不提供任何自助注册入口。

约束：
- 仅 ``admin`` 角色可访问（``login_required`` + ``require_role("admin")``）。
- 密码只以 ``werkzeug.security.generate_password_hash`` 的哈希落库；界面仅展示
  用户名 / 角色 / 显示名 / 创建时间，绝不暴露 ``password_hash``。
- 所有 SQL 均通过 ``db`` DAL 参数化执行。
- 用户名 UNIQUE 冲突时以 flash 报错并重渲染页面，绝不崩溃（500）。
- ``web/admin_users.py`` 与 ``templates/admin_users.html`` 之外的文件不改动。

app.py 的 ``_register_web_blueprints`` 会按模块名自动注册本模块暴露的 ``bp``。
"""

import sqlite3

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.security import generate_password_hash

import auth
import db

bp = Blueprint("admin_users", __name__, url_prefix="/admin/users")

#: 角色下拉展示顺序（值 -> 中文标签由 ``auth.ROLE_LABELS`` 提供）
_ROLE_ORDER = (
    auth.ROLE_FRONT,
    auth.ROLE_SOCIAL,
    auth.ROLE_MEDICAL,
    auth.ROLE_ADMIN,
)


def _list_users():
    """按 id 升序返回全部用户（只取展示列，绝不取 password_hash）。"""
    return db.query_all(
        "SELECT id, username, role, display_name, created_at"
        " FROM users ORDER BY id ASC"
    )


def _render_page(status=200):
    """渲染用户管理页（含 flash 提示）。"""
    return (
        render_template(
            "admin_users.html",
            users=_list_users(),
            role_order=_ROLE_ORDER,
        ),
        status,
    )


@bp.get("")
@auth.login_required
@auth.require_role("admin")
def list_users():
    """GET /admin/users — 用户列表。"""
    return _render_page()


@bp.post("/add")
@auth.login_required
@auth.require_role("admin")
def add():
    """POST /admin/users/add — 新增账号（密码哈希存储，UNIQUE 冲突不崩溃）。"""
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "").strip()
    display_name = (request.form.get("display_name") or "").strip()

    if not username or not password:
        flash("用户名和密码不能为空", "danger")
        return _render_page()
    if role not in auth.ROLE_LABELS:
        flash("请选择有效的角色", "danger")
        return _render_page()

    password_hash = generate_password_hash(password)
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, role, display_name)"
            " VALUES (?, ?, ?, ?)",
            (username, password_hash, role, display_name or None),
        )
    except sqlite3.IntegrityError:
        # username UNIQUE 冲突：提示已存在，不崩溃。
        flash(f"用户名「{username}」已存在", "danger")
        return _render_page()

    flash(f"已新增用户「{username}」", "success")
    return redirect(url_for("admin_users.list_users"))


@bp.post("/edit/<int:id>")
@auth.login_required
@auth.require_role("admin")
def edit(id):
    """POST /admin/users/edit/<id> — 更新角色 / 显示名；密码留空则不改。"""
    user = db.query_one(
        "SELECT id, username FROM users WHERE id = ?", (id,)
    )
    if user is None:
        flash("用户不存在", "danger")
        return redirect(url_for("admin_users.list_users"))

    role = (request.form.get("role") or "").strip()
    display_name = (request.form.get("display_name") or "").strip()
    password = request.form.get("password") or ""

    if role not in auth.ROLE_LABELS:
        flash("请选择有效的角色", "danger")
        return redirect(url_for("admin_users.list_users"))

    if password:
        password_hash = generate_password_hash(password)
        db.execute(
            "UPDATE users SET role = ?, display_name = ?, password_hash = ?"
            " WHERE id = ?",
            (role, display_name or None, password_hash, id),
        )
    else:
        db.execute(
            "UPDATE users SET role = ?, display_name = ? WHERE id = ?",
            (role, display_name or None, id),
        )

    flash(f"已保存用户「{user['username']}」的修改", "success")
    return redirect(url_for("admin_users.list_users"))


@bp.post("/delete/<int:id>")
@auth.login_required
@auth.require_role("admin")
def delete(id):
    """POST /admin/users/delete/<id> — 删除账号。"""
    user = db.query_one(
        "SELECT id, username FROM users WHERE id = ?", (id,)
    )
    if user is None:
        flash("用户不存在", "danger")
        return redirect(url_for("admin_users.list_users"))

    db.execute("DELETE FROM users WHERE id = ?", (id,))
    flash(f"已删除用户「{user['username']}」", "success")
    return redirect(url_for("admin_users.list_users"))
