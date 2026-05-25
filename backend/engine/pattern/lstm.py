# smart-stock/backend/engine/pattern/lstm.py
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
import pickle
from pathlib import Path
from backend.config import LSTM_SEQ_LEN, LSTM_HIDDEN, LSTM_LAYERS, LSTM_DROPOUT, MODEL_DIR


class PriceLSTM(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, LSTM_HIDDEN, LSTM_LAYERS,
            batch_first=True, dropout=LSTM_DROPOUT
        )
        self.fc = nn.Sequential(
            nn.Linear(LSTM_HIDDEN, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 2)  # up_5d_prob, up_20d_prob
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


def prepare_sequences(df, seq_len=LSTM_SEQ_LEN):
    feature_cols = ["open", "high", "low", "close", "volume",
                    "ma_5", "ma_20", "macd_dif", "macd_dea",
                    "kdj_k", "kdj_d", "rsi", "boll_width", "atr", "volume_ratio"]

    # 只用存在的列
    feature_cols = [c for c in feature_cols if c in df.columns]
    data = df[feature_cols].copy()
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    scaler = StandardScaler()
    scaled = scaler.fit_transform(data)

    X, y_5d, y_20d = [], [], []
    for i in range(seq_len, len(scaled) - 20):
        X.append(scaled[i - seq_len:i])
        future_5 = df["close"].iloc[i + 5] / df["close"].iloc[i] - 1
        future_20 = df["close"].iloc[i + 20] / df["close"].iloc[i] - 1
        y_5d.append(1.0 if future_5 > 0 else 0.0)
        y_20d.append(1.0 if future_20 > 0 else 0.0)

    return (torch.tensor(np.array(X), dtype=torch.float32),
            torch.tensor(np.array([y_5d, y_20d]).T, dtype=torch.float32),
            scaler, feature_cols)


def train_model(X, y, epochs=50, batch_size=64, lr=0.001):
    n = len(X)
    split = int(n * 0.8)
    train_ds = TensorDataset(X[:split], y[:split])
    test_ds = TensorDataset(X[split:], y[split:])
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    test_dl = DataLoader(test_ds, batch_size=batch_size)

    model = PriceLSTM(input_dim=X.shape[2])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss()

    best_loss = float("inf")
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for xb, yb in train_dl:
            optimizer.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        model.eval()
        test_loss = 0
        with torch.no_grad():
            for xb, yb in test_dl:
                test_loss += loss_fn(model(xb), yb).item()

        if test_loss < best_loss:
            best_loss = test_loss
            torch.save(model.state_dict(),
                       str(MODEL_DIR / "lstm_best.pt"))

        if epoch % 10 == 0:
            print(f"Epoch {epoch}: train_loss={train_loss/len(train_dl):.4f}, "
                  f"test_loss={test_loss/len(test_dl):.4f}")

    model.load_state_dict(torch.load(str(MODEL_DIR / "lstm_best.pt")))
    return model


def predict(model, X, scaler, feature_cols):
    model.eval()
    with torch.no_grad():
        logits = model(X.unsqueeze(0))
        probs = torch.sigmoid(logits).squeeze().tolist()
    return {"up_5d_prob": round(probs[0], 4), "up_20d_prob": round(probs[1], 4)}
