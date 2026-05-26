# smart-stock/backend/api/backtest.py
from fastapi import APIRouter, Query
from pydantic import BaseModel
from backend.engine.data.schema import get_connection
from backend.engine.backtest.stats import signal_accuracy
from backend.engine.backtest.simulator import run_backtest, run_backtest_v2
import pandas as pd

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    start_date: str = "2026-01-01"
    end_date: str = "2026-05-25"
    capital: float = 100000
    max_positions: int = 5
    stop_loss: float = -0.08      # 止损: 从入场价下跌超过此比例卖出, e.g. -0.08 = -8%
    trailing_stop: float = 0.05   # 回撤止盈: 从最高点回撤超过此比例卖出, e.g. 0.05 = 5%
    version: str = "v1"           # "v1" or "v2"


@router.get("/signal-stats")
def get_signal_stats(horizon: int = Query(5, ge=1, le=20)):
    conn = get_connection()
    stats = signal_accuracy(conn, horizon)
    conn.close()
    return stats


@router.post("/run")
def execute_backtest(req: BacktestRequest):
    conn = get_connection()
    df = pd.read_sql_query(
        """SELECT ts_code, trade_date, composite_score FROM signals
           WHERE trade_date BETWEEN ? AND ? AND composite_score >= 50
           ORDER BY trade_date""",
        conn, params=(req.start_date, req.end_date)
    )
    if df.empty:
        conn.close()
        return {"error": "no signals in this date range"}

    if req.version == "v2":
        result = run_backtest_v2(conn, df, req.capital, req.max_positions,
                                 req.stop_loss, req.trailing_stop)
    else:
        result = run_backtest(conn, df, req.capital, req.max_positions,
                              req.stop_loss, req.trailing_stop)

    # 补充股票名称
    codes = set(t["ts_code"] for t in result["trades"])
    if codes:
        names = dict(conn.execute(
            f"SELECT ts_code, name FROM stock_basic WHERE ts_code IN ({','.join('?' * len(codes))})",
            tuple(codes)
        ).fetchall())
        for t in result["trades"]:
            t["name"] = names.get(t["ts_code"], "")

    conn.close()
    return result
