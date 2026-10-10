"""generator/medical_reduce.py — T12 医保减员报盘生成器（.xls 3 列，省/市拆分）。

输出「批量减员申报(减员).xls」的医保部分：Sheet1 表头 3 列（0-based 行 0），
数据自 0-based 行 1。列：姓名 / 证件类型 / 证件号码 —— 不追加合同终止原因列。

按医保参保属地拆分为 省医保减员.xls 与 市医保减员.xls 两个文件。
reduce_records 无 medical_location 列：按 id_card 回查 enroll_records
（取 id 最大的一条）的 medical_location 判定属地 ——
属地代码（首个 '-' 之前）以 '2299' 开头 → 省医保减员.xls；
否则（含查不到参保记录）→ 市医保减员.xls。
"""

from __future__ import annotations

import os

import xlwt

from columns import (
    MEDICAL_REDUCE_OUTPUT_SHEET,
    MEDICAL_REDUCE_OUTPUT_HEADER_ROW,
    MEDICAL_REDUCE_OUTPUT_DATA_START_ROW,
    MEDICAL_REDUCE_OUTPUT_HEADERS,
)
from db import query_all, query_one

PROVINCE_FILENAME = "省医保减员.xls"
CITY_FILENAME = "市医保减员.xls"

_PROVINCE_LOCATION_PREFIX = "2299"

_DEFAULT_DOC_TYPE = "居民身份证（户口簿）"

_SELECT_RECORDS = (
    "SELECT * FROM reduce_records WHERE batch_id = ? AND medical_reduce_ym IS NOT NULL"
    " AND TRIM(medical_reduce_ym) <> '' ORDER BY id"
)

_SELECT_LOCATION = (
    "SELECT medical_location FROM enroll_records WHERE id_card = ?"
    " ORDER BY id DESC LIMIT 1"
)

_SELECT_DOC_TYPE = (
    "SELECT target_value FROM dict_mapping"
    " WHERE category = 'doc_type' AND source_code = ?"
)


def _doc_type():
    """证件类型：reduce_records 无 doc_type 列，按输入约定取空值映射
    （'' → 居民身份证（户口簿））；字典缺失时回退默认值。"""
    row = query_one(_SELECT_DOC_TYPE, ("",))
    if row is not None and row["target_value"]:
        return row["target_value"]
    return _DEFAULT_DOC_TYPE


def _is_province(location):
    """医保参保属地是否省直：属地代码（首个 '-' 之前）以 '2299' 开头。"""
    if not location:
        return False
    code = str(location).split("-", 1)[0]
    return code.startswith(_PROVINCE_LOCATION_PREFIX)


def generate(batch_id, out_dir, *, generated_by=None):
    """生成省/市医保减员报盘 .xls，返回写入文件路径。

    batch_id      — import_batches.id（减员批次）
    out_dir       — 输出目录（不存在时自动创建）
    generated_by  — 生成人（保留参数，供调用方记录）

    返回 {"province": 省医保减员.xls 路径, "city": 市医保减员.xls 路径}。
    """
    rows = query_all(_SELECT_RECORDS, (batch_id,))
    doc_type = _doc_type()

    province_rows = []
    city_rows = []
    for row in rows:
        location = None
        enroll = query_one(_SELECT_LOCATION, (row["id_card"],))
        if enroll is not None:
            location = enroll["medical_location"]
        if _is_province(location):
            province_rows.append(row)
        else:
            city_rows.append(row)

    os.makedirs(out_dir, exist_ok=True)

    def _write(filename, record_rows):
        wb = xlwt.Workbook()
        ws = wb.add_sheet(MEDICAL_REDUCE_OUTPUT_SHEET)
        for col_idx, name in enumerate(MEDICAL_REDUCE_OUTPUT_HEADERS):
            ws.write(MEDICAL_REDUCE_OUTPUT_HEADER_ROW, col_idx, name)
        for offset, record in enumerate(record_rows):
            r = MEDICAL_REDUCE_OUTPUT_DATA_START_ROW + offset
            ws.write(r, 0, record["name"] or "")
            ws.write(r, 1, doc_type)
            ws.write(r, 2, str(record["id_card"] or ""))
        path = os.path.join(out_dir, filename)
        wb.save(path)
        return path

    return {
        "province": _write(PROVINCE_FILENAME, province_rows),
        "city": _write(CITY_FILENAME, city_rows),
    }
