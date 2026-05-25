# smart-stock/backend/engine/backtest/stats.py
import pandas as pd
from backend.engine.data.schema import get_connection


def signal_accuracy(conn, horizon_days: int = 5) -> dict:
    query = """
    SELECT s.ts_code, s.trade_date as signal_date, s.composite_score,
           s.up_5d_prob, s.up_20d_prob,
           k5.close as close_5d, k20.close as close_20d,
           k0.close as close_0
    FROM signals s
    JOIN daily_kline k0 ON s.ts_code=k0.ts_code AND s.trade_date=k0.trade_date
    LEFT JOIN daily_kline k5 ON s.ts_code=k5.ts_code
      AND k5.trade_date = (SELECT trade_date FROM daily_kline
                           WHERE ts_code=s.ts_code AND trade_date>s.trade_date
                           ORDER BY trade_date LIMIT 1 OFFSET ?)
    LEFT JOIN daily_kline k20 ON s.ts_code=k20.ts_code
      AND k20.trade_date = (SELECT trade_date FROM daily_kline
                            WHERE ts_code=s.ts_code AND trade_date>s.trade_date
                            ORDER BY trade_date LIMIT 1 OFFSET ?)
    WHERE k5.close IS NOT NULL
    """
    df = pd.read_sql_query(query, conn, params=(horizon_days - 1, 19))

    if df.empty:
        return {"error": "no signals found"}

    df["ret_5d"] = df["close_5d"] / df["close_0"] - 1
    df["ret_20d"] = df["close_20d"] / df["close_0"] - 1

    win_5d = (df["ret_5d"] > 0).sum()
    win_20d = (df["ret_20d"] > 0).sum()
    total = len(df)

    return {
        "total_signals": total,
        "win_rate_5d": round(win_5d / total, 4),
        "win_rate_20d": round(win_20d / total, 4),
        "avg_return_5d": round(float(df["ret_5d"].mean()), 4),
        "avg_return_20d": round(float(df["ret_20d"].mean()), 4),
        "best_5d": round(float(df["ret_5d"].max()), 4),
        "worst_5d": round(float(df["ret_5d"].min()), 4),
        "high_score_win_rate": round(
            float((df[df["composite_score"] >= 80]["ret_5d"] > 0).mean()), 4
        ) if len(df[df["composite_score"] >= 80]) > 0 else 0,
    }
