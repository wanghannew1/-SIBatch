"""web/social.py — 社保管理员页面 + 路由（T14）。

- GET  /social               → 人员信息总表（增员/减员 Tab）+ 过滤 + 勾选生成
- POST /social/generate      → 按选中人员生成社保增员/减员报盘（跨批次合并）
- GET  /social/download/<id> → 下载已生成的报盘文件

权限：social、admin。医保/省工伤报盘不在此页暴露。
"""

import os
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

import auth
import config
import db
from generator import social_enroll, social_reduce

bp = Blueprint("social", __name__, url_prefix="/social")

_ROLES = (auth.ROLE_SOCIAL, auth.ROLE_ADMIN)
_TYPE_LABELS = {"enroll": "增员", "reduce": "减员"}


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


@bp.get("")
@bp.get("/")
@auth.require_role(*_ROLES)
def index():
    active = request.args.get("ptype") or "enroll"
    if active not in ("enroll", "reduce"):
        active = "enroll"
    filters = _parse_filters(request.args)
    persons = db.list_person_records(active, insurance_type="social", **filters)
    outputs = db.query_all(
        "SELECT * FROM output_batches WHERE insurance_type = 'social' ORDER BY id DESC"
    )
    return render_template(
        "social.html",
        active=active,
        persons=persons,
        filters=filters,
        batch_options=_batch_options(active),
        uploader_options=_uploader_options(),
        outputs=outputs,
        type_labels=_TYPE_LABELS,
    )


@bp.post("/generate")
@auth.require_role(*_ROLES)
def generate():
    """按选中人员（record_ids）生成社保增员/减员报盘，跨批次合并一个文件。"""
    batch_type = (request.form.get("type") or "").strip()
    ids = []
    for value in request.form.getlist("record_ids"):
        value = value.strip()
        if value.isdigit():
            ids.append(int(value))
    ids = list(dict.fromkeys(ids))

    if batch_type not in ("enroll", "reduce"):
        flash("请选择报盘类型（增员 / 减员）", "danger")
        return redirect(url_for("social.index", ptype=batch_type or "enroll"))
    if not ids:
        flash("请至少勾选一条记录", "danger")
        return redirect(url_for("social.index", ptype=batch_type))

    placeholders = ",".join("?" * len(ids))
    already_rows = db.query_all(
        f"SELECT DISTINCT o.record_id FROM output_records o"
        f" JOIN output_batches ob ON ob.id = o.output_id"
        f" WHERE o.record_type = ? AND ob.insurance_type = 'social'"
        f" AND o.record_id IN ({placeholders})",
        (batch_type,) + tuple(ids),
    )
    already = {r["record_id"] for r in already_rows}
    fresh_ids = [i for i in ids if i not in already]
    skipped = len(ids) - len(fresh_ids)
    if not fresh_ids:
        flash("所选记录均已生成过报盘", "warning")
        return redirect(url_for("social.index", ptype=batch_type))

    username = auth.current_user()["username"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"social_{batch_type}_{ts}.xlsx"
    out = os.path.join(config.OUTPUT_DIR, filename)

    try:
        if batch_type == "enroll":
            social_enroll.generate(fresh_ids, out=out, generated_by=username)
        else:
            social_reduce.generate(fresh_ids, out=out, generated_by=username)
    except Exception as exc:
        flash(f"生成失败：{exc}", "danger")
        return redirect(url_for("social.index", ptype=batch_type))

    output_id, _ = db.execute(
        "INSERT INTO output_batches"
        " (batch_id, insurance_type, batch_type, generated_by, filename,"
        "  file_path, status, record_count)"
        " VALUES (NULL, 'social', ?, ?, ?, ?, 'generated', ?)",
        (batch_type, username, filename, out, len(fresh_ids)),
    )
    for rid in fresh_ids:
        db.execute(
            "INSERT INTO output_records (output_id, record_id, record_type)"
            " VALUES (?, ?, ?)",
            (output_id, rid, batch_type),
        )

    message = f"已生成社保{_TYPE_LABELS[batch_type]}报盘，包含 {len(fresh_ids)} 人"
    if skipped:
        message += f"（已跳过 {skipped} 个已报盘记录）"
    flash(message, "success")
    return redirect(url_for("social.index", ptype=batch_type))


@bp.get("/download/<int:oid>")
@auth.require_role(*_ROLES)
def download(oid):
    """下载社保生成记录对应的报盘文件（attachment）。"""
    row = db.query_one(
        "SELECT * FROM output_batches WHERE id = ? AND insurance_type = 'social'",
        (oid,),
    )
    if row is None or not row["file_path"] or not os.path.isfile(row["file_path"]):
        abort(404)
    return send_file(
        row["file_path"],
        as_attachment=True,
        download_name=row["filename"] or os.path.basename(row["file_path"]),
    )
