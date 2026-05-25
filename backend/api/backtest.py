# smart-stock/backend/api/backtest.py
from fastapi import APIRouter, Query
from backend.engine.data.schema import get_connection
from backend.engine.backtest.stats import signal_accuracy
from backend.engine.backtest.simulator import run_backtest
import pandas as pd

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.get("/signal-stats")
def get_signal_stats(horizon: int = Query(5, ge=1, le=20)):
    conn = get_connection()
    stats = signal_accuracy(conn, horizon)
    conn.close()
    return stats


@router.post("/run")
def execute_backtest(
    start_date: str = "2024-01-01",
    end_date: str = "2026-05-25",
    capital: float = 100000,
    max_positions: int = 5,
    stop_loss: float = -0.08,
):
    conn = get_connection()
    df = pd.read_sql_query(
        """SELECT ts_code, trade_date, composite_score FROM signals
           WHERE trade_date BETWEEN ? AND ? AND composite_score >= 60
           ORDER BY trade_date""",
        conn, params=(start_date, end_date)
    )
    if df.empty:
        conn.close()
        return {"error": "no signals in this date range"}
    result = run_backtest(conn, df, capital, max_positions, stop_loss)
    conn.close()
    return result
