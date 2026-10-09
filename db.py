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
