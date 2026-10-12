"""web/province_injury.py — 省工伤人员信息管理页面 + 路由（T15）。

- 列表 / 新增 / 编辑 / 删除 / 导入（增员模板 .xls）/ 生成减员报盘（T10）
- 权限：``social``、``admin``
- 数据独立存 ``province_injury`` 表，不与其他批次（import_batches /
  enroll_records / reduce_records）混用。

导入复用 ``parser.enroll_parser`` 的增员模板提取逻辑（同一套列名/单元格
文本规则/必录校验），但只写入 ``province_injury`` —— 不调用会写
``import_batches`` + ``enroll_records`` 的 ``parse()``，保证省工伤名单
与增员/减员批次流程完全隔离。
"""

import json
import os
import time
from datetime import datetime

import xlrd
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

import auth
import config
import db
from columns import (
    ENROLL_INPUT_COLUMNS,
    ENROLL_INPUT_DATA_START_ROW,
    ENROLL_INPUT_SHEET,
)
from mapping import derive_birthday, derive_gender
from parser import enroll_parser

bp = Blueprint("province_injury", __name__, url_prefix="/province_injury")

# ---------------------------------------------------------------------------
# 字段定义
# ---------------------------------------------------------------------------
#: (字段名, 中文标签, 占位提示, 分组)
#: 分组 basic/contract 为新增表单核心字段；edit 弹窗展示全部分组。
_FORM_FIELDS = (
    # 基本信息
    ("name", "姓名", "50个汉字以内", "basic"),
    ("id_card", "证件号码", "18位身份证号码", "basic"),
    ("gender", "性别", "留空由证件号码推导", "basic"),
    ("birthday", "出生日期", "留空由证件号码推导", "basic"),
    ("ethnicity", "民族", "如 01-汉族", "basic"),
    ("person_identity", "人员身份", "如 91-干部", "basic"),
    ("household_type", "户口性质", "如 11-本市城镇户口", "basic"),
    ("phone", "联系电话", "11位数字", "basic"),
    ("doc_type", "证件类型", "空=居民身份证", "basic"),
    # 合同信息
    ("settlement_unit", "结算单元", "", "contract"),
    ("contract_start_date", "合同开始时间", "yyyy-mm-dd", "contract"),
    ("contract_end", "合同终止时间", "yyyy-mm-dd", "contract"),
    ("contract_salary", "合同工资", "10位整数2位小数", "contract"),
    # 参保信息
    ("participate_pension", "是否参加养老保险", "1-是 / 0-否", "insurance"),
    ("participate_unemployment", "是否参加失业保险", "1-是 / 0-否", "insurance"),
    ("participate_medical", "是否参加医疗保险", "1-是 / 0-否", "insurance"),
    ("participate_injury", "是否参加工伤保险", "1-是 / 0-否", "insurance"),
    ("participate_maternity", "是否参加生育保险", "1-是 / 0-否", "insurance"),
    ("social_location", "社保参保属地", "如 220100000000-吉林省长春市", "insurance"),
    ("social_ym", "社保参保年月", "yyyymm", "insurance"),
    ("medical_location", "医保参保属地", "如 229900000000-吉林省省直", "insurance"),
    ("medical_ym", "医保参保年月", "yyyymm", "insurance"),
    ("base_pension", "养老缴费基数", "", "insurance"),
    ("base_unemployment", "失业缴费基数", "", "insurance"),
    ("base_medical", "医保缴费基数", "", "insurance"),
    ("base_injury", "工伤缴费基数", "", "insurance"),
    ("base_maternity", "生育缴费基数", "", "insurance"),
    ("salary_account", "工资账号", "16位整数", "insurance"),
    ("bank_name", "发放银行", "如 02000-建设银行", "insurance"),
    ("social_status", "社保参保状态", "", "insurance"),
    ("medical_status", "医保参保状态", "", "insurance"),
    # 停保信息
    ("stop_date", "停保日期", "yyyy-mm-dd", "stop"),
    ("stop_reason", "停保原因", "", "stop"),
    ("status", "状态", "active / stopped", "stop"),
)

