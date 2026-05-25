# smart-stock/backend/engine/pattern/rules.py
import pandas as pd
import numpy as np


def detect_hammer(df: pd.DataFrame, body_ratio=0.3, shadow_ratio=2.0) -> pd.Series:
    body = (df["close"] - df["open"]).abs()
    upper = df["high"] - df[["open", "close"]].max(axis=1)
    lower = df[["open", "close"]].min(axis=1) - df["low"]
    is_small_body = body / (df["high"] - df["low"] + 1e-9) < body_ratio
    is_long_lower = lower / (body + 1e-9) > shadow_ratio
    is_short_upper = upper / (body + 1e-9) < 0.5
    return is_small_body & is_long_lower & is_short_upper


def detect_engulfing(df: pd.DataFrame) -> pd.Series:
    prev_open, prev_close = df["open"].shift(1), df["close"].shift(1)
    bullish = (prev_close < prev_open) & (df["close"] > df["open"]) & \
              (df["open"] <= prev_close) & (df["close"] >= prev_open)
    bearish = (prev_close > prev_open) & (df["close"] < df["open"]) & \
              (df["open"] >= prev_close) & (df["close"] <= prev_open)
    return bullish, bearish


def detect_doji(df: pd.DataFrame, threshold=0.001) -> pd.Series:
    body_pct = (df["close"] - df["open"]).abs() / (df["open"] + 1e-9)
    return body_pct < threshold


def detect_three_white_soldiers(df: pd.DataFrame) -> pd.Series:
    c1, c2, c3 = df["close"].shift(2), df["close"].shift(1), df["close"]
    o1, o2, o3 = df["open"].shift(2), df["open"].shift(1), df["open"]
    bullish = (c1 > o1) & (c2 > o2) & (c3 > o3)
    rising = (c2 > c1) & (c3 > c2)
    return bullish & rising


def detect_three_black_crows(df: pd.DataFrame) -> pd.Series:
    c1, c2, c3 = df["close"].shift(2), df["close"].shift(1), df["close"]
    o1, o2, o3 = df["open"].shift(2), df["open"].shift(1), df["open"]
    bearish = (c1 < o1) & (c2 < o2) & (c3 < o3)
    falling = (c2 < c1) & (c3 < c2)
    return bearish & falling


def detect_morning_star(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(2) - df["open"].shift(2)
    mid_body = (df["close"].shift(1) - df["open"].shift(1)).abs()
    cur = df["close"] - df["open"]
    prev_bearish = prev < -0.02 * df["open"].shift(2)
    mid_small = mid_body / (df["open"].shift(1) + 1e-9) < 0.01
    cur_bullish = cur > 0.02 * df["open"]
    return prev_bearish & mid_small & cur_bullish


def detect_evening_star(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(2) - df["open"].shift(2)
    mid_body = (df["close"].shift(1) - df["open"].shift(1)).abs()
    cur = df["close"] - df["open"]
    prev_bullish = prev > 0.02 * df["open"].shift(2)
    mid_small = mid_body / (df["open"].shift(1) + 1e-9) < 0.01
    cur_bearish = cur < -0.02 * df["open"]
    return prev_bullish & mid_small & cur_bearish


def detect_double_bottom(df: pd.DataFrame, window=20, tolerance=0.03) -> pd.Series:
    low_20 = df["low"].rolling(window).min()
    high_mid = df["high"].rolling(window // 2).max()
    is_near_low = (df["low"] - low_20).abs() / (low_20 + 1e-9) < tolerance
    break_neck = df["close"] > df["close"].rolling(window // 2).max()
    return is_near_low & break_neck


def detect_double_top(df: pd.DataFrame, window=20, tolerance=0.03) -> pd.Series:
    high_20 = df["high"].rolling(window).max()
    is_near_high = (high_20 - df["high"]).abs() / (high_20 + 1e-9) < tolerance
    break_neck = df["close"] < df["close"].rolling(window // 2).min()
    return is_near_high & break_neck


def detect_head_shoulder_bottom(df: pd.DataFrame, window=60) -> pd.Series:
    half = window // 2
    left_low = df["low"].rolling(half).min().shift(half)
    head_low = df["low"].rolling(half).min()
    right_low = df["low"].rolling(half).min()
    is_pattern = (head_low < left_low) & (head_low < right_low)
    neckline = df["high"].rolling(window).max().shift(1)
    return is_pattern & (df["close"] > neckline)


def detect_duo_fang_pao(df: pd.DataFrame) -> pd.Series:
    c1, c2, c3 = df["close"], df["close"].shift(1), df["close"].shift(2)
    o1, o2, o3 = df["open"], df["open"].shift(1), df["open"].shift(2)
    v1, v3 = df["volume"], df["volume"].shift(2)
    day1_bull = c3 > o3
    day2_small = (c2 - o2).abs() / (o2 + 1e-9) < 0.015
    day3_bull = c1 > o1
    vol_up = v1 > v3
    return day1_bull & day2_small & day3_bull & vol_up


def detect_all_patterns(df: pd.DataFrame) -> pd.DataFrame:
    bullish_engulf, bearish_engulf = detect_engulfing(df)

    patterns = pd.DataFrame(index=df.index)
    patterns["hammer"] = detect_hammer(df)
    patterns["doji"] = detect_doji(df)
    patterns["bullish_engulfing"] = bullish_engulf
    patterns["bearish_engulfing"] = bearish_engulf
    patterns["three_white_soldiers"] = detect_three_white_soldiers(df)
    patterns["three_black_crows"] = detect_three_black_crows(df)
    patterns["morning_star"] = detect_morning_star(df)
    patterns["evening_star"] = detect_evening_star(df)
    patterns["double_bottom"] = detect_double_bottom(df)
    patterns["double_top"] = detect_double_top(df)
    patterns["head_shoulder_bottom"] = detect_head_shoulder_bottom(df)
    patterns["duo_fang_pao"] = detect_duo_fang_pao(df)

    return patterns
