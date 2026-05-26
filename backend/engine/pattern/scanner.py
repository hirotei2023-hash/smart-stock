# smart-stock/backend/engine/pattern/scanner.py
import json
import pandas as pd
import torch
from backend.engine.data.schema import get_connection
from backend.engine.pattern.indicators import calc_all_indicators
from backend.engine.pattern.rules import detect_all_patterns
from backend.engine.pattern.lstm import PriceLSTM, prepare_sequences, predict
from backend.config import LSTM_SEQ_LEN, MODEL_DIR


def compute_composite_score(rule_hits: int, total_rules: int,
                            confidence: float, up_prob: float) -> float:
    """综合评分：规则命中 + 模型概率 加权"""
    rule_score = min(rule_hits / max(total_rules, 1), 1.0) * 40
    model_score = 30 + (confidence - 0.5) * 60  # 0.5→30分(中性), 1.0→60分
    return round(rule_score + model_score, 1)


def scan_stock(ts_code: str, conn, model, scaler, feature_cols) -> dict | None:
    """扫描单只股票，返回信号 dict 或 None"""
    df = pd.read_sql_query(
        "SELECT * FROM daily_kline WHERE ts_code=? ORDER BY trade_date",
        conn, params=(ts_code,)
    )
    if len(df) < LSTM_SEQ_LEN + 20:
        return None

    df = calc_all_indicators(df)
    patterns = detect_all_patterns(df)
    latest_patterns = patterns.iloc[-1]
    rule_hits = [k for k, v in latest_patterns.items() if v]

    if not rule_hits:
        return None  # 规则层筛掉

    # 准备 LSTM 输入
    feature_cols_available = [c for c in feature_cols if c in df.columns]
    data = df[feature_cols_available].dropna()
    if len(data) < LSTM_SEQ_LEN:
        return None

    scaled = scaler.transform(data.iloc[-LSTM_SEQ_LEN:])
    X = torch.tensor(scaled, dtype=torch.float32)
    pred = predict(model, X, scaler, feature_cols_available)

    confidence = max(pred["up_5d_prob"], pred["up_20d_prob"])
    score = compute_composite_score(len(rule_hits), len(patterns.columns),
                                     confidence, pred["up_5d_prob"])

    return {
        "ts_code": ts_code,
        "trade_date": df["trade_date"].iloc[-1],
        "composite_score": score,
        "rule_signals": json.dumps(rule_hits),
        "confidence": round(confidence, 4),
        "up_5d_prob": pred["up_5d_prob"],
        "up_20d_prob": pred["up_20d_prob"],
        "market_regime": "neutral",
        "risk_flags": json.dumps([]),
    }


def daily_scan(conn, model, scaler, feature_cols) -> list[dict]:
    """每日全量扫描沪深300"""
    stocks = conn.execute("SELECT ts_code FROM stock_basic").fetchall()
    results = []
    for (ts_code,) in stocks:
        sig = scan_stock(ts_code, conn, model, scaler, feature_cols)
        if sig and sig["composite_score"] >= 50:  # 最低 50 分入库
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
            results.append(sig)
    conn.commit()
    return results
