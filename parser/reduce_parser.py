"""parser/reduce_parser.py — 减员表（合同解除批量导入模板）解析器。

读取 16 列 .xls 减员模板（Sheet1，数据从 0-based row 4 开始），按列名
（columns.REDUCE_INPUT_COLUMNS）提取 reduce_records 字段，校验必录项后
入库（import_batches + reduce_records），返回结构化结果。

文本保真：身份证号码一律按文本处理；整数数值转为整数字符串，绝不使用
科学计数法、绝不转数字。公积金报减年月（col5）不参与字段提取（公积金
out of scope），仅保留在 raw_json 中。
"""

import json
import os

import xlrd

from columns import (
    REDUCE_INPUT_COLUMNS,
    REDUCE_INPUT_DATA_START_ROW,
    REDUCE_INPUT_SHEET,
)
from db import execute

# reduce_records 列名 -> 减员模板列名
_FIELD_COLUMNS = {
    "name": "姓名",
    "id_card": "身份证号码",
    "terminate_date": "合同终止日期",
    "social_reduce_ym": "社保报减年月\n(不减社保不用填写)",
    "medical_reduce_ym": "医保报减年月\n(不减医保不用填写)",
    "injury_reduce_ym": "工伤报减年月\n(不减工伤不用填写)",
    "terminate_reason": "合同终止原因",
    "unemployment_benefit": "是否享受失业金",
    "salary_end_ym": "工资结束年月（填几月发放到几月）",
    "economic_compensation": "是否经济赔偿",
    "remark": "备注",
    "social_status": "社保参保状态",
    "medical_status": "医保参保状态",
}

# INSERT 参数顺序（不含 batch_id，由调用方前置）
_RECORD_PARAMS = (
    "name", "id_card", "raw_json", "terminate_date", "social_reduce_ym",
    "medical_reduce_ym", "injury_reduce_ym", "terminate_reason",
    "unemployment_benefit", "salary_end_ym", "economic_compensation",
    "remark", "social_status", "medical_status",
)

_INSERT_BATCH = (
    "INSERT INTO import_batches (batch_type, filename, uploaded_by, total_rows, status)"
    " VALUES ('reduce', ?, ?, ?, 'imported')"
)

_INSERT_RECORD = (
    "INSERT INTO reduce_records ("
    "batch_id, name, id_card, raw_json, terminate_date, social_reduce_ym,"
    " medical_reduce_ym, injury_reduce_ym, terminate_reason,"
    " unemployment_benefit, salary_end_ym, economic_compensation,"
    " remark, social_status, medical_status"
    ") VALUES ("
    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
    ")"
)


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
    """解析减员 .xls 模板，校验必录项并入库。

    返回 {"batch_id": int, "records": [...], "success_count": int,
           "errors": [{"row": <1-based excel row>, "reason": str}]}。
    每条 record 的键与 reduce_records 表列一致，另含 raw_json（完整 16 列
    按列名键控的 JSON 字符串）。
    """
    workbook = xlrd.open_workbook(path)
    sheet = workbook.sheet_by_name(REDUCE_INPUT_SHEET)
    datemode = workbook.datemode

    if filename is None:
        filename = os.path.basename(path)

    records = []
    errors = []

    for row_idx in range(REDUCE_INPUT_DATA_START_ROW, sheet.nrows):
        excel_row = row_idx + 1
        values = {
            col_name: _cell_text(sheet.cell(row_idx, col_idx), datemode)
            for col_name, col_idx in REDUCE_INPUT_COLUMNS.items()
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

        record = {field: values[col_name] for field, col_name in _FIELD_COLUMNS.items()}
        record["name"] = name
        record["id_card"] = id_card
        record["raw_json"] = json.dumps(values, ensure_ascii=False)
        records.append(record)

    batch_id, _ = execute(_INSERT_BATCH, (filename, uploaded_by, len(records)))

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
    }
