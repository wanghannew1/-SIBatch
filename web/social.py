"""web/social.py — 社保管理员页面 + 路由（T14）。

- GET  /social               → 列出增员/减员批次 + 社保生成记录（output_batches）
- POST /social/generate      → 调 T8/T9 生成社保增员/减员报盘并记录 output_batches
- GET  /social/download/<id> → 下载已生成的报盘文件

权限：social、admin。医保/省工伤报盘不在此页暴露（分别走 T16/T15 页面）。
"""

import os

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


@bp.get("")
@bp.get("/")
@auth.require_role(*_ROLES)
def index():
    """社保管理首页：增员批次、减员批次、社保生成记录。"""
    enroll_batches = db.query_all(
        "SELECT * FROM import_batches WHERE batch_type = 'enroll' ORDER BY id DESC"
    )
    reduce_batches = db.query_all(
        "SELECT * FROM import_batches WHERE batch_type = 'reduce' ORDER BY id DESC"
    )
    outputs = db.query_all(
        "SELECT * FROM output_batches WHERE insurance_type = 'social' ORDER BY id DESC"
    )
    return render_template(
        "social.html",
        enroll_batches=enroll_batches,
        reduce_batches=reduce_batches,
        outputs=outputs,
    )


@bp.post("/generate")
@auth.require_role(*_ROLES)
def generate():
    """按批次生成社保报盘（type=enroll|reduce，batch_id 为 import_batches.id）。

    type/batch_id 支持 query 参数与表单字段两种来源（页面表单用隐藏字段提交）。
    """
    batch_type = request.args.get("type") or request.form.get("type")
    batch_id_raw = request.args.get("batch_id") or request.form.get("batch_id")
    try:
        batch_id = int(batch_id_raw)
    except (TypeError, ValueError):
        batch_id = None

    if batch_type not in ("enroll", "reduce") or batch_id is None:
        flash("参数错误：type 必须为 enroll 或 reduce，batch_id 必须为整数", "danger")
        return redirect(url_for("social.index"))

    batch = db.query_one(
        "SELECT * FROM import_batches WHERE id = ? AND batch_type = ?",
        (batch_id, batch_type),
    )
    if batch is None:
        flash("批次不存在或类型不匹配", "danger")
        return redirect(url_for("social.index"))

    username = auth.current_user()["username"]
    filename = f"social_{batch_type}_b{batch_id}.xlsx"
    out = os.path.join(config.OUTPUT_DIR, filename)

    try:
        if batch_type == "enroll":
            social_enroll.generate(batch_id=batch_id, out=out, generated_by=username)
        else:
            social_reduce.generate(batch_id=batch_id, out=out, generated_by=username)
    except Exception as exc:
        flash(f"生成失败：{exc}", "danger")
        return redirect(url_for("social.index"))

    # 确保 output_batches 有记录：T8 生成器已自带插入；T9 不插入，这里补上。
    existing = db.query_one(
        "SELECT id FROM output_batches WHERE batch_id = ? AND insurance_type = 'social'"
        " AND batch_type = ? AND filename = ?",
        (batch_id, batch_type, filename),
    )
    if existing is None:
        db.execute(
            "INSERT INTO output_batches"
            " (batch_id, insurance_type, batch_type, generated_by, filename, file_path, status)"
            " VALUES (?, 'social', ?, ?, ?, ?, 'generated')",
            (batch_id, batch_type, username, filename, out),
        )

    flash("生成成功", "success")
    return redirect(url_for("social.index"))


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