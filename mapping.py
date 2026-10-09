"""mapping.py — 纯函数工具集（stdin 无副作用，仅用标准库）。

提供 T5 工具函数：
- derive_gender       身份证 → 性别
- derive_birthday     身份证 → 出生日期 yyyyMMdd
- yyyymm_to_date      yyyyMM → yyyyMMdd（补 01）
- dash_date_to_yyyymmdd  去横线日期
- to_excel_serial     日期 → Excel 1900 序列号 float
- strip_prefix        取最后一个 '-' 之后的文本

约定：非法输入一律返回 None（strip_prefix 例外，返回原值字符串），永不抛异常。
15 位老身份证视为非法（返回 None）。
"""

from __future__ import annotations

from datetime import datetime

__all__ = [
    "derive_gender",
    "derive_birthday",
    "yyyymm_to_date",
    "dash_date_to_yyyymmdd",
    "to_excel_serial",
    "strip_prefix",
]

# Excel 1900 日期系统的历元（含 1900 闰年 bug 的补偿值）。
_EXCEL_EPOCH = datetime(1899, 12, 30)

_ID_CARD_LENGTH = 18


def _as_text(value):
    """尽力把任意输入转成字符串；None 原样返回以便上层判空。"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:  # pragma: no cover - str() 极少失败，保险起见
        return None


def derive_gender(id_card):
    """18 位身份证第 17 位（index 16）奇偶推导性别：奇=男，偶=女。

    非 18 位 / 非数字第 17 位 / 非身份证证件 → None（绝不抛异常）。
    """
    text = _as_text(id_card)
    if text is None:
        return None
    text = text.strip()
    if len(text) != _ID_CARD_LENGTH:
        return None
    gender_digit = text[16]
    if not gender_digit.isdigit():
        return None
    return "男" if int(gender_digit) % 2 == 1 else "女"


def derive_birthday(id_card):
    """18 位身份证第 7-14 位（index 6:14）推导出生日期 yyyyMMdd。

    非 18 位 / 出生段非 8 位数字 → None。
    """
    text = _as_text(id_card)
    if text is None:
        return None
    text = text.strip()
    if len(text) != _ID_CARD_LENGTH:
        return None
    birthday = text[6:14]
    if len(birthday) != 8 or not birthday.isdigit():
        return None
    return birthday


def yyyymm_to_date(yyyymm):
    """'202006' / 202006 → '20200601'（补 '01'）。非法返回 None。"""
    if yyyymm is None:
        return None
    # 保留前导零：int 转 str；str 原样。
    text = _as_text(yyyymm)
    if text is None:
        return None
    text = text.strip()
    if len(text) != 6 or not text.isdigit():
        return None
    month = int(text[4:6])
    if month < 1 or month > 12:
        return None
    return text + "01"


def dash_date_to_yyyymmdd(s):
    """'2019-03-03' → '20190303'；已紧凑的 '20190303' 原样返回。非法/空 → None。"""
    text = _as_text(s)
    if text is None:
        return None
    compact = text.strip().replace("-", "")
    if len(compact) != 8 or not compact.isdigit():
        return None
    try:
        datetime.strptime(compact, "%Y%m%d")
    except ValueError:
        return None
    return compact


def to_excel_serial(date_str_yyyymmdd):
    """'yyyyMMdd'（容忍 '-' 分隔）→ Excel 1900 序列号 float。

    历元为 datetime(1899, 12, 30)，返回 (date - epoch).days 的浮点值。
    非法输入返回 None。
    """
    compact = dash_date_to_yyyymmdd(date_str_yyyymmdd)
    if compact is None:
        return None
    try:
        day = datetime.strptime(compact, "%Y%m%d")
    except ValueError:
        return None
    return float((day - _EXCEL_EPOCH).days)


def strip_prefix(value):
    """取最后一个 '-' 之后的文本；无 '-' 时返回原值字符串。

    非字符串输入先 str()；保留前导零。输入为 None 时返回 None。
    """
    text = _as_text(value)
    if text is None:
        return None
    if "-" in text:
        return text.rsplit("-", 1)[1]
    return text
