import pandas as pd
import numpy as np


def calc_ma(df: pd.DataFrame, periods: list[int] = [5, 10, 20, 60]) -> pd.DataFrame:
    for p in periods:
        df[f"ma_{p}"] = df["close"].rolling(p).mean()
        df[f"ema_{p}"] = df["close"].ewm(span=p, adjust=False).mean()
    return df


def calc_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd_dif"] = ema_fast - ema_slow
    df["macd_dea"] = df["macd_dif"].ewm(span=signal, adjust=False).mean()
    df["macd_bar"] = 2 * (df["macd_dif"] - df["macd_dea"])
    return df


def calc_kdj(df: pd.DataFrame, n=9, k=3, d=3) -> pd.DataFrame:
    low_min = df["low"].rolling(n).min()
    high_max = df["high"].rolling(n).max()
    rsv = ((df["close"] - low_min) / (high_max - low_min + 1e-9)) * 100
    df["kdj_k"] = rsv.ewm(com=k-1, adjust=False).mean()
    df["kdj_d"] = df["kdj_k"].ewm(com=d-1, adjust=False).mean()
    df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]
    return df


def calc_rsi(df: pd.DataFrame, period=14) -> pd.DataFrame:
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def calc_bollinger(df: pd.DataFrame, period=20, std=2) -> pd.DataFrame:
    df["boll_mid"] = df["close"].rolling(period).mean()
    s = df["close"].rolling(period).std()
    df["boll_upper"] = df["boll_mid"] + std * s
    df["boll_lower"] = df["boll_mid"] - std * s
    df["boll_width"] = (df["boll_upper"] - df["boll_lower"]) / df["boll_mid"]
    return df


def calc_atr(df: pd.DataFrame, period=14) -> pd.DataFrame:
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        (high - low),
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(span=period, adjust=False).mean()
    return df


def calc_volume_ma(df: pd.DataFrame, period=20) -> pd.DataFrame:
    df["vol_ma_5"] = df["volume"].rolling(5).mean()
    df["vol_ma_20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / (df["vol_ma_20"] + 1e-9)
    return df


def calc_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = calc_ma(df)
    df = calc_macd(df)
    df = calc_kdj(df)
    df = calc_rsi(df)
    df = calc_bollinger(df)
    df = calc_atr(df)
    df = calc_volume_ma(df)
    return df
