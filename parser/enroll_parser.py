"""parser/enroll_parser.py — 增员表（合同批量导入模板）解析器。

读取 60 列 .xls 增员模板（Sheet1，数据从 0-based row 4 开始），按列名
（columns.ENROLL_INPUT_COLUMNS）提取 enroll_records 字段，校验必录项后
入库（import_batches + enroll_records），返回结构化结果。

文本保真：身份证号码 / 工资账号等一律按文本处理；整数数值转为整数字符串，
绝不使用科学计数法、绝不转数字。性别/出生日期由身份证推导（mapping）。
"""

import json
import os

import xlrd

from columns import (
    ENROLL_INPUT_COLUMNS,
    ENROLL_INPUT_DATA_START_ROW,
    ENROLL_INPUT_SHEET,
)
from db import current_person_state, execute
from mapping import derive_birthday, derive_gender

# enroll_records 列名 -> 增员模板列名（gender/birthday 由身份证推导，无对应列）
_FIELD_COLUMNS = {
    "name": "姓名",
    "id_card": "身份证号码",
    "ethnicity": "民族",
    "person_identity": "人员身份",
    "household_type": "户口性质",
    "phone": "联系电话",
    "contract_start": "合同开始时间",
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

# INSERT 参数顺序（不含 batch_id，由调用方前置）
_RECORD_PARAMS = (
    "name", "id_card", "raw_json", "gender", "birthday", "ethnicity",
    "person_identity", "household_type", "phone", "contract_start",
    "contract_end", "contract_salary", "participate_pension",
    "participate_unemployment", "participate_medical", "participate_injury",
    "participate_maternity", "social_location", "social_ym",
    "medical_location", "medical_ym", "base_pension", "base_unemployment",
    "base_medical", "base_injury", "base_maternity", "salary_account",
    "bank_name", "social_status", "medical_status", "doc_type",
)

_INSERT_BATCH = (
    "INSERT INTO import_batches"
    " (batch_type, filename, uploaded_by, total_rows, status, stored_name)"
    " VALUES ('enroll', ?, ?, ?, 'imported', ?)"
)

_INSERT_RECORD = (
    "INSERT INTO enroll_records ("
    "batch_id, name, id_card, raw_json, gender, birthday, ethnicity,"
    " person_identity, household_type, phone, contract_start, contract_end,"
    " contract_salary, participate_pension, participate_unemployment,"
    " participate_medical, participate_injury, participate_maternity,"
    " social_location, social_ym, medical_location, medical_ym,"
    " base_pension, base_unemployment, base_medical, base_injury,"
    " base_maternity, salary_account, bank_name, social_status,"
    " medical_status, doc_type"
    ") VALUES ("
    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
    " ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
    ")"
)


def _cell_at(sheet, row_idx, col_idx, datemode):
    """取单元格文本；稀疏行中未写入的单元格（xlrd 抛 IndexError）按空处理。"""
    try:
        cell = sheet.cell(row_idx, col_idx)
    except IndexError:
        return ""
    return _cell_text(cell, datemode)


def _cell_text(cell, datemode):
    """xlrd cell -> 文本。TEXT 原样；NUMBER 整数转整数字符串（防科学计数）；
    DATE 经 xldate 转 yyyy-mm-dd；其余（空/布尔/错误）返回 ''。"""
    ctype = cell.ctype
    if ctype == xlrd.XL_CELL_TEXT:
        return cell.value
    if ctype == xlrd.XL_CELL_NUMBER:
        value = cell.value
        if value == int(value):
            return str(int(value))
        return str(value)
    if ctype == xlrd.XL_CELL_DATE:
        dt = xlrd.xldate.xldate_as_datetime(cell.value, datemode)
        return dt.strftime("%Y-%m-%d")
    return ""


def parse(path, *, filename=None, uploaded_by=None):
    """解析增员 .xls 模板，校验必录项并入库。

    返回 {"batch_id": int, "records": [...], "success_count": int,
          "errors": [{"row": <1-based excel row>, "reason": str}]}。
    每条 record 的键与 enroll_records 表列一致，另含 raw_json（完整 60 列
    按列名键控的 JSON 字符串）。
    """
    workbook = xlrd.open_workbook(path)
    sheet = workbook.sheet_by_name(ENROLL_INPUT_SHEET)
    datemode = workbook.datemode

    if filename is None:
        filename = os.path.basename(path)

    records = []
    errors = []

    for row_idx in range(ENROLL_INPUT_DATA_START_ROW, sheet.nrows):
        excel_row = row_idx + 1
        values = {
            col_name: _cell_at(sheet, row_idx, col_idx, datemode)
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

        record = {field: values[col_name] for field, col_name in _FIELD_COLUMNS.items()}
        record["name"] = name
        record["id_card"] = id_card
        record["gender"] = derive_gender(id_card) or ""
        record["birthday"] = derive_birthday(id_card) or ""
        record["raw_json"] = json.dumps(values, ensure_ascii=False)
        records.append(record)

    seen = set()
    duplicates = []
    final_records = []
    for record in records:
        id_card = record["id_card"]
        if id_card in seen or current_person_state(id_card) == "enrolled":
            duplicates.append(
                {
                    "name": record["name"],
                    "id_card": id_card,
                    "reason": "重复增员：该人员当前已在册",
                }
            )
            continue
        seen.add(id_card)
        final_records.append(record)
    records = final_records

    batch_id, _ = execute(
        _INSERT_BATCH,
        (filename, uploaded_by, len(records), os.path.basename(path)),
    )

    for record in records:
        record["batch_id"] = batch_id
        record_id, _ = execute(
            _INSERT_RECORD,
            (batch_id,) + tuple(record[key] for key in _RECORD_PARAMS),
        )
        record["id"] = record_id

    return {
        "batch_id": batch_id,
        "records": records,
        "success_count": len(records),
        "errors": errors,
        "duplicates": duplicates,
    }
