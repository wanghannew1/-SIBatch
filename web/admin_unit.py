"""web/admin_unit.py — admin 单位信息配置页面 + 路由（T18）。

系统管理员（admin）在此维护 `unit_config`：社保（social）与医保（medical）
各自的单位编号 / 单位名称。生成报盘时（如 generator.social_enroll 的 R2
B2/E2）从该表读取单位信息填入模板，不硬编码任何单位值。

- GET  `/admin/units`       — 渲染配置表单（回填当前 unit_config 值）
- POST `/admin/units/save`  — 保存表单：social_code/social_name、
                              medical_code/medical_name；空字符串存 NULL，
                              按 insurance_type upsert（ON CONFLICT DO UPDATE）

所有 SQL 均通过 `db` DAL 参数化执行；权限仅 `admin`（require_role）。
app.py 的 `_register_web_blueprints` 会自动注册本模块暴露的 `bp`。
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

import auth
import db

bp = Blueprint("admin_units", __name__, url_prefix="/admin/units")

#: 险种 -> 中文标签（社保 / 医保两套单位信息）
_TYPE_LABELS = {"social": "社保", "medical": "医保"}

#: 表单前缀 -> 险种
_PREFIX_TO_TYPE = {"social": "social", "medical": "medical"}

#: upsert 语句：按 insurance_type 唯一键冲突时更新，空缺行为插入。
#: 需要 SQLite >= 3.24（环境为 3.45.x）。
_UPSERT_SQL = (
    "INSERT INTO unit_config (insurance_type, unit_code, unit_name) "
    "VALUES (?, ?, ?) "
    "ON CONFLICT(insurance_type) DO UPDATE SET "
    "unit_code = excluded.unit_code, "
    "unit_name = excluded.unit_name"
)


def _clean(value):
    """去首尾空白；空字符串归一为 None（DB 存 NULL）。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_units():
    """读取 unit_config 当前值，返回 {险种: {'code': ..., 'name': ...}}。

    缺失的行以 None 占位，模板回填空输入框。
    """
    units = {key: {"code": None, "name": None} for key in _TYPE_LABELS}
    for row in db.query_all(
        "SELECT insurance_type, unit_code, unit_name FROM unit_config"
    ):
        key = row["insurance_type"]
        if key in units:
            units[key] = {"code": row["unit_code"], "name": row["unit_name"]}
    return units


def _form_values():
    """读取表单四项，返回 {险种: {'code': 归一值, 'name': 归一值}}。"""
    values = {}
    for prefix, insurance_type in _PREFIX_TO_TYPE.items():
        values[insurance_type] = {
            "code": _clean(request.form.get(f"{prefix}_code")),
            "name": _clean(request.form.get(f"{prefix}_name")),
        }
    return values


@bp.get("")
@auth.login_required
@auth.require_role("admin")
def index():
    """GET /admin/units — 单位信息配置表单（回填当前值）。"""
    return render_template(
        "admin_units.html",
        units=_load_units(),
        type_labels=_TYPE_LABELS,
    )


@bp.post("/save")
@auth.login_required
@auth.require_role("admin")
def save():
    """POST /admin/units/save — upsert 社保/医保单位信息并重定向。"""
    values = _form_values()
    for insurance_type in ("social", "medical"):
        item = values[insurance_type]
        db.execute(
            _UPSERT_SQL,
            (insurance_type, item["code"], item["name"]),
        )
    flash("单位信息已保存", "success")
    return redirect(url_for("admin_units.index"))
