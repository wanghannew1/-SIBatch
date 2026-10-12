"""web/front.py — 前台上传页面 + 路由（T13）。

前台业务员（front）与系统管理员（admin）在此：
- 上传增员/减员表，解析入库并展示成功/失败明细
- 查看全部人员信息总表（增员/减员 Tab，带过滤）
- 查看单个批次明细、删除自己上传的批次（已报盘锁定）

本模块只负责「保存上传文件 + 调解析器 + 渲染」。所有入库（import_batches
与 enroll/reduce_records）由解析器完成；本模块的一切 SQL 均通过 ``db`` DAL
参数化执行。
"""

import os
import uuid

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import auth
import config
import db
from parser import enroll_parser, reduce_parser

bp = Blueprint("upload", __name__, url_prefix="/upload")

_TYPE_LABELS = {"enroll": "增员", "reduce": "减员"}

_PARSERS = {"enroll": enroll_parser.parse, "reduce": reduce_parser.parse}

#: 明细展示字段（field -> 中文标签），按展示顺序排列。
_ENROLL_DISPLAY = (
    ("name", "姓名"),
    ("id_card", "身份证号码"),
    ("gender", "性别"),
    ("birthday", "出生日期"),
    ("ethnicity", "民族"),
    ("person_identity", "人员身份"),
    ("household_type", "户口性质"),
    ("phone", "联系电话"),
    ("contract_start", "合同开始时间"),
    ("contract_end", "合同终止时间"),
    ("contract_salary", "合同工资"),
    ("social_location", "社保参保属地"),
    ("social_ym", "社保参保年月"),
    ("medical_location", "医保参保属地"),
    ("medical_ym", "医保参保年月"),
)

_REDUCE_DISPLAY = (
    ("name", "姓名"),
    ("id_card", "身份证号码"),
    ("terminate_date", "合同终止日期"),
    ("social_reduce_ym", "社保报减年月"),
    ("medical_reduce_ym", "医保报减年月"),
    ("injury_reduce_ym", "工伤报减年月"),
    ("terminate_reason", "合同终止原因"),
    ("unemployment_benefit", "是否享受失业金"),
    ("salary_end_ym", "工资结束年月"),
    ("economic_compensation", "是否经济赔偿"),
    ("remark", "备注"),
)

#: 类型 -> 明细展示字段
_DISPLAY_FIELDS = {"enroll": _ENROLL_DISPLAY, "reduce": _REDUCE_DISPLAY}


def _batch_options(batch_type):
    return db.query_all(
        "SELECT id, filename FROM import_batches WHERE batch_type = ? ORDER BY id DESC",
        (batch_type,),
    )


def _uploader_options():
    rows = db.query_all(
        "SELECT DISTINCT uploaded_by FROM import_batches"
        " WHERE uploaded_by IS NOT NULL AND TRIM(uploaded_by) <> '' ORDER BY uploaded_by"
    )
    return [r["uploaded_by"] for r in rows]


def _parse_filters(args):
    keyword = (args.get("keyword") or "").strip() or None
    batch_id_raw = (args.get("batch_id") or "").strip()
    batch_id = int(batch_id_raw) if batch_id_raw.isdigit() else None
    uploaded_by = (args.get("uploaded_by") or "").strip() or None
    reported_raw = (args.get("reported") or "").strip()
    reported = {"1": 1, "0": 0}.get(reported_raw)
    location = (args.get("location") or "").strip() or None
    return dict(
        keyword=keyword,
        batch_id=batch_id,
        uploaded_by=uploaded_by,
        reported=reported,
        location=location,
    )


def _list_batches():
    """按 id 倒序（最新在前）返回导入批次列表。

    每项为 dict，附带 ``locked``（该批次下是否已有人员生成报盘）与
    ``can_delete``（admin 全可删；front 仅可删自己上传的且未锁定的）。
    """
    rows = db.query_all(
        "SELECT b.id, b.batch_type, b.filename, b.uploaded_by, b.uploaded_at,"
        " b.total_rows, b.status,"
        " CASE WHEN b.batch_type = 'enroll' THEN"
        "   (SELECT COUNT(*) FROM output_records o WHERE o.record_type = 'enroll'"
        "     AND o.record_id IN (SELECT id FROM enroll_records e WHERE e.batch_id = b.id))"
        " ELSE"
        "   (SELECT COUNT(*) FROM output_records o WHERE o.record_type = 'reduce'"
        "     AND o.record_id IN (SELECT id FROM reduce_records r WHERE r.batch_id = b.id))"
        " END AS reported_count"
        " FROM import_batches b ORDER BY b.id DESC"
    )
    user = auth.current_user()
    username = user["username"] if user else None
    is_admin = bool(user and user["role"] == auth.ROLE_ADMIN)
    batches = []
    for r in rows:
        locked = r["reported_count"] > 0
        can_delete = (not locked) and (is_admin or r["uploaded_by"] == username)
        batches.append(
            {
                "id": r["id"],
                "batch_type": r["batch_type"],
                "filename": r["filename"],
                "uploaded_by": r["uploaded_by"],
                "uploaded_at": r["uploaded_at"],
                "total_rows": r["total_rows"],
                "status": r["status"],
                "locked": locked,
                "can_delete": can_delete,
            }
        )
    return batches


