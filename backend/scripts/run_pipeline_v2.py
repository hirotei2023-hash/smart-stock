"""Phase 2b: LightGBM + Walk-Forward + 因子 — 内存优化版（逐股处理）"""
import sys
import json
import gc
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
from backend.engine.backtest.validation import WalkForwardValidator
from backend.config import LSTM_SEQ_LEN


def build_label(df, horizon=20):
    future = df["close"].shift(-horizon)
    label = (future / df["close"] - 1) > 0
    return label.astype(np.int8)


def model_builder():
    return LightGBMClassifier()


def process_stock(conn, ts_code, factor_names, step=3):
    """处理单只股票：计算因子+label，只保留因子列，返回精简 DataFrame"""
    df = pd.read_sql_query(
        "SELECT * FROM daily_kline WHERE ts_code=? ORDER BY trade_date",
        conn, params=(ts_code,)
    )
    if len(df) < 200:
        return None

    df = df.iloc[::step].copy()  # 每 step 天取一个样本，减少数据量
    df = calc_all_indicators(df)
    factors = compute_all_factors(df)
    df = pd.concat([df.reset_index(drop=True), factors.reset_index(drop=True)], axis=1)

    df["label"] = build_label(df, horizon=20)

    # 只保留因子列 + 必要标识
    cols_to_keep = ["ts_code", "trade_date", "close", "label"]
    available_factors = [c for c in factor_names if c in df.columns]
    cols_to_keep += available_factors

    df = df[cols_to_keep].copy()
    df = df.dropna(subset=["label"])

    # float32 减少内存
    for c in available_factors:
        df[c] = df[c].astype(np.float32)
    df["label"] = df["label"].astype(np.int8)

    return df


def scan_signals_v2(conn, model, scaler, feature_cols, date):
    """用训练好的模型扫描最新信号"""
    stocks = conn.execute("SELECT ts_code FROM stock_basic").fetchall()
    results = []

    for (ts_code,) in stocks:
        df = pd.read_sql_query(
            "SELECT * FROM daily_kline WHERE ts_code=? ORDER BY trade_date",
            conn, params=(ts_code,)
        )
        if len(df) < 120:
            continue

        df = calc_all_indicators(df)
        factors = compute_all_factors(df)
        df = pd.concat([df, factors], axis=1)

        patterns = detect_all_patterns(df)
        latest_patterns = patterns.iloc[-1]
        rule_hits = [k for k, v in latest_patterns.items() if v]

        latest = df.iloc[-1]
        available = [c for c in feature_cols if c in df.columns]
        X = pd.DataFrame([latest[available].fillna(0).values], columns=available).astype(np.float32)
        X_scaled = scaler.transform(X)

        try:
            proba = model.predict_proba(X_scaled)[0, 1]
        except Exception:
            proba = 0.5

        if "ret_20d" in df.columns:
            ret20 = latest.get("ret_20d", 0)
            if pd.isna(ret20):
                ret20 = 0
            reversal_score = max(0, min(60, 30 - ret20 * 100))
        else:
            reversal_score = 30

        rule_score = min(len(rule_hits) / max(len(patterns.columns) or 1, 1), 1.0) * 30
        model_score = 30 + (proba - 0.5) * 80  # 0.5→30, 0.6→38
        composite = round(rule_score + model_score + reversal_score, 1)  # 恢复满权重

        if composite >= 40:
            results.append({
                "ts_code": ts_code,
                "trade_date": date,
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

    # 1. 获取股票列表和因子名
    stocks = conn.execute("SELECT ts_code FROM stock_basic").fetchall()
    factor_names = list(ALL_FACTORS.keys())
    print(f"Stocks: {len(stocks)}, Factors: {len(factor_names)}")

    # 2. 逐股处理（内存友好）
    print("Processing stocks (factor computation + label)...")
    frames = []
    n_stocks = len(stocks)
    for i, (ts_code,) in enumerate(stocks):
        try:
            result = process_stock(conn, ts_code, factor_names, step=3)
            if result is not None and len(result) > 0:
                frames.append(result)
        except Exception as e:
            print(f"  [{i+1}/{n_stocks}] {ts_code} ERROR: {e}")

        if (i + 1) % 100 == 0:
            total_rows = sum(len(f) for f in frames)
            print(f"  [{i+1}/{n_stocks}] {len(frames)} stocks processed, {total_rows:,} samples")
            gc.collect()

    if not frames:
        print("ERROR: No data after processing!")
        conn.close()
        return

    df_model = pd.concat(frames, ignore_index=True)
    del frames
    gc.collect()

    total_rows = len(df_model)
    print(f"\nTotal model-ready samples: {total_rows:,}")
    print(f"Label distribution: {df_model['label'].value_counts().to_dict()}")
    print(f"Memory usage: {df_model.memory_usage(deep=True).sum() / 1024**2:.1f} MB")

    # 3. 确定特征列
    factor_cols = [c for c in factor_names if c in df_model.columns]
    print(f"Available factors: {len(factor_cols)}")

    # 4. Walk-Forward 训练
    print("\n=== Walk-Forward Training ===")
    wf = WalkForwardValidator(train_years=3, test_months=6, step_months=3)
    result = wf.evaluate(model_builder, df_model, factor_cols, "label")

    print(f"  Splits: {result['n_splits']}")
    print(f"  AUC per split: {[round(a, 4) for a in result['auc_per_split']]}")
    print(f"  Mean AUC: {result['mean_auc']:.4f}")
    print(f"  Overall AUC: {result['overall_auc']:.4f}")
    print(f"  Overall Acc: {result['overall_acc']:.4f}")

    # 5. 全量训练最终模型
    print("\n=== Training Final Model ===")
    X_full = df_model[factor_cols].fillna(0).astype(np.float32)
    y_full = df_model["label"].astype(int)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_full)

    final_model = LightGBMClassifier()
    final_model.fit(X_scaled, y_full, feature_names=factor_cols)
    final_model.save("lightgbm")

    print("Top 10 feature importance:")
    if final_model.feature_importance is not None:
        for feat, imp in final_model.feature_importance.head(10).items():
            print(f"  {feat}: {imp:.1f}")

    # 6. 扫描最新信号
    print("\n=== Scanning Latest Signals ===")
    latest_date = conn.execute("SELECT MAX(trade_date) FROM daily_kline").fetchone()[0]
    print(f"  Latest trading date: {latest_date}")

    signals = scan_signals_v2(conn, final_model, scaler, factor_cols, latest_date)

    conn.execute("DELETE FROM signals WHERE trade_date=?", (latest_date,))
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
    print(f"  Generated {len(signals)} signals")

    if signals:
        print("\nTop 10 signals:")
        for s in signals[:10]:
            name_row = conn.execute(
                "SELECT name FROM stock_basic WHERE ts_code=?", (s["ts_code"],)
            ).fetchone()
            name = name_row[0] if name_row else "?"
            print(f"  {s['ts_code']} {name}: score={s['composite_score']:.1f} conf={s['confidence']:.4f}")

    conn.close()
    print("\nAll done!")


if __name__ == "__main__":
    main()
