# smart-stock/backend/api/signals.py
from fastapi import APIRouter, Query
from backend.engine.data.schema import get_connection

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/dates")
def get_signal_dates():
    """返回有信号的日期列表（供前端日期选择器）"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT trade_date FROM signals ORDER BY trade_date DESC"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


@router.get("/today")
def get_today_signals(limit: int = Query(50, ge=1, le=200),
                       min_score: float = Query(50, ge=0, le=100),
                       date: str = Query(None)):
    conn = get_connection()
    if date is None:
        date = conn.execute("SELECT MAX(trade_date) FROM signals").fetchone()[0]
    rows = conn.execute(
        """SELECT s.*, b.name FROM signals s
           JOIN stock_basic b ON s.ts_code=b.ts_code
           WHERE s.trade_date=? AND s.composite_score >= ?
           ORDER BY s.composite_score DESC LIMIT ?""",
        (date, min_score, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/{ts_code}")
def get_stock_signals(ts_code: str, days: int = Query(90, ge=1, le=365)):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM signals WHERE ts_code=? ORDER BY trade_date DESC LIMIT ?",
        (ts_code, days)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/kline/{ts_code}")
def get_kline(ts_code: str, days: int = Query(120, ge=1, le=500)):
    conn = get_connection()
    rows = conn.execute(
        """SELECT trade_date, open, high, low, close, volume, turnover, pct_chg
           FROM daily_kline WHERE ts_code=?
           ORDER BY trade_date DESC LIMIT ?""",
        (ts_code, days)
    ).fetchall()
    conn.close()
    return sorted([dict(r) for r in rows], key=lambda x: x["trade_date"])


@router.get("/summary/today")
def get_today_summary(date: str = Query(None)):
    conn = get_connection()
    if date is None:
        date = conn.execute("SELECT MAX(trade_date) FROM signals").fetchone()[0]
    avg_score = conn.execute(
        "SELECT AVG(composite_score) FROM signals WHERE trade_date=?",
        (date,)
    ).fetchone()[0]
    high_count = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE trade_date=? AND composite_score>=80",
        (date,)
    ).fetchone()[0]
    total = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE trade_date=?", (date,)
    ).fetchone()[0]
    alert_count = conn.execute(
        "SELECT COUNT(*) FROM alerts WHERE resolved=0"
    ).fetchone()[0]
    conn.close()
    return {
        "date": date,
        "avg_score": round(avg_score or 0, 1),
        "high_signal_count": high_count,
        "total_signals": total,
        "active_alerts": alert_count,
    }
