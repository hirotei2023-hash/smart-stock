import sqlite3
from backend.config import DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stock_basic (
    ts_code     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    industry    TEXT,
    market_cap  REAL,
    list_date   TEXT
);

CREATE TABLE IF NOT EXISTS daily_kline (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    open        REAL NOT NULL,
    high        REAL NOT NULL,
    low         REAL NOT NULL,
    close       REAL NOT NULL,
    volume      REAL NOT NULL,
    amount      REAL,
    turnover    REAL,
    pct_chg     REAL,
    UNIQUE(ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS weekly_kline (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    open        REAL NOT NULL,
    high        REAL NOT NULL,
    low         REAL NOT NULL,
    close       REAL NOT NULL,
    volume      REAL NOT NULL,
    amount      REAL,
    turnover    REAL,
    pct_chg     REAL,
    UNIQUE(ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS monthly_kline (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    open        REAL NOT NULL,
    high        REAL NOT NULL,
    low         REAL NOT NULL,
    close       REAL NOT NULL,
    volume      REAL NOT NULL,
    amount      REAL,
    turnover    REAL,
    pct_chg     REAL,
    UNIQUE(ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code         TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    composite_score REAL,
    rule_signals    TEXT,
    confidence      REAL,
    up_5d_prob      REAL,
    up_20d_prob     REAL,
    market_regime   TEXT,
    risk_flags      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS watchlist (
    ts_code     TEXT PRIMARY KEY,
    name        TEXT,
    added_at    TEXT DEFAULT (datetime('now')),
    active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,
    alert_type  TEXT NOT NULL,
    severity    TEXT NOT NULL,
    message     TEXT NOT NULL,
    suggestion  TEXT,
    triggered_at TEXT DEFAULT (datetime('now')),
    resolved    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_kline_code_date ON daily_kline(ts_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_signals_code_date ON signals(ts_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_signals_score ON signals(trade_date, composite_score);
CREATE INDEX IF NOT EXISTS idx_alerts_ts_code ON alerts(ts_code, triggered_at);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
