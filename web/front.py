"""web/front.py — 前台上传页面 + 路由（T13）。

前台业务员（front）与系统管理员（admin）在此上传增员表 / 减员表（.xls），
调用 ``parser.enroll_parser`` / ``parser.reduce_parser`` 解析入库，并展示
成功条数与失败原因；页面下方列出全部已导入批次（类型/文件名/上传人/时间/条数）。

本模块只负责「保存上传文件 + 调解析器 + 渲染」。所有入库（import_batches
与 enroll/reduce_records）由解析器完成；本模块的一切 SQL 均通过 ``db`` DAL
参数化执行。

app.py 的 ``_register_web_blueprints`` 会按模块名自动注册本模块暴露的 ``bp``。
"""

import os
import uuid

from flask import Blueprint, flash, render_template, request

import auth
import config
import db
from parser import enroll_parser, reduce_parser

bp = Blueprint("upload", __name__, url_prefix="/upload")

#: 批次类型 -> 中文标签
_TYPE_LABELS = {"enroll": "增员", "reduce": "减员"}

#: 类型 -> 解析器
_PARSERS = {"enroll": enroll_parser.parse, "reduce": reduce_parser.parse}


def _list_batches():
    """按 id 倒序（最新在前）返回导入批次列表。"""
    return db.query_all(
        "SELECT id, batch_type, filename, uploaded_by, uploaded_at, total_rows, status"
        " FROM import_batches ORDER BY id DESC"
    )


def _render(batches=None, result=None, active_type="enroll", status=200):
    return (
        render_template(
            "upload.html",
            batches=batches if batches is not None else _list_batches(),
            result=result,
            active_type=active_type,
            type_labels=_TYPE_LABELS,
        ),
        status,
    )


@bp.get("")
@auth.login_required
@auth.require_role("front", "admin")
def upload_page():
    """GET /upload — 渲染上传页面 + 批次列表。"""
    return _render()


@bp.post("")
@auth.login_required
@auth.require_role("front", "admin")
def upload_submit():
    """POST /upload — 保存上传文件并调用解析器入库。"""
    upload = request.files.get("file")
    batch_type = (request.form.get("type") or "").strip()

    if batch_type not in _PARSERS:
        flash("请选择导入类型（增员 / 减员）", "danger")
        return _render(active_type=batch_type or "enroll")

    if upload is None or not upload.filename:
        flash("请选择要上传的文件", "danger")
        return _render(active_type=batch_type)

    original_name = upload.filename
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in config.ALLOWED_EXTENSIONS:
        allowed = "、".join(sorted(config.ALLOWED_EXTENSIONS))
        flash(f"不支持的文件类型 .{ext or '?'}，仅允许 {allowed}", "danger")
        return _render(active_type=batch_type)

    # 存储名：随机前缀 + 原扩展名（避免中文名/路径穿越，原文件名保留用于展示）。
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(config.UPLOAD_DIR, stored_name)
    upload.save(save_path)

    user = auth.current_user()
    uploaded_by = user["username"] if user else None

    try:
        result = _PARSERS[batch_type](
            save_path, filename=original_name, uploaded_by=uploaded_by
        )
    except Exception as exc:  # noqa: BLE001 — 解析失败需以页面提示而非 500 呈现
        flash(f"文件解析失败：{exc}", "danger")
        return _render(active_type=batch_type)

    type_label = _TYPE_LABELS[batch_type]
    success_count = result["success_count"]
    error_count = len(result["errors"])
    if success_count and not error_count:
        flash(f"成功导入 {success_count} 条{type_label}记录", "success")
    elif success_count:
        flash(
            f"成功导入 {success_count} 条{type_label}记录，{error_count} 行失败",
            "warning",
        )
    else:
        flash(f"未导入任何记录，{error_count} 行失败", "danger")

    return _render(result=result, active_type=batch_type)