#: 新增表单展示的分组（核心字段）
_ADD_GROUPS = ("basic", "contract")

#: province_injury 列名 -> 增员模板列名（gender/birthday 由身份证推导，无对应列）
_FIELD_COLUMNS = {
    "name": "姓名",
    "id_card": "身份证号码",
    "ethnicity": "民族",
    "person_identity": "人员身份",
    "household_type": "户口性质",
    "phone": "联系电话",
    "contract_start_date": "合同开始时间",
    "contract_end": "合同终止时间",
    "contract_salary": "合同工资",
    "participate_pension": "是否参加养老保险",
    "participate_unemployment": "是否参加失业保险",
    "participate_medical": "是否参加医疗保险",
    "participate_injury": "是否参加工伤保险",
    "participate_maternity": "是否参加生育保险",
    "social_location": "社保参保属地",
    "social_ym": "社保参保年月",
    "medical_location": "医保参保属地",
    "medical_ym": "医保参保年月",
    "base_pension": "养老缴费基数",
    "base_unemployment": "失业缴费基数",
    "base_medical": "医保缴费基数",
    "base_injury": "工伤缴费基数",
    "base_maternity": "生育缴费基数",
    "salary_account": "工资账号",
    "bank_name": "发放银行",
    "social_status": "社保参保状态",
    "medical_status": "医保参保状态",
    "doc_type": "证件类型",
}

#: INSERT 参数顺序（与 _INSERT_SQL 的列一一对应）
_INSERT_ORDER = (
    "name", "id_card", "settlement_unit", "contract_start_date", "gender",
    "birthday", "ethnicity", "person_identity", "household_type", "phone",
    "contract_end", "contract_salary", "participate_pension",
    "participate_unemployment", "participate_medical", "participate_injury",
    "participate_maternity", "social_location", "social_ym",
    "medical_location", "medical_ym", "base_pension", "base_unemployment",
    "base_medical", "base_injury", "base_maternity", "salary_account",
    "bank_name", "social_status", "medical_status", "doc_type",
    "stop_date", "stop_reason", "status", "raw_json",
)

