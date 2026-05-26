"""训练 LSTM + 全量扫描流水线"""
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
from backend.engine.pattern.lstm import PriceLSTM, LSTM_SEQ_LEN, MODEL_DIR
from backend.config import LSTM_HIDDEN, LSTM_LAYERS, LSTM_DROPOUT
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset
import torch.nn as nn


FEATURE_COLS = [
    "open", "high", "low", "close", "volume",
    "ma_5", "ma_20", "macd_dif", "macd_dea",
    "kdj_k", "kdj_d", "rsi", "boll_width", "atr", "volume_ratio",
]


def load_all_data(conn):
    """加载全部股票的K线数据并计算指标"""
    stocks = conn.execute("SELECT ts_code FROM stock_basic").fetchall()
    all_sequences = []

    for i, (ts_code,) in enumerate(stocks):
        df = pd.read_sql_query(
            "SELECT * FROM daily_kline WHERE ts_code=? ORDER BY trade_date",
            conn, params=(ts_code,),
        )
        if len(df) < LSTM_SEQ_LEN + 20:
            continue

        df = calc_all_indicators(df)
        available = [c for c in FEATURE_COLS if c in df.columns]
        df_clean = df[available].replace([np.inf, -np.inf], np.nan).dropna()

        if len(df_clean) < LSTM_SEQ_LEN + 20:
            continue

        close = df.loc[df_clean.index, "close"]

        X_list, y_5d_list, y_20d_list = [], [], []
        for j in range(LSTM_SEQ_LEN, len(df_clean) - 20, 3):  # 每3条取1条，降采样
            X_list.append(df_clean.iloc[j - LSTM_SEQ_LEN:j].values.astype(np.float32))
            f5 = close.iloc[j + 5] / close.iloc[j] - 1
            f20 = close.iloc[j + 20] / close.iloc[j] - 1
            y_5d_list.append(1.0 if f5 > 0 else 0.0)
            y_20d_list.append(1.0 if f20 > 0 else 0.0)

        if X_list:
            all_sequences.append({
                "X": np.array(X_list, dtype=np.float32),
                "y_5d": np.array(y_5d_list, dtype=np.float32),
                "y_20d": np.array(y_20d_list, dtype=np.float32),
            })

        if (i + 1) % 50 == 0:
            print(f"  Loaded {i + 1}/{len(stocks)} stocks...")

    return all_sequences


def train(conn):
    print("Loading data and computing indicators...")
    sequences = load_all_data(conn)

    if not sequences:
        print("ERROR: No valid sequences found")
        return None, None

    # Merge all sequences
    X_all = np.concatenate([s["X"] for s in sequences], axis=0)
    y_5d_all = np.concatenate([s["y_5d"] for s in sequences])
    y_20d_all = np.concatenate([s["y_20d"] for s in sequences])

    print(f"Total sequences: {len(X_all)} (from {len(sequences)} stocks)")

    # Fit scaler on raw data (reshaped), keep float32
    n_samples, seq_len, n_features = X_all.shape
    X_flat = X_all.reshape(-1, n_features)
    scaler = StandardScaler()
    scaler.fit(X_flat.astype(np.float64))  # sklearn needs float64 for fitting

    # Scale in float32
    X_scaled = np.array([scaler.transform(sample.astype(np.float64)).astype(np.float32)
                         for sample in X_all])
    X_tensor = torch.tensor(X_scaled, dtype=torch.float32)
    y_tensor = torch.tensor(np.column_stack([y_5d_all, y_20d_all]), dtype=torch.float32)

    # Train/Test split
    n = len(X_tensor)
    split = int(n * 0.8)
    train_ds = TensorDataset(X_tensor[:split], y_tensor[:split])
    test_ds = TensorDataset(X_tensor[split:], y_tensor[split:])
    train_dl = DataLoader(train_ds, batch_size=256, shuffle=True)
    test_dl = DataLoader(test_ds, batch_size=256)

    model = PriceLSTM(input_dim=n_features)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.0005, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

    print(f"Training LSTM (input_dim={n_features}, samples={n})...")
    best_loss = float("inf")
    patience_counter = 0
    MODEL_DIR.mkdir(exist_ok=True)

    for epoch in range(50):
        model.train()
        train_loss = 0
        for xb, yb in train_dl:
            optimizer.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()

        model.eval()
        test_loss = 0
        with torch.no_grad():
            for xb, yb in test_dl:
                test_loss += loss_fn(model(xb), yb).item()

        scheduler.step(test_loss)

        if test_loss < best_loss:
            best_loss = test_loss
            patience_counter = 0
            torch.save(model.state_dict(), str(MODEL_DIR / "lstm_best.pt"))
        else:
            patience_counter += 1

        if epoch % 5 == 0:
            print(f"  Epoch {epoch}: train={train_loss/len(train_dl):.4f}, test={test_loss/len(test_dl):.4f}")

        if patience_counter >= 10:
            print(f"  Early stopping at epoch {epoch}")
            break

    model.load_state_dict(torch.load(str(MODEL_DIR / "lstm_best.pt")))

    # Save scaler
    with open(MODEL_DIR / "scaler.pkl", "wb") as f:
        pickle.dump((scaler, FEATURE_COLS), f)

    print(f"Model saved to {MODEL_DIR}")
    return model, scaler


