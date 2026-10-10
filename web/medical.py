"""web/medical.py — 医保管理员页面 + 路由（T16）。

提供：
- ``GET  /medical``                  医保报盘页面（增员/减员批次 + 生成记录）
- ``POST /medical/generate``         生成省/市医保增员或减员报盘
                                     （query: ``type``=enroll|reduce, ``batch_id``=int）
- ``GET  /medical/download/<oid>``   下载某个已生成的医保报盘文件

权限：``medical``、``admin``。

生成器调用：
- 增员 → ``generator.medical_enroll.generate(batch_id, out_dir)``
- 减员 → ``generator.medical_reduce.generate(batch_id, out_dir)``
两者均返回 ``{"province": <path>, "city": <path>}``（仅含实际写出的侧）。
每个写出的文件插入一行 ``output_batches``（insurance_type='medical'）。

本模块的一切 SQL 均通过 ``db`` DAL 参数化执行；app.py 的
``_register_web_blueprints`` 会按模块名自动注册本模块暴露的 ``bp``。
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
from generator import medical_enroll, medical_reduce

bp = Blueprint("medical", __name__, url_prefix="/medical")

#: 批次类型 -> 中文标签
_TYPE_LABELS = {"enroll": "增员", "reduce": "减员"}

#: 批次类型 -> 生成器 generate()
_GENERATORS = {
    "enroll": medical_enroll.generate,
    "reduce": medical_reduce.generate,
}

#: 生成器返回字典的键 -> 侧别中文标签（兼容 province/city 与 省/市 两种键）
_SIDE_LABELS = {
    "province": "省医保",
    "city": "市医保",
    "省": "省医保",
    "市": "市医保",
}


def _list_batches(batch_type):
    """按 id 倒序返回指定类型的导入批次。"""
    return db.query_all(
        "SELECT id, batch_type, filename, uploaded_by, uploaded_at, total_rows, status"
        " FROM import_batches WHERE batch_type = ? ORDER BY id DESC",
        (batch_type,),
    )


def _list_outputs():
    """按 id 倒序返回全部医保生成记录。"""
    return db.query_all(
        "SELECT id, batch_id, batch_type, filename, file_path, status,"
        " generated_by, generated_at FROM output_batches"
        " WHERE insurance_type = 'medical' ORDER BY id DESC"
    )


def _render(status=200):
    return (
        render_template(
            "medical.html",
            enroll_batches=_list_batches("enroll"),
            reduce_batches=_list_batches("reduce"),
            outputs=_list_outputs(),
            type_labels=_TYPE_LABELS,
            side_labels=_SIDE_LABELS,
        ),
        status,
    )


@bp.get("")
@auth.login_required
@auth.require_role("medical", "admin")
def index():
    """GET /medical — 医保报盘页面。"""
    return _render()


@bp.route("/generate", methods=["GET", "POST"])
@auth.login_required
@auth.require_role("medical", "admin")
def generate():
    """POST /medical/generate?type=enroll|reduce&batch_id=N — 生成省/市报盘。"""
    batch_type = (request.values.get("type") or "").strip()
    raw_batch_id = (request.values.get("batch_id") or "").strip()

    if batch_type not in _GENERATORS:
        flash("请选择报盘类型（增员 / 减员）", "danger")
        return redirect(url_for("medical.index"))

    try:
        batch_id = int(raw_batch_id)
    except (TypeError, ValueError):
        flash("批次 ID 无效", "danger")
        return redirect(url_for("medical.index"))

    batch = db.query_one(
        "SELECT id, batch_type, filename FROM import_batches WHERE id = ?",
        (batch_id,),
    )
    if batch is None:
        flash(f"批次 #{batch_id} 不存在", "danger")
        return redirect(url_for("medical.index"))
    if batch["batch_type"] != batch_type:
        flash(
            f"批次 #{batch_id} 不是{_TYPE_LABELS[batch_type]}批次",
            "danger",
        )
        return redirect(url_for("medical.index"))

    user = auth.current_user()
    generated_by = user["username"] if user else None

    try:
        written = _GENERATORS[batch_type](
            batch_id=batch_id,
            out_dir=config.OUTPUT_DIR,
            generated_by=generated_by,
        )
    except Exception as exc:  # noqa: BLE001 — 生成失败以页面提示而非 500 呈现
        flash(f"报盘生成失败：{exc}", "danger")
        return redirect(url_for("medical.index"))

    if not written:
        flash(
            f"批次 #{batch_id} 没有可生成的{_TYPE_LABELS[batch_type]}数据",
            "warning",
        )
        return redirect(url_for("medical.index"))

    filenames = []
    for path in written.values():
        if not path:
            continue
        abspath = os.path.abspath(path)
        filename = os.path.basename(abspath)
        db.execute(
            "INSERT INTO output_batches"
            " (batch_id, insurance_type, batch_type, generated_by, filename,"
            "  file_path, status)"
            " VALUES (?, 'medical', ?, ?, ?, ?, 'generated')",
            (batch_id, batch_type, generated_by, filename, abspath),
        )
        filenames.append(filename)

    if filenames:
        flash(
            f"已生成 {len(filenames)} 个医保{_TYPE_LABELS[batch_type]}报盘："
            + "、".join(filenames),
            "success",
        )
    else:
        flash("生成器未输出任何文件", "warning")
    return redirect(url_for("medical.index"))


@bp.get("/download/<int:oid>")
@auth.login_required
@auth.require_role("medical", "admin")
def download(oid):
    """GET /medical/download/<oid> — 下载已生成的医保报盘（附件）。"""
    row = db.query_one(
        "SELECT id, filename, file_path FROM output_batches"
        " WHERE id = ? AND insurance_type = 'medical'",
        (oid,),
    )
    if row is None:
        abort(404)
    path = row["file_path"]
    if not path or not os.path.isfile(path):
        abort(404)
    return send_file(
        path,
        as_attachment=True,
        download_name=row["filename"] or os.path.basename(path),
    )
