"""SQLite schema + thin data-access layer for SI-Batch.

- No business logic, no seed data (seed data is owned by T4).
- All business rules / mappings / dictionaries live in DB tables so the admin
  backend can configure them at runtime.
- All SQL executed through this module is parameterized.
"""

import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FALLBACK_DATABASE = os.path.join(BASE_DIR, "si_batch.db")


def _database_path():
    """Resolve the SQLite file path, preferring config.py (T1)."""
    try:
        from config import DATABASE  # noqa: F401  (owned by T1)

        path = DATABASE
    except Exception:
        path = FALLBACK_DATABASE
    if not path:
        path = FALLBACK_DATABASE
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    return path


DATABASE = _database_path()


SCHEMA = (
    # ---------------- 用户与权限 ----------------
    """
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    NOT NULL UNIQUE,
        password_hash TEXT    NOT NULL,
        role          TEXT    NOT NULL,
        display_name  TEXT,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
    )
    """,
    # ---------------- 单位信息（社保 / 医保各一套） ----------------
    """
    CREATE TABLE IF NOT EXISTS unit_config (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        insurance_type TEXT   NOT NULL CHECK (insurance_type IN ('social', 'medical')),
        unit_code     TEXT,
        unit_name     TEXT,
        UNIQUE (insurance_type)
    )
    """,
    # ---------------- 减员原因映射 ----------------
    """
    CREATE TABLE IF NOT EXISTS mapping_stop_reason (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        source_reason        TEXT NOT NULL UNIQUE,
        social_stop_reason   TEXT,
        medical_change_reason TEXT
    )
    """,
    # ---------------- 通用字典映射 ----------------
    """
    CREATE TABLE IF NOT EXISTS dict_mapping (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        category     TEXT NOT NULL,
        source_code  TEXT NOT NULL,
        target_value TEXT,
        UNIQUE (category, source_code)
    )
    """,
    # ---------------- 默认值 ----------------
    """
    CREATE TABLE IF NOT EXISTS system_defaults (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        key   TEXT NOT NULL UNIQUE,
        value TEXT
    )
    """,
    # ---------------- 导入批次 ----------------
    """
    CREATE TABLE IF NOT EXISTS import_batches (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_type  TEXT NOT NULL CHECK (batch_type IN ('enroll', 'reduce')),
        filename    TEXT,
        uploaded_by TEXT,
        uploaded_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        total_rows  INTEGER NOT NULL DEFAULT 0,
        status      TEXT NOT NULL DEFAULT 'imported'
    )
    """,
    # ---------------- 增员记录 ----------------
    """
    CREATE TABLE IF NOT EXISTS enroll_records (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id                INTEGER REFERENCES import_batches(id) ON DELETE CASCADE,
        name                    TEXT NOT NULL,
        id_card                 TEXT NOT NULL,
        raw_json                TEXT,
        gender                  TEXT,
        birthday                TEXT,
        ethnicity               TEXT,
        person_identity         TEXT,
        household_type          TEXT,
        phone                   TEXT,
        contract_start          TEXT,
        contract_end            TEXT,
        contract_salary         TEXT,
        participate_pension      TEXT,
        participate_unemployment TEXT,
        participate_medical      TEXT,
        participate_injury       TEXT,
        participate_maternity    TEXT,
        social_location         TEXT,
        social_ym               TEXT,
        medical_location        TEXT,
        medical_ym              TEXT,
        base_pension            TEXT,
        base_unemployment       TEXT,
        base_medical            TEXT,
        base_injury             TEXT,
        base_maternity          TEXT,
        salary_account          TEXT,
        bank_name               TEXT,
        social_status           TEXT,
        medical_status          TEXT,
        doc_type                TEXT
    )
    """,
    # ---------------- 减员记录 ----------------
    """
    CREATE TABLE IF NOT EXISTS reduce_records (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id               INTEGER REFERENCES import_batches(id) ON DELETE CASCADE,
        name                   TEXT NOT NULL,
        id_card                TEXT NOT NULL,
        raw_json               TEXT,
        terminate_date         TEXT,
        social_reduce_ym       TEXT,
        medical_reduce_ym      TEXT,
        injury_reduce_ym       TEXT,
        terminate_reason       TEXT,
        unemployment_benefit   TEXT,
        salary_end_ym          TEXT,
        economic_compensation  TEXT,
        remark                 TEXT,
        social_status          TEXT,
        medical_status         TEXT
    )
    """,
    # ---------------- 省工伤人员信息表（独立维护，按增员模板字段设计） ----------------
    """
    CREATE TABLE IF NOT EXISTS province_injury (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        name                 TEXT NOT NULL,
        id_card              TEXT NOT NULL,
        settlement_unit      TEXT,
        contract_start_date  TEXT,
        gender               TEXT,
        birthday             TEXT,
        ethnicity            TEXT,
        person_identity      TEXT,
        household_type       TEXT,
        phone                TEXT,
        contract_end         TEXT,
        contract_salary      TEXT,
        participate_pension      TEXT,
        participate_unemployment TEXT,
        participate_medical      TEXT,
        participate_injury       TEXT,
        participate_maternity    TEXT,
        social_location      TEXT,
        social_ym            TEXT,
        medical_location     TEXT,
        medical_ym           TEXT,
        base_pension         TEXT,
        base_unemployment    TEXT,
        base_medical         TEXT,
        base_injury          TEXT,
        base_maternity       TEXT,
        salary_account       TEXT,
        bank_name            TEXT,
        social_status        TEXT,
        medical_status       TEXT,
        doc_type             TEXT,
        stop_date            TEXT,
        stop_reason          TEXT,
        status               TEXT NOT NULL DEFAULT 'active',
        raw_json             TEXT
    )
    """,
    # ---------------- 输出报盘批次 ----------------
    """
    CREATE TABLE IF NOT EXISTS output_batches (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id       INTEGER REFERENCES import_batches(id) ON DELETE CASCADE,
        insurance_type TEXT NOT NULL CHECK (insurance_type IN ('social', 'medical')),
        batch_type     TEXT NOT NULL CHECK (batch_type IN ('enroll', 'reduce')),
        generated_by   TEXT,
        generated_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        filename       TEXT,
        file_path      TEXT,
        status         TEXT NOT NULL DEFAULT 'generated'
    )
    """,
)


INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
    "CREATE INDEX IF NOT EXISTS idx_dict_mapping_category ON dict_mapping(category)",
    "CREATE INDEX IF NOT EXISTS idx_import_batches_type ON import_batches(batch_type)",
    "CREATE INDEX IF NOT EXISTS idx_enroll_records_batch ON enroll_records(batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_enroll_records_id_card ON enroll_records(id_card)",
    "CREATE INDEX IF NOT EXISTS idx_enroll_records_medical_loc ON enroll_records(medical_location)",
    "CREATE INDEX IF NOT EXISTS idx_reduce_records_batch ON reduce_records(batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_reduce_records_id_card ON reduce_records(id_card)",
    "CREATE INDEX IF NOT EXISTS idx_province_injury_id_card ON province_injury(id_card)",
    "CREATE INDEX IF NOT EXISTS idx_province_injury_status ON province_injury(status)",
    "CREATE INDEX IF NOT EXISTS idx_output_batches_batch ON output_batches(batch_id)",
)


def get_conn():
    """Open a new connection with Row factory and FK enforcement on."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    """Context manager: auto commit on success, rollback on error."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables and indexes if missing. Idempotent."""
    conn = get_conn()
    try:
        for stmt in SCHEMA:
            conn.execute(stmt)
        for stmt in INDEXES:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()
    return DATABASE


def query_all(sql, params=()):
    """Run a SELECT and return all rows (list of sqlite3.Row)."""
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()


