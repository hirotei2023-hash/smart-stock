# smart-stock/backend/engine/monitor/triggers.py
import pandas as pd
from backend.engine.data.schema import get_connection
from backend.engine.pattern.indicators import calc_ma, calc_macd, calc_kdj, calc_volume_ma


def check_ma_break(conn, ts_code: str, trade_date: str) -> dict | None:
    df = pd.read_sql_query(
        "SELECT * FROM daily_kline WHERE ts_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 60",
        conn, params=(ts_code, trade_date)
    )
    if len(df) < 20:
        return None

    df = calc_ma(df.sort_values("trade_date"))
    latest = df.iloc[-1]
    alerts = []
    for p in [5, 10, 20, 60]:
        ma_col = f"ma_{p}"
        if ma_col in df.columns:
            prev = df[ma_col].iloc[-2]
            cur = df[ma_col].iloc[-1]
            if latest["close"] < cur and prev >= df[ma_col].iloc[-2]:
                alerts.append({
                    "type": "ma_break",
                    "severity": "danger" if p >= 20 else "warning",
                    "message": f"跌破 {p} 日均线 ({cur:.2f})",
                    "suggestion": f"建议减仓 {'50%' if p >= 20 else '30%'}，关注 {p} 日线能否收复",
                })
    return alerts[0] if alerts else None


def check_volume_drop(conn, ts_code: str, trade_date: str) -> dict | None:
    df = pd.read_sql_query(
        "SELECT * FROM daily_kline WHERE ts_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 25",
        conn, params=(ts_code, trade_date)
    )
    if len(df) < 21:
        return None

    df = calc_volume_ma(df.sort_values("trade_date"))
    latest = df.iloc[-1]
    if latest["pct_chg"] is not None and latest["pct_chg"] < -3:
        if latest["volume_ratio"] > 2.0:
            return {
                "type": "volume_drop",
                "severity": "danger",
                "message": f"放量下跌 {latest['pct_chg']}%，量比 {latest['volume_ratio']:.1f}",
                "suggestion": "放量下跌信号明确，建议减仓 50% 或清仓观望",
            }
    return None


def check_macd_kdj_death_cross(conn, ts_code: str, trade_date: str) -> dict | None:
    df = pd.read_sql_query(
        "SELECT * FROM daily_kline WHERE ts_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 60",
        conn, params=(ts_code, trade_date)
    )
    if len(df) < 30:
        return None

    df = calc_macd(df.sort_values("trade_date"))
    df = calc_kdj(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    macd_cross = (prev["macd_dif"] >= prev["macd_dea"] and
                  latest["macd_dif"] < latest["macd_dea"])
    kdj_cross = (prev["kdj_k"] >= prev["kdj_d"] and
                 latest["kdj_k"] < latest["kdj_d"])

    if macd_cross or kdj_cross:
        crosses = []
        if macd_cross:
            crosses.append("MACD")
        if kdj_cross:
            crosses.append("KDJ")
        return {
            "type": "death_cross",
            "severity": "warning",
            "message": f"{'/'.join(crosses)} 死叉",
            "suggestion": "指标转弱，建议缩小仓位或设置更紧的止损",
        }
    return None


def check_pattern_breakdown(conn, ts_code: str, trade_date: str) -> dict | None:
    df = pd.read_sql_query(
        "SELECT * FROM daily_kline WHERE ts_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 25",
        conn, params=(ts_code, trade_date)
    )
    if len(df) < 21:
        return None

    low_20 = df["low"].iloc[1:21].min()
    if df["close"].iloc[0] < low_20:
        return {
            "type": "pattern_breakdown",
            "severity": "danger",
            "message": f"跌破 20 日最低点 {low_20:.2f}",
            "suggestion": "形态破位，建议清仓",
        }
    return None


def run_all_checks(conn, ts_code: str, trade_date: str) -> list[dict]:
    checks = [
        check_ma_break, check_volume_drop,
        check_macd_kdj_death_cross, check_pattern_breakdown,
    ]
    results = []
    for check in checks:
        r = check(conn, ts_code, trade_date)
        if r:
            results.append(r)
    return results
