"""综合评分: 量价60% + 股性40%，ST 过滤"""
import json
import numpy as np
import pandas as pd

from backend.engine.scoring.volume_price import compute_volume_price_score, get_latest_signal_detail
from backend.engine.scoring.character import (
    compute_limit_up_counts, compute_character_score, build_rank_maps,
)


def scan_all_stocks(conn, date: str = None) -> list[dict]:
    """全市场扫描：对每只股票计算量价+股性评分（单轮读取，合并两次查询）。
    返回: 综合评分 >= 50 的信号列表，按 score 降序
    """
    if date is None:
        date = conn.execute("SELECT MAX(trade_date) FROM daily_kline").fetchone()[0]

    stocks = conn.execute(
        "SELECT ts_code, name FROM stock_basic"
    ).fetchall()

    # 排除 ST 股票
    active_stocks = [
        (ts_code, name) for ts_code, name in stocks
        if "ST" not in (name or "").upper() and "*ST" not in (name or "").upper()
    ]

    results = []
    all_lu_counts = []
    total = len(active_stocks)
    scanned = 0

    for ts_code, name in active_stocks:
        scanned += 1
        if scanned % 200 == 0:
            print(f"  [{scanned}/{total}] scanning...")

        # 一次读取所有需要的列，裁剪到目标日期
        df = pd.read_sql_query(
            "SELECT trade_date, close, volume, pct_chg FROM daily_kline "
            "WHERE ts_code=? AND trade_date <= ? ORDER BY trade_date",
            conn, params=(ts_code, date)
        )
        if len(df) < 60:
            continue

        # --- 股性数据（涨停次数） ---
        lu = compute_limit_up_counts(df)
        all_lu_counts.append(lu)

        # --- 量价得分 ---
        vp_scores = compute_volume_price_score(df)
        latest_vp = float(vp_scores.iloc[-1])

        results.append({
            "ts_code": ts_code,
            "name": name,
            "latest_vp": latest_vp,
            "lu": lu,
        })

    # 构建排名映射
    print(f"  Building rank maps from {len(all_lu_counts)} stocks...")
    year_ranks, month_ranks = build_rank_maps(all_lu_counts)

    # 计算股性得分 + 综合得分，过滤输出
    output = []
    for r in results:
        char_score = compute_character_score(
            r["lu"]["limit_up_year"], r["lu"]["limit_up_month"],
            year_ranks, month_ranks,
        )
        composite = round(r["latest_vp"] * 0.6 + char_score * 0.4, 1)

        if composite >= 50:
            output.append({
                "ts_code": r["ts_code"],
                "name": r["name"],
                "trade_date": date,
                "composite_score": composite,
                "vp_score": round(r["latest_vp"], 1),
                "char_score": round(char_score, 1),
                "limit_up_year": r["lu"]["limit_up_year"],
                "limit_up_month": r["lu"]["limit_up_month"],
                "vol_ratio": 0,
                "cross_days_ago": -1,
                "ma5": 0,
                "ma21": 0,
                "close": 0,
            })

    output.sort(key=lambda x: x["composite_score"], reverse=True)
    return output


def save_signals_to_db(conn, signals: list[dict]):
    """将信号写入 signals 表"""
    if not signals:
        return

    date = signals[0]["trade_date"]
    conn.execute("DELETE FROM signals WHERE trade_date=?", (date,))

    for s in signals:
        rule_info = json.dumps({
            "vp_score": s["vp_score"],
            "char_score": s["char_score"],
            "limit_up_year": s["limit_up_year"],
            "limit_up_month": s["limit_up_month"],
            "vol_ratio": s.get("vol_ratio", 0),
        })

        conn.execute(
            """INSERT OR REPLACE INTO signals
               (ts_code, trade_date, composite_score, rule_signals,
                confidence, up_5d_prob, up_20d_prob, market_regime, risk_flags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (s["ts_code"], date, s["composite_score"],
             rule_info,
             round(s["composite_score"] / 100, 4),  # confidence 用归一化综合分
             round(s["composite_score"] / 100, 4),
             round(s["composite_score"] / 100, 4),
             "neutral", json.dumps([]))
        )
    conn.commit()
