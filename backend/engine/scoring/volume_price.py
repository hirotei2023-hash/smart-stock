"""量价评分: 5MA金叉21MA(窗口) + 金叉日放量 + 今日MA5趋势延续"""
import numpy as np
import pandas as pd


def compute_volume_price_score(df: pd.DataFrame) -> pd.Series:
    """逐日计算量价得分 (0-100)。
    逻辑: 近5日发生过金叉 → 金叉日量能确认 → 今日趋势延续
    """
    close = df["close"].values
    volume = df["volume"].values
    n = len(df)

    ma5 = pd.Series(close).rolling(5).mean().values
    ma21 = pd.Series(close).rolling(21).mean().values
    vol_ma5 = pd.Series(volume).rolling(5).mean().values

    scores = np.zeros(n)

    for i in range(21, n):
        # 1. 找最近一次金叉日（5日窗口内）
        cross_idx = -1
        for j in range(i, max(21, i-4)-1, -1):
            if (ma5[j-1] < ma21[j-1]) and (ma5[j] > ma21[j]):
                cross_idx = j
                break

        if cross_idx < 0:
            continue

        # 2. 金叉日量能确认 (>1.5倍5日均量)
        if vol_ma5[cross_idx] <= 0:
            continue
        vol_ratio = volume[cross_idx] / vol_ma5[cross_idx]
        if vol_ratio < 1.5:
            continue

        # 3. 今日 MA5 趋势延续（至少 3 日中的 2 日走高）
        if i >= 3:
            rising_days = sum([
                ma5[i] > ma5[i-1],
                ma5[i-1] > ma5[i-2],
                ma5[i-2] > ma5[i-3],
            ])
            if rising_days < 2:
                continue

        # 4. 今日收盘站上 21 日线
        if close[i] <= ma21[i]:
            continue

        # --- 打分 ---
        cross_days_ago = i - cross_idx
        cross_score = max(25, 40 - cross_days_ago * 5)  # 当天40→35→30→25

        vol_score = 15.0 + min(15.0, (vol_ratio - 1.5) / 1.5 * 15)  # 1.5x→15, 3x→30

        scores[i] = cross_score + 30.0 + vol_score  # 金叉 + 趋势 + 量能

    return pd.Series(scores, index=df.index)


def get_latest_signal_detail(df: pd.DataFrame) -> dict | None:
    """获取最新一天的信号详细信息，供前端展示"""
    close = df["close"].values
    volume = df["volume"].values
    n = len(df)
    i = n - 1

    ma5 = pd.Series(close).rolling(5).mean().values
    ma21 = pd.Series(close).rolling(21).mean().values
    vol_ma5 = pd.Series(volume).rolling(5).mean().values

    cross_idx = -1
    for j in range(i, max(21, i-4)-1, -1):
        if (ma5[j-1] < ma21[j-1]) and (ma5[j] > ma21[j]):
            cross_idx = j
            break

    if cross_idx < 0:
        return None

    vol_ratio = volume[cross_idx] / vol_ma5[cross_idx] if vol_ma5[cross_idx] > 0 else 0

    return {
        "cross_date": str(df["trade_date"].iloc[cross_idx]),
        "cross_days_ago": i - cross_idx,
        "cross_vol_ratio": round(float(vol_ratio), 2),
        "ma5": round(float(ma5[i]), 2),
        "ma21": round(float(ma21[i]), 2),
        "close": round(float(close[i]), 2),
    }