_INSERT_SQL = (
    "INSERT INTO province_injury ("
    "name, id_card, settlement_unit, contract_start_date, gender, birthday,"
    " ethnicity, person_identity, household_type, phone, contract_end,"
    " contract_salary, participate_pension, participate_unemployment,"
    " participate_medical, participate_injury, participate_maternity,"
    " social_location, social_ym, medical_location, medical_ym,"
    " base_pension, base_unemployment, base_medical, base_injury,"
    " base_maternity, salary_account, bank_name, social_status,"
    " medical_status, doc_type, stop_date, stop_reason, status, raw_json"
    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
    " ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

_UPDATE_SQL = (
    "UPDATE province_injury SET "
    "name=?, id_card=?, settlement_unit=?, contract_start_date=?, gender=?,"
    " birthday=?, ethnicity=?, person_identity=?, household_type=?, phone=?,"
    " contract_end=?, contract_salary=?, participate_pension=?,"
    " participate_unemployment=?, participate_medical=?, participate_injury=?,"
    " participate_maternity=?, social_location=?, social_ym=?,"
    " medical_location=?, medical_ym=?, base_pension=?, base_unemployment=?,"
    " base_medical=?, base_injury=?, base_maternity=?, salary_account=?,"
    " bank_name=?, social_status=?, medical_status=?, doc_type=?,"
    " stop_date=?, stop_reason=?, status=?, raw_json=? WHERE id=?"
)

_LIST_SQL = "SELECT * FROM province_injury ORDER BY id DESC"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _form_record():
    """从 request.form 收集 province_injury 字段值。

    gender/birthday 留空时由证件号码推导；status 缺省为 'active'。
    """
    id_card = (request.form.get("id_card") or "").strip()
    gender = (request.form.get("gender") or "").strip()
    birthday = (request.form.get("birthday") or "").strip()
    if not gender:
        gender = derive_gender(id_card) or ""
    if not birthday:
        birthday = derive_birthday(id_card) or ""
    record = {
        "name": (request.form.get("name") or "").strip(),
        "id_card": id_card,
        "settlement_unit": (request.form.get("settlement_unit") or "").strip(),
        "contract_start_date": (request.form.get("contract_start_date") or "").strip(),
        "gender": gender,
        "birthday": birthday,
        "ethnicity": (request.form.get("ethnicity") or "").strip(),
        "person_identity": (request.form.get("person_identity") or "").strip(),
        "household_type": (request.form.get("household_type") or "").strip(),
        "phone": (request.form.get("phone") or "").strip(),
        "contract_end": (request.form.get("contract_end") or "").strip(),
        "contract_salary": (request.form.get("contract_salary") or "").strip(),
        "participate_pension": (request.form.get("participate_pension") or "").strip(),
        "participate_unemployment": (request.form.get("participate_unemployment") or "").strip(),
        "participate_medical": (request.form.get("participate_medical") or "").strip(),
        "participate_injury": (request.form.get("participate_injury") or "").strip(),
        "participate_maternity": (request.form.get("participate_maternity") or "").strip(),
        "social_location": (request.form.get("social_location") or "").strip(),
        "social_ym": (request.form.get("social_ym") or "").strip(),
        "medical_location": (request.form.get("medical_location") or "").strip(),
        "medical_ym": (request.form.get("medical_ym") or "").strip(),
        "base_pension": (request.form.get("base_pension") or "").strip(),
        "base_unemployment": (request.form.get("base_unemployment") or "").strip(),
        "base_medical": (request.form.get("base_medical") or "").strip(),
        "base_injury": (request.form.get("base_injury") or "").strip(),
        "base_maternity": (request.form.get("base_maternity") or "").strip(),
        "salary_account": (request.form.get("salary_account") or "").strip(),
        "bank_name": (request.form.get("bank_name") or "").strip(),
        "social_status": (request.form.get("social_status") or "").strip(),
        "medical_status": (request.form.get("medical_status") or "").strip(),
        "doc_type": (request.form.get("doc_type") or "").strip(),
        "stop_date": (request.form.get("stop_date") or "").strip(),
        "stop_reason": (request.form.get("stop_reason") or "").strip(),
        "status": (request.form.get("status") or "active").strip(),
    }
    return record


def _insert_values(record):
    """按 _INSERT_ORDER 组装参数元组。

    缺失字段补空串（导入行无 settlement_unit/stop_date/stop_reason/status）；
    raw_json 已存在（导入行的完整 60 列 JSON）则保留，否则以记录本身生成。
    """
    record = dict(record)
    for key in _INSERT_ORDER:
        record.setdefault(key, "")
    if not record.get("status"):
        record["status"] = "active"
    if not record.get("raw_json"):
        record["raw_json"] = json.dumps(record, ensure_ascii=False)
    return tuple(record[key] for key in _INSERT_ORDER)


def _extract_enroll_rows(path):
    """复用 parser.enroll_parser 的增员模板提取逻辑，返回 (records, errors)。

    与 ``parser.enroll_parser.parse`` 的区别：只做提取与校验，不写
    import_batches / enroll_records —— 省工伤名单独立存 province_injury 表。
    """
    workbook = xlrd.open_workbook(path)
    sheet = workbook.sheet_by_name(ENROLL_INPUT_SHEET)
    datemode = workbook.datemode

    records = []
    errors = []
    for row_idx in range(ENROLL_INPUT_DATA_START_ROW, sheet.nrows):
        excel_row = row_idx + 1
        values = {
            col_name: enroll_parser._cell_at(sheet, row_idx, col_idx, datemode)
            for col_name, col_idx in ENROLL_INPUT_COLUMNS.items()
        }
        if not any(values.values()):
            continue

        name = values["姓名"].strip()
        id_card = values["身份证号码"].strip()
        if not name:
            errors.append({"row": excel_row, "reason": "姓名不能为空"})
            continue
        if not id_card:
            errors.append({"row": excel_row, "reason": "身份证号码不能为空"})
            continue
        if len(id_card) != 18:
            errors.append({"row": excel_row, "reason": "身份证号码必须为18位"})
            continue

        record = {
            field: values[col_name] for field, col_name in _FIELD_COLUMNS.items()
        }
        record["name"] = name
        record["id_card"] = id_card
        record["gender"] = derive_gender(id_card) or ""
        record["birthday"] = derive_birthday(id_card) or ""
        record["raw_json"] = json.dumps(values, ensure_ascii=False)
        records.append(record)
    return records, errors


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
def _parse_filters(args):
    keyword = (args.get("keyword") or "").strip() or None
    reported_raw = (args.get("reported") or "").strip()
    reported = {"1": 1, "0": 0}.get(reported_raw)
    location = (args.get("location") or "").strip() or None
    return dict(keyword=keyword, reported=reported, location=location)


@bp.route("", methods=["GET"])
@auth.require_role(auth.ROLE_SOCIAL, auth.ROLE_ADMIN)
def index():
    rows = [dict(r) for r in db.query_all(_LIST_SQL)]
    add_fields = [f for f in _FORM_FIELDS if f[3] in _ADD_GROUPS]
    filters = _parse_filters(request.args)
    stop_persons = db.list_injury_persons(**filters)
    outputs = db.query_all(
        "SELECT * FROM output_batches WHERE insurance_type = 'injury' ORDER BY id DESC"
    )
    return render_template(
        "province_injury.html",
        rows=rows,
        form_fields=_FORM_FIELDS,
        add_fields=add_fields,
        stop_persons=stop_persons,
        filters=filters,
        outputs=outputs,
    )


@bp.route("/add", methods=["POST"])
@auth.require_role(auth.ROLE_SOCIAL, auth.ROLE_ADMIN)
def add():
    record = _form_record()
    if not record["name"]:
        flash("姓名不能为空", "danger")
        return redirect(url_for("province_injury.index"))
    if not record["id_card"]:
        flash("证件号码不能为空", "danger")
        return redirect(url_for("province_injury.index"))
    db.execute(_INSERT_SQL, _insert_values(record))
    flash(f"已新增人员：{record['name']}", "success")
    return redirect(url_for("province_injury.index"))


@bp.route("/edit/<int:row_id>", methods=["POST"])
@auth.require_role(auth.ROLE_SOCIAL, auth.ROLE_ADMIN)
def edit(row_id):
    existing = db.query_one(
        "SELECT id FROM province_injury WHERE id = ?", (row_id,)
    )
    if existing is None:
        abort(404)
    record = _form_record()
    if not record["name"]:
        flash("姓名不能为空", "danger")
        return redirect(url_for("province_injury.index"))
    if not record["id_card"]:
        flash("证件号码不能为空", "danger")
        return redirect(url_for("province_injury.index"))
    record["raw_json"] = json.dumps(record, ensure_ascii=False)
    db.execute(
        _UPDATE_SQL,
        tuple(record[key] for key in _INSERT_ORDER) + (row_id,),
    )
    flash(f"已更新人员：{record['name']}", "success")
    return redirect(url_for("province_injury.index"))


@bp.route("/delete/<int:row_id>", methods=["POST"])
@auth.require_role(auth.ROLE_SOCIAL, auth.ROLE_ADMIN)
def delete(row_id):
    db.execute("DELETE FROM province_injury WHERE id = ?", (row_id,))
    flash("已删除该人员", "success")
    return redirect(url_for("province_injury.index"))


@bp.route("/import", methods=["POST"])
@auth.require_role(auth.ROLE_SOCIAL, auth.ROLE_ADMIN)
def import_roster():
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("请选择要导入的增员模板 .xls 文件", "danger")
        return redirect(url_for("province_injury.index"))

    filename = secure_filename(file.filename)
    if not filename.lower().endswith((".xls", ".xlsx")):
        flash("仅支持 .xls / .xlsx 文件", "danger")
        return redirect(url_for("province_injury.index"))

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    saved_name = f"{time.strftime('%Y%m%d%H%M%S')}_{filename}"
    path = os.path.join(config.UPLOAD_DIR, saved_name)
    file.save(path)

    try:
        records, errors = _extract_enroll_rows(path)
    except Exception as exc:  # 解析失败（非模板文件等）
        current_app.logger.warning("省工伤导入解析失败: %s", exc)
        flash(f"文件解析失败：{exc}", "danger")
        return redirect(url_for("province_injury.index"))

    inserted = 0
    for record in records:
        db.execute(_INSERT_SQL, _insert_values(record))
        inserted += 1

    message = f"导入完成：成功 {inserted} 条"
    if errors:
        detail = "；".join(
            f"第{e['row']}行 {e['reason']}" for e in errors[:10]
        )
        message += f"；跳过 {len(errors)} 条（{detail}）"
    flash(message, "success" if inserted else "warning")
    return redirect(url_for("province_injury.index"))


@bp.route("/generate", methods=["POST"])
@auth.require_role(auth.ROLE_SOCIAL, auth.ROLE_ADMIN)
def generate():
    """按选中停保人员生成省工伤减员报盘，写入 output_batches + output_records。"""
    from generator import province_injury_reduce

    ids = []
    for value in request.form.getlist("record_ids"):
        value = value.strip()
        if value.isdigit():
            ids.append(int(value))
    ids = list(dict.fromkeys(ids))

    if not ids:
        flash("请至少勾选一名停保人员", "danger")
        return redirect(url_for("province_injury.index"))

    placeholders = ",".join("?" * len(ids))
    already_rows = db.query_all(
        f"SELECT DISTINCT o.record_id FROM output_records o"
        f" JOIN output_batches ob ON ob.id = o.output_id"
        f" WHERE o.record_type = 'injury' AND ob.insurance_type = 'injury'"
        f" AND o.record_id IN ({placeholders})",
        tuple(ids),
    )
    already = {r["record_id"] for r in already_rows}
    fresh_ids = [i for i in ids if i not in already]
    skipped = len(ids) - len(fresh_ids)
    if not fresh_ids:
        flash("所选人员均已生成过工伤减员报盘", "warning")
        return redirect(url_for("province_injury.index"))

    user = auth.current_user()
    username = user["username"] if user else None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"province_injury_reduce_{ts}.xlsx"
    out = os.path.join(config.OUTPUT_DIR, filename)

    try:
        province_injury_reduce.generate(fresh_ids, out=out, generated_by=username)
    except Exception as exc:
        flash(f"生成失败：{exc}", "danger")
        return redirect(url_for("province_injury.index"))

    output_id, _ = db.execute(
        "INSERT INTO output_batches"
        " (batch_id, insurance_type, batch_type, generated_by, filename,"
        "  file_path, status, record_count)"
        " VALUES (NULL, 'injury', 'reduce', ?, ?, ?, 'generated', ?)",
        (username, filename, out, len(fresh_ids)),
    )
    for rid in fresh_ids:
        db.execute(
            "INSERT INTO output_records (output_id, record_id, record_type)"
            " VALUES (?, ?, 'injury')",
            (output_id, rid),
        )

    message = f"已生成省工伤减员报盘，包含 {len(fresh_ids)} 人"
    if skipped:
        message += f"（已跳过 {skipped} 个已报盘记录）"
    flash(message, "success")
    return redirect(url_for("province_injury.index"))


@bp.route("/download/<int:oid>", methods=["GET"])
@auth.require_role(auth.ROLE_SOCIAL, auth.ROLE_ADMIN)
def download(oid):
    """下载已生成的省工伤减员报盘文件（attachment）。"""
    row = db.query_one(
        "SELECT * FROM output_batches WHERE id = ? AND insurance_type = 'injury'",
        (oid,),
    )
    if row is None or not row["file_path"] or not os.path.isfile(row["file_path"]):
        abort(404)
    return send_file(
        row["file_path"],
        as_attachment=True,
        download_name=row["filename"] or os.path.basename(row["file_path"]),
    )