def query_one(sql, params=()):
    """Run a SELECT and return the first row, or None."""
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row
    finally:
        conn.close()


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE.

    Returns (lastrowid, rowcount). Commits before closing.
    """
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        lastrowid = cur.lastrowid
        rowcount = cur.rowcount
        conn.commit()
        cur.close()
        return lastrowid, rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_many(sql, seq_of_params):
    """Run one statement for each parameter tuple. Returns (lastrowid, rowcount)."""
    conn = get_conn()
    try:
        cur = conn.executemany(sql, seq_of_params)
        lastrowid = cur.lastrowid
        rowcount = cur.rowcount
        conn.commit()
        cur.close()
        return lastrowid, rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================================
# Seed data (T4) — business dictionaries / mappings / defaults.
#
# ALL values below are real values extracted from the template files under
# 输入输出/ (增员表「二级代码」/「发放银行」sheets, 增员/减员 sample rows,
# 社保增员「代码」sheet, 社保减员 Sheet2, 医保减员 Sheet2).
#
# dict_mapping.source_code convention: the CODE portion of an input value,
# i.e. the part before the first '-' (e.g. '01-汉族' -> '01',
# '220100000000-吉林省长春市' -> '220100000000'). Full code-prefixed values
# that actually appear in input data columns are seeded as well, so
# generators may look up either form.
#
# Idempotent: every statement uses INSERT OR IGNORE, so re-running
# seed_data() never duplicates or overwrites admin-edited rows.
# =====================================================================

# ---- dict_mapping: ethnicity(民族) — 增员表「二级代码」民族列, 56 值 ----
# code form: '01' -> '汉族' ... '56' -> '基诺族'
# full form: '01-汉族' -> '汉族' ... (as appearing in input data cells)
_ETHNICITY = [
    ("01", "汉族"), ("02", "蒙古族"), ("03", "回族"), ("04", "藏族"),
    ("05", "维吾尔族"), ("06", "苗族"), ("07", "彝族"), ("08", "壮族"),
    ("09", "布依族"), ("10", "朝鲜族"), ("11", "满族"), ("12", "侗族"),
    ("13", "瑶族"), ("14", "白族"), ("15", "土家族"), ("16", "哈尼族"),
    ("17", "哈萨克族"), ("18", "傣族"), ("19", "黎族"), ("20", "傈傈族"),
    ("21", "佤族"), ("22", "畲族"), ("23", "高山族"), ("24", "拉祜族"),
    ("25", "水族"), ("26", "东乡族"), ("27", "纳西族"), ("28", "景颇族"),
    ("29", "柯尔克孜族"), ("30", "土族"), ("31", "达翰尔族"), ("32", "仫佬族"),
    ("33", "羌族"), ("34", "布朗族"), ("35", "撒拉族"), ("36", "毛南族"),
    ("37", "仡佬族"), ("38", "锡伯族"), ("39", "阿昌族"), ("40", "普米族"),
    ("41", "塔吉克族"), ("42", "怒族"), ("43", "乌孜别克族"), ("44", "俄罗斯族"),
    ("45", "鄂温克族"), ("46", "德昂族"), ("47", "保安族"), ("48", "裕固族"),
    ("49", "京族"), ("50", "塔塔尔族"), ("51", "独龙族"), ("52", "鄂伦春族"),
    ("53", "赫哲族"), ("54", "门巴族"), ("55", "珞巴族"), ("56", "基诺族"),
]

# ---- dict_mapping: household(户口性质) ----
# source = 增员表「二级代码」户口性质列 (input dropdown values);
# target = 社保增员「代码」sheet 户口性质列 (output vocabulary).
# code form + full form both seeded; the last full-form row is the value
# that actually appears in the 增员 sample data row (R4).
_HOUSEHOLD = [
    ("10", "非农业户口（城镇）"),
    ("11", "本地非农业户口（本地城镇）"),
    ("12", "外地非农业户口（外地城镇）"),
    ("20", "农业户口（农村）"),
    ("21", "本地农业户口（本地农村）"),
    ("22", "外地农业户口（外地农村）"),
    ("30", "港澳台侨人员"),
    ("40", "外国人"),
    # full form (「二级代码」input values)
    ("10-城镇户口", "非农业户口（城镇）"),
    ("11-本市城镇户口", "本地非农业户口（本地城镇）"),
    ("12-非本市城镇户口", "外地非农业户口（外地城镇）"),
    ("20-农业户口（农村）", "农业户口（农村）"),
    ("21-本市农村户口", "本地农业户口（本地农村）"),
    ("22-非本市农村户口", "外地农业户口（外地农村）"),
    ("30-台港澳人员", "港澳台侨人员"),
    ("40-外籍人士", "外国人"),
    # full form as appearing in the 增员 sample data row R4
    ("11-本地非农业户口（本地城镇）", "本地非农业户口（本地城镇）"),
]

# ---- dict_mapping: person_identity(人员身份) ----
# source = 「二级代码」人员身份列; target = 社保增员「代码」sheet 人员身份列.
_PERSON_IDENTITY = [
    ("91", "职员"),
    ("92", "企业职工"),
    ("91-干部", "职员"),
    ("92-工人", "企业职工"),
]

# ---- dict_mapping: doc_type(证件类型) ----
# 输入列 59 说明: 空=居民身份证(默认); 使用身份证证外的证件填写 9.
# target = 社保增员「代码」sheet 证件类型列 values.
_DOC_TYPE = [
    ("", "居民身份证（户口簿）"),
    ("9", "其他身份证件"),
]

# ---- dict_mapping: location_work_address(属地→工作地址) ----
# source = 「二级代码」户籍所在地 12 位代码 (input 社保/医保参保属地 values
# are '<code>-<名称>'); target = 社保增员「代码」sheet 工作地址列.
_LOCATION_WORK_ADDRESS = [
    ("220100000000", "长春市市本级"),
    ("220200000000", "吉林市市本级"),
    ("220300000000", "四平市市本级"),
    ("220400000000", "辽源市市本级"),
    ("220500000000", "通化市市本级"),
    ("220600000000", "白山市市本级"),
    ("220700000000", "松原市市本级"),
    ("220800000000", "白城市市本级"),
    ("229900000000", "吉林省省本级"),
    # full form (as appearing in input data cells)
    ("220100000000-吉林省长春市", "长春市市本级"),
    ("220200000000-吉林省吉林市", "吉林市市本级"),
    ("220300000000-吉林省四平市", "四平市市本级"),
    ("220400000000-吉林省辽源市", "辽源市市本级"),
    ("220500000000-吉林省通化市", "通化市市本级"),
    ("220600000000-吉林省白山市", "白山市市本级"),
    ("220700000000-吉林省松原市", "松原市市本级"),
    ("220800000000-吉林省白城市", "白城市市本级"),
    ("229900000000-吉林省省直", "吉林省省本级"),
]

# ---- mapping_stop_reason: 合同终止原因 → 社保停保原因 | 医保变更原因 ----
# 16 default rows (plan T4): the 14 codes listed in the plan (01-04, 07-16)
# plus the 减员表 Sheet2 full-text variants of 07/08 (real dictionary values,
# same targets) to reach the planned 16. social_stop_reason values are the
# 9-value dictionary from 单位职工停保模板 Sheet2; medical_change_reason
# uses the 医保减员 Sheet2 value 「在职人员解除/终止劳动合同」(人员中断缴费类).
_MAPPING_STOP_REASON = [
    ("01-在试用期被证明不符合录用条件", "用人单位辞退", "在职人员解除/终止劳动合同"),
    ("02-劳动者被依法追究刑事责任", "人员被判刑收监执行", "在职人员解除/终止劳动合同"),
    ("03-严重违反用人单位规章制度", "用人单位辞退", "在职人员解除/终止劳动合同"),
    ("04-工作调转", "工作关系调转", "在职人员解除/终止劳动合同"),
    ("07-劳动合同到期本人提出", "个人原因解除", "在职人员解除/终止劳动合同"),
    ("08-劳动合同到期单位提出", "用人单位辞退", "在职人员解除/终止劳动合同"),
    ("09-职工个人原因", "个人原因解除", "在职人员解除/终止劳动合同"),
    ("10-用人单位裁员", "用人单位辞退", "在职人员解除/终止劳动合同"),
    ("11-关闭破产", "用人单位辞退", "在职人员解除/终止劳动合同"),
    ("12-改制", "其他原因中断缴费", "在职人员解除/终止劳动合同"),
    ("13-隶属关系转移", "工作关系调转", "在职人员解除/终止劳动合同"),
    ("14-双方协商一致本人解除", "个人原因解除", "在职人员解除/终止劳动合同"),
    ("15-双方协商一致单位解除", "用人单位辞退", "在职人员解除/终止劳动合同"),
    ("16-退休", "人员达到享受养老待遇条件", "在职人员解除/终止劳动合同"),
    # 减员表 Sheet2 full-text variants of 07/08 (same targets as above)
    ("07-劳动合同到期，本人提出解除劳动合同", "个人原因解除", "在职人员解除/终止劳动合同"),
    ("08-劳动合同到期，单位提出解除劳动合同", "用人单位辞退", "在职人员解除/终止劳动合同"),
]

# ---- system_defaults: 默认值 (值均见于模板示例行) ----
_SYSTEM_DEFAULTS = [
    ("婚姻状态", "未说明的婚姻状况"),
    ("健康状况", "健康或良好"),
    ("编制类型", "非在编"),
    ("国籍", "中国"),
    ("农民工标识", "非农民工"),
    ("临时账户标识", "一般账户"),
    ("是否兼职工伤", "否"),
    ("参保身份", "企业职工"),
    ("模板版本", "1.0"),
]

# ---- unit_config: 社保/医保单位信息占位 (admin 后台填写) ----
_UNIT_CONFIG = [
    ("social", None, None),
    ("medical", None, None),
]


def seed_data():
    """Insert business dictionaries / mappings / defaults. Idempotent.

    Calls init_db() first, then INSERT OR IGNORE for every row, so the
    function is safely re-runnable and never overwrites admin edits.
    """
    init_db()

    dict_rows = []
    for code, name in _ETHNICITY:
        dict_rows.append(("ethnicity", code, name))
        dict_rows.append(("ethnicity", f"{code}-{name}", name))
    for code, target in _HOUSEHOLD:
        dict_rows.append(("household", code, target))
    for code, target in _PERSON_IDENTITY:
        dict_rows.append(("person_identity", code, target))
    for code, target in _DOC_TYPE:
        dict_rows.append(("doc_type", code, target))
    for code, target in _LOCATION_WORK_ADDRESS:
        dict_rows.append(("location_work_address", code, target))

    execute_many(
        "INSERT OR IGNORE INTO dict_mapping (category, source_code, target_value) VALUES (?, ?, ?)",
        dict_rows,
    )
    execute_many(
        "INSERT OR IGNORE INTO mapping_stop_reason (source_reason, social_stop_reason, medical_change_reason) VALUES (?, ?, ?)",
        _MAPPING_STOP_REASON,
    )
    execute_many(
        "INSERT OR IGNORE INTO system_defaults (key, value) VALUES (?, ?)",
        _SYSTEM_DEFAULTS,
    )
    execute_many(
        "INSERT OR IGNORE INTO unit_config (insurance_type, unit_code, unit_name) VALUES (?, ?, ?)",
        _UNIT_CONFIG,
    )
    return DATABASE
