"""web/admin_mapping.py — admin 映射/字典/默认值配置页面 + 路由（T19）。

三个可在线配置的分区（全部为 DB 表驱动，生成器运行时读库生效）：

1. 减员原因映射（``mapping_stop_reason``）：合同终止原因 → 社保停保原因 /
    医保变更原因。``POST /admin/mappings/save_reason`` 与
    ``POST /admin/mappings/save`` （行为完全相同的别名） 按 ``source_reason``
    主键 upsert（INSERT ... ON CONFLICT DO UPDATE）。
2. 字典映射（``dict_mapping``）：分类/来源代码/目标值。
   ``POST /admin/mappings/save_dict`` 按 (category, source_code) upsert；
   ``POST /admin/mappings/delete_dict`` 删除指定行。
3. 默认值（``system_defaults``）：键/值。``POST /admin/mappings/save_default``
   按 ``key`` upsert。

所有 SQL 均通过 ``db`` DAL 参数化执行；本模块不硬编码任何字典/映射业务值，
页面展示与写入全部来自数据库表。

``app.py`` 的 ``_register_web_blueprints`` 按模块名自动注册本模块暴露的 ``bp``。
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

import auth
import db

bp = Blueprint("admin_mappings", __name__, url_prefix="/admin/mappings")

# ---------------------------------------------------------------------------
# SQL（全部参数化；upsert 使用 sqlite 的 ON CONFLICT ... DO UPDATE）
# ---------------------------------------------------------------------------

_SELECT_REASONS = (
    "SELECT source_reason, social_stop_reason, medical_change_reason"
    " FROM mapping_stop_reason ORDER BY source_reason"
)

_UPSERT_REASON = (
    "INSERT INTO mapping_stop_reason"
    " (source_reason, social_stop_reason, medical_change_reason)"
    " VALUES (?, ?, ?)"
    " ON CONFLICT(source_reason) DO UPDATE SET"
    " social_stop_reason = excluded.social_stop_reason,"
    " medical_change_reason = excluded.medical_change_reason"
)

_SELECT_DICT_CATEGORIES = (
    "SELECT DISTINCT category FROM dict_mapping ORDER BY category"
)

_SELECT_DICT = (
    "SELECT category, source_code, target_value FROM dict_mapping"
    " WHERE category = ? ORDER BY source_code"
)

_UPSERT_DICT = (
    "INSERT INTO dict_mapping (category, source_code, target_value)"
    " VALUES (?, ?, ?)"
    " ON CONFLICT(category, source_code) DO UPDATE SET"
    " target_value = excluded.target_value"
)

_DELETE_DICT = (
    "DELETE FROM dict_mapping WHERE category = ? AND source_code = ?"
)

_SELECT_DEFAULTS = (
    "SELECT key, value FROM system_defaults ORDER BY key"
)

_UPSERT_DEFAULT = (
    "INSERT INTO system_defaults (key, value) VALUES (?, ?)"
    " ON CONFLICT(key) DO UPDATE SET value = excluded.value"
)


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------
def _load_reasons():
    """减员原因映射全部行。"""
    return db.query_all(_SELECT_REASONS)


def _load_dict(active_category=None):
    """字典分类列表 + 当前分类的行。

    返回 (categories, rows, active_category)。首次访问（无 active_category）
    时默认选中字典序第一个分类。
    """
    categories = [
        row["category"] for row in db.query_all(_SELECT_DICT_CATEGORIES)
    ]
    if not categories:
        return [], [], ""
    if active_category not in categories:
        # 允许通过 query string 预览「即将新建」的分类
        if active_category:
            return categories, [], active_category
        active_category = categories[0]
    rows = db.query_all(_SELECT_DICT, (active_category,))
    return categories, rows, active_category


def _load_defaults():
    """系统默认值全部行。"""
    return db.query_all(_SELECT_DEFAULTS)


def _form(*names):
    """读取并 trim 表单字段；字段缺失时返回空串。"""
    return [(request.form.get(name) or "").strip() for name in names]


def _render_page(dict_category=None, status=200):
    dict_categories, dict_rows, active_dict_category = _load_dict(dict_category)
    return (
        render_template(
            "admin_mappings.html",
            reasons=_load_reasons(),
            dict_categories=dict_categories,
            dict_rows=dict_rows,
            active_dict_category=active_dict_category,
            defaults=_load_defaults(),
        ),
        status,
    )


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------
@bp.get("")
@auth.login_required
@auth.require_role("admin")
def mappings_page():
    """GET /admin/mappings — 映射/字典/默认值配置页（仅 admin）。"""
    return _render_page()


# ---------------------------------------------------------------------------
# 1. 减员原因映射
# ---------------------------------------------------------------------------
@bp.post("/save_reason")
@auth.login_required
@auth.require_role("admin")
def save_reason():
    """POST /admin/mappings/save_reason — upsert 一条减员原因映射。"""
    source, social, medical = _form("source", "social", "medical")
    if not source:
        flash("合同终止原因不能为空", "danger")
        return redirect(url_for("admin_mappings.mappings_page"))
    db.execute(_UPSERT_REASON, (source, social, medical))
    flash(f"已保存减员原因映射：{source}", "success")
    return redirect(url_for("admin_mappings.mappings_page"))


@bp.post("/save")
@auth.login_required
@auth.require_role("admin")
def save():
    """POST /admin/mappings/save — 同 save_reason 的别名路由。

    项目计划的 QA 直接 POST 该 URL（表单字段 source/social/medical），
    行为与 ``save_reason`` 完全一致：复用同一 upsert SQL，按
    ``source_reason`` 主键写入。管理页面仍继续使用 ``save_reason``。
    """
    source, social, medical = _form("source", "social", "medical")
    if not source:
        flash("合同终止原因不能为空", "danger")
        return redirect(url_for("admin_mappings.mappings_page"))
    db.execute(_UPSERT_REASON, (source, social, medical))
    flash(f"已保存减员原因映射：{source}", "success")
    return redirect(url_for("admin_mappings.mappings_page"))


# ---------------------------------------------------------------------------
# 2. 字典映射
# ---------------------------------------------------------------------------
@bp.post("/save_dict")
@auth.login_required
@auth.require_role("admin")
def save_dict():
    """POST /admin/mappings/save_dict — upsert 一条字典映射。"""
    category, source_code, target_value = _form(
        "category", "source_code", "target_value"
    )
    if not category or not source_code:
        flash("字典分类与来源代码不能为空", "danger")
        return redirect(
            url_for("admin_mappings.mappings_page", category=category or None)
        )
    db.execute(_UPSERT_DICT, (category, source_code, target_value))
    flash(f"已保存字典映射：{category} / {source_code}", "success")
    return redirect(
        url_for("admin_mappings.mappings_page", category=category)
    )


@bp.post("/delete_dict")
@auth.login_required
@auth.require_role("admin")
def delete_dict():
    """POST /admin/mappings/delete_dict — 删除一条字典映射。"""
    category, source_code = _form("category", "source_code")
    if not category or not source_code:
        flash("字典分类与来源代码不能为空", "danger")
        return redirect(url_for("admin_mappings.mappings_page"))
    db.execute(_DELETE_DICT, (category, source_code))
    flash(f"已删除字典映射：{category} / {source_code}", "success")
    return redirect(
        url_for("admin_mappings.mappings_page", category=category)
    )


# ---------------------------------------------------------------------------
# 3. 默认值
# ---------------------------------------------------------------------------
@bp.post("/save_default")
@auth.login_required
@auth.require_role("admin")
def save_default():
    """POST /admin/mappings/save_default — upsert 一条系统默认值。"""
    key, value = _form("key", "value")
    if not key:
        flash("默认值键不能为空", "danger")
        return redirect(url_for("admin_mappings.mappings_page"))
    db.execute(_UPSERT_DEFAULT, (key, value))
    flash(f"已保存默认值：{key}", "success")
    return redirect(url_for("admin_mappings.mappings_page"))
