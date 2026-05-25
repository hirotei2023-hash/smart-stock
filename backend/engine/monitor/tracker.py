# smart-stock/backend/engine/monitor/tracker.py
from backend.engine.data.schema import get_connection


def add_to_watchlist(ts_code: str, name: str = ""):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO watchlist (ts_code, name) VALUES (?, ?)",
        (ts_code, name)
    )
    conn.commit()
    conn.close()


def remove_from_watchlist(ts_code: str):
    conn = get_connection()
    conn.execute("UPDATE watchlist SET active=0 WHERE ts_code=?", (ts_code,))
    conn.commit()
    conn.close()


def get_watchlist() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT ts_code, name FROM watchlist WHERE active=1"
    ).fetchall()
    conn.close()
    return [{"ts_code": r["ts_code"], "name": r["name"]} for r in rows]
