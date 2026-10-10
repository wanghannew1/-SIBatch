"""T11 — 医保增员报盘生成器（001 批量职工新参保(增员).xls，Sheet1 17 列，省/市拆分）。

列名取自 columns.MEDICAL_ENROLL_OUTPUT_HEADERS（与模板逐字节一致），
表头写在第 0 行，数据从第 1 行开始（xlwt 全新工作簿，不复制模板示例行）。

按医保参保属地拆成两个独立文件：
  - 属地代码（第一个 '-' 之前）以 '2299' 开头 → 省直 → 省医保增员.xls
  - 其余（如 '2201' 长春市）                        → 市医保增员.xls
只输出有数据的侧；返回 {"province": path, "city": path}（仅有数据的侧）。

写入类型（关键）：
  - 出生日期/首次参加工作日期/本次参保时间 = Excel 序列号 float（NUMBER 单元格）
  - 证件号码/居住地邮政编码/手机号码 = TEXT（'@' 数字格式，防科学计数/精度丢失）
  - 本次参保时间：省医保 = 合同开始时间；市医保 = 医保参保年月 + '01'

字典/默认值全部读库（dict_mapping / system_defaults），业务规则函数取自 mapping.py。
generated_by 目前未使用，仅保留在签名中以兼容调用方接口。
"""

import json
import os

import xlwt

import columns
import db
from mapping import (
    dash_date_to_yyyymmdd,
    derive_birthday,
    derive_gender,
    strip_prefix,
    to_excel_serial,
    yyyymm_to_date,
)

_PROVINCE_FILE = "省医保增员.xls"
_CITY_FILE = "市医保增员.xls"
_PROVINCE_CODE_PREFIX = "2299"

_TEXT_COLUMNS = frozenset(
    {
        columns.MEDICAL_ENROLL_OUTPUT_COLUMNS["证件号码"],
        columns.MEDICAL_ENROLL_OUTPUT_COLUMNS["居住地邮政编码"],
        columns.MEDICAL_ENROLL_OUTPUT_COLUMNS["手机号码"],
    }
)

_DEFAULT_STYLE = xlwt.easyxf()
_TEXT_STYLE = xlwt.easyxf(num_format_str="@")


def _load_dict():
    rows = db.query_all("SELECT category, source_code, target_value FROM dict_mapping")
    return {(r["category"], r["source_code"]): r["target_value"] for r in rows}


def _load_defaults():
    rows = db.query_all("SELECT key, value FROM system_defaults")
    return {r["key"]: r["value"] for r in rows}


def _lookup(mapping, category, *keys):
    for key in keys:
        if key is None:
            continue
        value = mapping.get((category, key))
        if value:
            return value
    return None


def _code_prefix(value):
    text = "" if value is None else str(value)
    if "-" in text:
        return text.split("-", 1)[0].strip()
    return text.strip()


def _json_field(raw_json, key):
    if not raw_json:
        return ""
    try:
        data = json.loads(raw_json)
    except (TypeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    value = data.get(key, "")
    return "" if value is None else str(value)


def _salary(value):
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return float(text)
    except ValueError:
        return text


def _record_values(record, mapping, defaults, is_province):
    household_type = record["household_type"]
    doc_type = record["doc_type"]
    contract_start = dash_date_to_yyyymmdd(record["contract_start"])
    enroll_date = contract_start if is_province else yyyymm_to_date(record["medical_ym"])
    return (
        _lookup(mapping, "doc_type", doc_type) or "",
        record["id_card"],
        record["name"],
        derive_gender(record["id_card"]) or "",
        strip_prefix(record["ethnicity"]) or "",
        to_excel_serial(derive_birthday(record["id_card"])),
        to_excel_serial(contract_start),
        _lookup(mapping, "household", _code_prefix(household_type), household_type) or "",
        defaults.get("婚姻状态") or "",
        defaults.get("健康状况") or "",
        _json_field(record["raw_json"], "地址"),
        _json_field(record["raw_json"], "邮政编码"),
        "",
        record["phone"],
        _salary(record["contract_salary"]),
        defaults.get("编制类型") or "",
        to_excel_serial(enroll_date),
    )


def _write_workbook(path, rows, mapping, defaults, is_province):
    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet(columns.MEDICAL_ENROLL_OUTPUT_SHEET)
    for col_idx, header in enumerate(columns.MEDICAL_ENROLL_OUTPUT_HEADERS):
        ws.write(0, col_idx, header, _DEFAULT_STYLE)
    start = columns.MEDICAL_ENROLL_OUTPUT_DATA_START_ROW
    for offset, record in enumerate(rows):
        values = _record_values(record, mapping, defaults, is_province)
        for col_idx, value in enumerate(values):
            style = _TEXT_STYLE if col_idx in _TEXT_COLUMNS else _DEFAULT_STYLE
            ws.write(start + offset, col_idx, "" if value is None else value, style)
    wb.save(path)


def generate(batch_id, out_dir, *, generated_by=None):
    """生成医保增员报盘（省/市两个 .xls），返回写出的文件路径字典。

    只取 medical_location 非空的 enroll_records；按属地代码前缀拆分：
    2299…（省直）→ 省医保增员.xls，其余（2201…等）→ 市医保增员.xls。
    只写出有数据的侧，返回形如 {"province": "<path>", "city": "<path>"}。
    """
    mapping = _load_dict()
    defaults = _load_defaults()

    records = db.query_all(
        "SELECT * FROM enroll_records WHERE batch_id = ?"
        " AND medical_location IS NOT NULL AND TRIM(medical_location) <> ''",
        (batch_id,),
    )

    province_rows = []
    city_rows = []
    for record in records:
        if _code_prefix(record["medical_location"]).startswith(_PROVINCE_CODE_PREFIX):
            province_rows.append(record)
        else:
            city_rows.append(record)

    os.makedirs(out_dir, exist_ok=True)
    written = {}
    for key, rows, filename, is_province in (
        ("province", province_rows, _PROVINCE_FILE, True),
        ("city", city_rows, _CITY_FILE, False),
    ):
        if not rows:
            continue
        path = os.path.join(out_dir, filename)
        _write_workbook(path, rows, mapping, defaults, is_province)
        written[key] = os.path.abspath(path)
    return written
