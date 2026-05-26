"""Historical scan: 用 V2 LightGBM 模型扫描过去每个采样日期，生成历史信号用于回测"""
import sys, json, gc
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from backend.engine.data.schema import get_connection, init_db
from backend.engine.factors.library import compute_all_factors, ALL_FACTORS
from backend.engine.pattern.lightgbm_model import LightGBMClassifier
from backend.engine.pattern.rules import detect_all_patterns
from backend.engine.pattern.indicators import calc_all_indicators


def scan_date(conn, model, scaler, factor_cols, date):
    """扫描某个日期的所有股票，返回信号列表"""
    stocks = conn.execute("SELECT ts_code FROM stock_basic").fetchall()
    results = []

    for (ts_code,) in stocks:
        # 只读取该日期之前的数据，避免未来信息泄露
        df = pd.read_sql_query(
            "SELECT * FROM daily_kline WHERE ts_code=? AND trade_date <= ? ORDER BY trade_date",
            conn, params=(ts_code, date)
        )
        if len(df) < 120:
            continue

        # 检查该股票在该日期是否有数据
        if df["trade_date"].iloc[-1] != date:
            continue

        df = calc_all_indicators(df)
        factors = compute_all_factors(df)
        df_combined = pd.concat([df.reset_index(drop=True), factors.reset_index(drop=True)], axis=1)

        patterns = detect_all_patterns(df)
        latest_patterns = patterns.iloc[-1]
        rule_hits = [k for k, v in latest_patterns.items() if v]

        latest = df_combined.iloc[-1]
        available = [c for c in factor_cols if c in df_combined.columns]
        X = pd.DataFrame([latest[available].fillna(0).values], columns=available).astype(np.float32)
        X_scaled = scaler.transform(X)

        try:
            proba = model.predict_proba(X_scaled)[0, 1]
        except Exception:
            proba = 0.5

        ret20 = latest.get("ret_20d", 0) if "ret_20d" in df_combined.columns else 0
        if pd.isna(ret20):
            ret20 = 0
        reversal_score = max(0, min(60, 30 - ret20 * 100))

        rule_score = min(len(rule_hits) / max(len(patterns.columns) or 1, 1), 1.0) * 30
        model_score = 30 + (proba - 0.5) * 80
        composite = round(rule_score + model_score + reversal_score, 1)

        if composite >= 40:
            results.append({
                "ts_code": ts_code, "trade_date": date,
                "composite_score": composite,
                "rule_signals": json.dumps(rule_hits),
                "confidence": round(proba, 4),
                "up_5d_prob": round(proba, 4),
                "up_20d_prob": round(proba, 4),
                "market_regime": "neutral",
                "risk_flags": json.dumps([]),
            })

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    return results


def main():
    conn = get_connection()
    init_db()

    # 加载模型
    model = LightGBMClassifier.load("lightgbm")
    factor_cols = list(ALL_FACTORS.keys())

    # 获取全量数据拟合 scaler
    print("Fitting scaler on all factor data...")
    all_stocks = conn.execute("SELECT ts_code FROM stock_basic").fetchall()
    sample_frames = []
    for (ts_code,) in all_stocks:
        df = pd.read_sql_query(
            "SELECT * FROM daily_kline WHERE ts_code=? ORDER BY trade_date",
            conn, params=(ts_code,)
        )
        if len(df) < 120:
            continue
        df = df.iloc[::5].copy()
        df = calc_all_indicators(df)
        factors = compute_all_factors(df)
        df = pd.concat([df.reset_index(drop=True), factors.reset_index(drop=True)], axis=1)

        available = [c for c in factor_cols if c in df.columns]
        sample = df[available].iloc[-50:].copy()
        sample_frames.append(sample)

    if not sample_frames:
        print("ERROR: No data for scaler fitting")
        conn.close()
        return

    scaler_data = pd.concat(sample_frames, ignore_index=True).fillna(0)
    scaler = StandardScaler()
    scaler.fit(scaler_data.astype(np.float32))
    del scaler_data, sample_frames
    gc.collect()

    # 采样日期：从 2025-12-01 开始，每 5 个交易日扫描一次
    print("Getting sampling dates...")
    all_dates = pd.read_sql_query(
        "SELECT DISTINCT trade_date FROM daily_kline WHERE trade_date >= '2025-12-01' AND trade_date <= '2026-05-25' ORDER BY trade_date",
        conn
    )["trade_date"].tolist()

    # 每 5 天采一个日期
    sample_dates = all_dates[::5]
    print(f"Sampling {len(sample_dates)} dates from {len(all_dates)} trading days")

    # 清除旧信号（非最新日期 2026-05-25 的）
    # 但保留原始 2025 年 signals 用于对比
    total_signals = 0
    for i, date in enumerate(sample_dates):
        print(f"[{i+1}/{len(sample_dates)}] Scanning {date}...")

        signals = scan_date(conn, model, scaler, factor_cols, date)
        total_signals += len(signals)

        # 替换该日期的旧信号
        conn.execute("DELETE FROM signals WHERE trade_date=?", (date,))
        for sig in signals:
            conn.execute(
                """INSERT OR REPLACE INTO signals
                   (ts_code, trade_date, composite_score, rule_signals,
                    confidence, up_5d_prob, up_20d_prob, market_regime, risk_flags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sig["ts_code"], sig["trade_date"], sig["composite_score"],
                 sig["rule_signals"], sig["confidence"],
                 sig["up_5d_prob"], sig["up_20d_prob"],
                 sig["market_regime"], sig["risk_flags"])
            )
        conn.commit()

        if (i + 1) % 5 == 0:
            print(f"  Progress: {total_signals} signals so far...")
            gc.collect()

    # 统计
    final_count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    dates_count = conn.execute("SELECT COUNT(DISTINCT trade_date) FROM signals").fetchone()[0]
    print(f"\nDone! {final_count} signals across {dates_count} dates")
    conn.close()


if __name__ == "__main__":
    main()
