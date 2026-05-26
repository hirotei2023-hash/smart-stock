# smart-stock/backend/api/monitor.py
from fastapi import APIRouter
from pydantic import BaseModel
from backend.engine.data.schema import get_connection
from backend.engine.monitor.triggers import run_all_checks
from backend.engine.monitor.tracker import (add_to_watchlist,
                                             remove_from_watchlist,
                                             get_watchlist)

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


class WatchItem(BaseModel):
    ts_code: str
    name: str = ""


@router.get("/watchlist")
def list_watchlist():
    return get_watchlist()


@router.post("/watchlist")
def add_watch(item: WatchItem):
    add_to_watchlist(item.ts_code, item.name)
    return {"ok": True}


@router.delete("/watchlist/{ts_code}")
def remove_watch(ts_code: str):
    remove_from_watchlist(ts_code)
    return {"ok": True}


@router.get("/check/{ts_code}")
def check_stock(ts_code: str):
    conn = get_connection()
    today = conn.execute(
        "SELECT MAX(trade_date) FROM daily_kline"
    ).fetchone()[0]
    alerts = run_all_checks(conn, ts_code, today)

    for a in alerts:
        conn.execute(
            """INSERT INTO alerts (ts_code, alert_type, severity, message, suggestion)
               VALUES (?, ?, ?, ?, ?)""",
            (ts_code, a["type"], a["severity"], a["message"], a["suggestion"])
        )
    conn.commit()
    conn.close()
    return {"ts_code": ts_code, "date": today, "alerts": alerts}


@router.delete("/alerts")
def clear_alerts():
    conn = get_connection()
    conn.execute("DELETE FROM alerts")
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/alerts")
def get_alerts(limit: int = 50):
    conn = get_connection()
    rows = conn.execute(
        """SELECT a.*, COALESCE(b.name, '') as name
           FROM alerts a LEFT JOIN stock_basic b ON a.ts_code = b.ts_code
           ORDER BY a.triggered_at DESC LIMIT ?""", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/watchlist-check")
def check_all_watched():
    items = get_watchlist()
    all_alerts = {}
    for item in items:
        result = check_stock(item["ts_code"])
        if result["alerts"]:
            all_alerts[item["ts_code"]] = result["alerts"]
    return all_alerts