def _render(batches=None, result=None, active_type="enroll", status=200,
            persons=None, filters=None, batch_options=None,
            uploader_options=None, persons_active="enroll"):
    return (
        render_template(
            "upload.html",
            batches=batches if batches is not None else _list_batches(),
            result=result,
            active_type=active_type,
            type_labels=_TYPE_LABELS,
            persons=persons,
            filters=filters,
            batch_options=batch_options,
            uploader_options=uploader_options,
            persons_active=persons_active,
        ),
        status,
    )


@bp.get("")
@auth.login_required
@auth.require_role("front", "admin")
def upload_page():
    """GET /upload — 渲染上传页面 + 批次列表 + 人员信息总表。"""
    persons_active = request.args.get("ptype") or "enroll"
    if persons_active not in ("enroll", "reduce"):
        persons_active = "enroll"
    filters = _parse_filters(request.args)
    persons = db.list_person_records(persons_active, **filters)
    return _render(
        persons=persons,
        filters=filters,
        batch_options=_batch_options(persons_active),
        uploader_options=_uploader_options(),
        persons_active=persons_active,
    )


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

    stored_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(config.UPLOAD_DIR, stored_name)
    upload.save(save_path)

    user = auth.current_user()
    uploaded_by = user["username"] if user else None

    try:
        result = _PARSERS[batch_type](
            save_path, filename=original_name, uploaded_by=uploaded_by
        )
    except Exception as exc:
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


@bp.get("/batch/<int:batch_id>")
@auth.login_required
@auth.require_role("front", "admin")
def batch_detail(batch_id):
    """GET /upload/batch/<id> — 查看某个导入批次的记录明细。"""
    batch = db.query_one(
        "SELECT * FROM import_batches WHERE id = ?", (batch_id,)
    )
    if batch is None:
        abort(404)

    table = "enroll_records" if batch["batch_type"] == "enroll" else "reduce_records"
    records = db.query_all(
        f"SELECT * FROM {table} WHERE batch_id = ? ORDER BY id", (batch_id,)
    )
    return render_template(
        "batch_detail.html",
        batch=batch,
        records=records,
        fields=_DISPLAY_FIELDS[batch["batch_type"]],
        type_labels=_TYPE_LABELS,
    )


@bp.post("/batch/<int:batch_id>/delete")
@auth.login_required
@auth.require_role("front", "admin")
def delete_batch(batch_id):
    """POST /upload/batch/<id>/delete — 删除批次（连带明细与原始文件）。

    权限：admin 可删任意批次；front 仅可删自己上传的。该批次下已有人员
    生成报盘（output_records 存在关联）时锁定，禁止删除。
    """
    user = auth.current_user()
    batch = db.query_one(
        "SELECT * FROM import_batches WHERE id = ?", (batch_id,)
    )
    if batch is None:
        flash("批次不存在", "danger")
        return redirect(url_for("upload.upload_page"))

    if user["role"] != auth.ROLE_ADMIN and batch["uploaded_by"] != user["username"]:
        abort(403)

    table = "enroll_records" if batch["batch_type"] == "enroll" else "reduce_records"
    row = db.query_one(
        f"SELECT COUNT(*) AS n FROM output_records o"
        f" WHERE o.record_type = ? AND o.record_id IN"
        f" (SELECT id FROM {table} WHERE batch_id = ?)",
        (batch["batch_type"], batch_id),
    )
    if row["n"] > 0:
        flash(
            f"批次 #{batch_id} 已有人员生成报盘，无法删除。如需处理请联系社保/医保管理员。",
            "danger",
        )
        return redirect(url_for("upload.upload_page"))

    stored_name = batch["stored_name"]
    if stored_name:
        file_path = os.path.join(config.UPLOAD_DIR, stored_name)
        if os.path.isfile(file_path):
            os.remove(file_path)

    db.execute("DELETE FROM import_batches WHERE id = ?", (batch_id,))
    flash(f"批次 #{batch_id} 已删除，可重新上传。", "success")
    return redirect(url_for("upload.upload_page"))