def scan(conn, model, scaler):
    print("Running daily scan...")
    stocks = conn.execute("SELECT ts_code FROM stock_basic").fetchall()
    results = []

    for ts_code, in stocks:
        df = pd.read_sql_query(
            "SELECT * FROM daily_kline WHERE ts_code=? ORDER BY trade_date",
            conn, params=(ts_code,),
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

        model.eval()
        with torch.no_grad():
            logits = model(X.unsqueeze(0))
            probs = torch.sigmoid(logits).squeeze().tolist()

        up_5d = round(probs[0], 4)
        up_20d = round(probs[1], 4)
        confidence = max(up_5d, up_20d)
        rule_score = min(len(rule_hits) / max(len(patterns.columns), 1), 1.0) * 40
        model_score = 30 + (confidence - 0.5) * 60
        score = round(rule_score + model_score, 1)

        if score >= 50:
            sig = {
                "ts_code": ts_code,
                "trade_date": df["trade_date"].iloc[-1],
                "composite_score": score,
                "rule_signals": json.dumps(rule_hits),
                "confidence": confidence,
                "up_5d_prob": up_5d,
                "up_20d_prob": up_20d,
                "market_regime": "neutral",
                "risk_flags": json.dumps([]),
            }
            conn.execute(
                """INSERT OR REPLACE INTO signals
                   (ts_code, trade_date, composite_score, rule_signals,
                    confidence, up_5d_prob, up_20d_prob, market_regime, risk_flags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sig["ts_code"], sig["trade_date"], sig["composite_score"],
                 sig["rule_signals"], sig["confidence"],
                 sig["up_5d_prob"], sig["up_20d_prob"],
                 sig["market_regime"], sig["risk_flags"]),
            )
            results.append(sig)

    conn.commit()
    print(f"Scan complete: {len(results)} signals generated (score >= 50)")
    return results


if __name__ == "__main__":
    init_db()
    conn = get_connection()

    # Check existing data
    stocks_count = conn.execute("SELECT COUNT(*) FROM stock_basic").fetchone()[0]
    klines_count = conn.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
    print(f"Data: {stocks_count} stocks, {klines_count} klines")

    # Train
    model, scaler = train(conn)

    if model is not None:
        # Scan
        results = scan(conn, model, scaler)

        # Show top signals
        if results:
            top = sorted(results, key=lambda x: x["composite_score"], reverse=True)[:10]
            print("\nTop 10 Signals:")
            for s in top:
                print(f"  {s['ts_code']} | score={s['composite_score']} | "
                      f"5d={s['up_5d_prob']:.2%} | 20d={s['up_20d_prob']:.2%} | "
                      f"rules={json.loads(s['rule_signals'])}")

    conn.close()
    print("\nPipeline complete.")
