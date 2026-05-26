"""历史扫描：对过去 N 个交易日扫描信号，用于回测验证"""
import sys
import pickle
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.engine.data.schema import get_connection, init_db
from backend.engine.pattern.indicators import calc_all_indicators
from backend.engine.pattern.rules import detect_all_patterns
from backend.engine.pattern.lstm import PriceLSTM, LSTM_SEQ_LEN, MODEL_DIR, prepare_sequences

FEATURE_COLS = [
    "open", "high", "low", "close", "volume",
    "ma_5", "ma_20", "macd_dif", "macd_dea",
    "kdj_k", "kdj_d", "rsi", "boll_width", "atr", "volume_ratio",
]


def main():
    init_db()
    conn = get_connection()

    # Load model
    with open(MODEL_DIR / "scaler.pkl", "rb") as f:
        scaler, _ = pickle.load(f)

    model = PriceLSTM(input_dim=15)
    model.load_state_dict(torch.load(MODEL_DIR / "lstm_best.pt"))
    model.eval()

    # Get all unique trade dates in the last 6 months
    dates = conn.execute(
        "SELECT DISTINCT trade_date FROM daily_kline WHERE trade_date >= '2025-12-01' ORDER BY trade_date"
    ).fetchall()
    trade_dates = [d[0] for d in dates]

    # Scan every 5th trading day
    scan_dates = trade_dates[::5]
    print(f"Scanning {len(scan_dates)} historical dates from {scan_dates[0]} to {scan_dates[-1]}")

    all_signals = []
    for scan_date in scan_dates:
        stocks = conn.execute("SELECT ts_code FROM stock_basic").fetchall()
        for ts_code, in stocks:
            df = pd.read_sql_query(
                "SELECT * FROM daily_kline WHERE ts_code=? AND trade_date<=? ORDER BY trade_date",
                conn, params=(ts_code, scan_date),
            )
            if len(df) < LSTM_SEQ_LEN + 20:
                continue

            df = calc_all_indicators(df)
            patterns = detect_all_patterns(df)
            latest_patterns = patterns.iloc[-1]
            rule_hits = [k for k, v in latest_patterns.items() if v]

            if not rule_hits:
                continue

            available = [c for c in FEATURE_COLS if c in df.columns]
            df_clean = df[available].replace([np.inf, -np.inf], np.nan).dropna()
            if len(df_clean) < LSTM_SEQ_LEN:
                continue

            raw = df_clean.iloc[-LSTM_SEQ_LEN:].values.astype(np.float64)
            scaled = scaler.transform(raw).astype(np.float32)
            X = torch.tensor(scaled, dtype=torch.float32)

            with torch.no_grad():
                logits = model(X.unsqueeze(0))
                probs = torch.sigmoid(logits).squeeze().tolist()

            up_5d = round(probs[0], 4)
            up_20d = round(probs[1], 4)
            confidence = max(up_5d, up_20d)
            rule_score = min(len(rule_hits) / max(len(patterns.columns), 1), 1.0) * 40
            model_score = 30 + (confidence - 0.5) * 60
            score = round(rule_score + model_score, 1)

            if score >= 48:
                conn.execute(
                    """INSERT OR REPLACE INTO signals
                       (ts_code, trade_date, composite_score, rule_signals,
                        confidence, up_5d_prob, up_20d_prob, market_regime, risk_flags)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ts_code, scan_date, score,
                     json.dumps(rule_hits), confidence,
                     up_5d, up_20d, "neutral", json.dumps([])),
                )
                all_signals.append({
                    "ts_code": ts_code,
                    "trade_date": scan_date,
                    "composite_score": score,
                    "rule_signals": rule_hits,
                })

        conn.commit()
        print(f"  {scan_date}: {len([s for s in all_signals if s['trade_date'] == scan_date])} signals")

    print(f"\nTotal: {len(all_signals)} historical signals generated")
    conn.close()


if __name__ == "__main__":
    main()
