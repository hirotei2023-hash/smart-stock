# smart-stock/backend/api/data.py
from fastapi import APIRouter, Query
from backend.engine.data.schema import get_connection

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/stocks")
def list_stocks(search: str = Query("", max_length=20)):
    conn = get_connection()
    if search:
        rows = conn.execute(
            "SELECT ts_code, name, industry FROM stock_basic WHERE ts_code LIKE ? OR name LIKE ? LIMIT 20",
            (f"%{search}%", f"%{search}%")
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT ts_code, name, industry FROM stock_basic LIMIT 300"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/status")
def data_status():
    conn = get_connection()
    stock_count = conn.execute("SELECT COUNT(*) FROM stock_basic").fetchone()[0]
    kline_count = conn.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
    latest_date = conn.execute("SELECT MAX(trade_date) FROM daily_kline").fetchone()[0]
    conn.close()
    return {
        "stocks": stock_count,
        "kline_rows": kline_count,
        "latest_date": latest_date,
    }
