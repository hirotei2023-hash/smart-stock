"""Alpha 因子库 — 40 个因子，9 大类，全部向量化计算

每个因子函数签名: (df: pd.DataFrame) -> pd.Series
输入 df 包含列: trade_date, open, high, low, close, volume, pct_chg, turnover, amount
返回与 df 等长的 pd.Series，索引对齐
"""
import numpy as np
import pandas as pd

EPS = 1e-9


# ============================================================
# 价格动量因子 (5)
# ============================================================

def ret_5d(df: pd.DataFrame) -> pd.Series:
    """5日收益率"""
    return df["close"].pct_change(5)


def ret_10d(df: pd.DataFrame) -> pd.Series:
    """10日收益率"""
    return df["close"].pct_change(10)


def ret_20d(df: pd.DataFrame) -> pd.Series:
    """20日收益率"""
    return df["close"].pct_change(20)


def ret_60d(df: pd.DataFrame) -> pd.Series:
    """60日收益率"""
    return df["close"].pct_change(60)


def momentum_20_60(df: pd.DataFrame) -> pd.Series:
    """中期动量: (T-20价格 / T-60价格 - 1)，即60日前到20日前的收益率"""
    return df["close"].shift(20) / (df["close"].shift(60) + EPS) - 1


# ============================================================
# 反转因子 (5)
# ============================================================

def ret_1d(df: pd.DataFrame) -> pd.Series:
    """1日收益率"""
    return df["close"].pct_change(1)


def ret_3d(df: pd.DataFrame) -> pd.Series:
    """3日收益率"""
    return df["close"].pct_change(3)


def rsi_6(df: pd.DataFrame) -> pd.Series:
    """6日RSI = 100 - 100/(1 + RS), RS = 6日平均涨幅/6日平均跌幅"""
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(6).mean()
    loss = (-delta).clip(lower=0).rolling(6).mean()
    rs = gain / (loss + EPS)
    return 100 - 100 / (1 + rs)


def rsi_14(df: pd.DataFrame) -> pd.Series:
    """14日RSI"""
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta).clip(lower=0).rolling(14).mean()
    rs = gain / (loss + EPS)
    return 100 - 100 / (1 + rs)


def bb_reversal(df: pd.DataFrame) -> pd.Series:
    """布林带反转: (close - bb_upper) / (bb_upper - bb_lower)
    值越小表示价格越低于上轨，反弹潜力越大
    """
    ma20 = df["close"].rolling(20).mean()
    std20 = df["close"].rolling(20).std()
    bb_upper = ma20 + 2 * std20
    bb_lower = ma20 - 2 * std20
    return (df["close"] - bb_upper) / (bb_upper - bb_lower + EPS)


# ============================================================
# 波动率因子 (4)
# ============================================================

def vol_5d(df: pd.DataFrame) -> pd.Series:
    """5日收益率标准差"""
    return df["close"].pct_change().rolling(5).std()


def vol_20d(df: pd.DataFrame) -> pd.Series:
    """20日收益率标准差"""
    return df["close"].pct_change().rolling(20).std()


def vol_ratio_5_20(df: pd.DataFrame) -> pd.Series:
    """短期波动/长期波动比率"""
    v5 = df["close"].pct_change().rolling(5).std()
    v20 = df["close"].pct_change().rolling(20).std()
    return v5 / (v20 + EPS)


def atr_pct(df: pd.DataFrame) -> pd.Series:
    """ATR(14)/close 简化版，用 (high-low) 近似真实波幅"""
    tr_approx = df["high"] - df["low"]
    atr = tr_approx.rolling(14).mean()
    return atr / (df["close"] + EPS)


# ============================================================
# 成交量因子 (6)
# ============================================================

def vol_ma_ratio_5(df: pd.DataFrame) -> pd.Series:
    """当日成交量 / 5日均量"""
    return df["volume"] / (df["volume"].rolling(5).mean() + EPS)


def vol_ma_ratio_20(df: pd.DataFrame) -> pd.Series:
    """当日成交量 / 20日均量"""
    return df["volume"] / (df["volume"].rolling(20).mean() + EPS)


def vol_trend_5(df: pd.DataFrame) -> pd.Series:
    """5日均量变化趋势: MA5(volume) 的5日变化率"""
    ma5 = df["volume"].rolling(5).mean()
    return ma5.pct_change(5)


def vol_trend_20(df: pd.DataFrame) -> pd.Series:
    """20日均量变化趋势: MA20(volume) 的20日变化率"""
    ma20 = df["volume"].rolling(20).mean()
    return ma20.pct_change(20)


def amount_ratio(df: pd.DataFrame) -> pd.Series:
    """当日成交额 / 5日均额"""
    if "amount" not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df["amount"] / (df["amount"].rolling(5).mean() + EPS)


def turnover_5d(df: pd.DataFrame) -> pd.Series:
    """5日平均换手率，若无 turnover 列则用 volume/1e8 估算"""
    if "turnover" in df.columns:
        return df["turnover"].rolling(5).mean()
    else:
        # 用成交量估算换手率（假设总股本约10亿股）
        return (df["volume"] / 100_000_000).rolling(5).mean()


# ============================================================
# 均线偏离因子 (4)
# ============================================================

def ma5_dev(df: pd.DataFrame) -> pd.Series:
    """收盘价相对5日均线偏离"""
    return df["close"] / (df["close"].rolling(5).mean() + EPS) - 1


def ma20_dev(df: pd.DataFrame) -> pd.Series:
    """收盘价相对20日均线偏离"""
    return df["close"] / (df["close"].rolling(20).mean() + EPS) - 1


def ma60_dev(df: pd.DataFrame) -> pd.Series:
    """收盘价相对60日均线偏离"""
    return df["close"] / (df["close"].rolling(60).mean() + EPS) - 1


def ma_5_20_cross(df: pd.DataFrame) -> pd.Series:
    """MA5/MA20 - 1，正值表示MA5在上方（多头排列）"""
    ma5 = df["close"].rolling(5).mean()
    ma20 = df["close"].rolling(20).mean()
    return ma5 / (ma20 + EPS) - 1


# ============================================================
# 资金流量因子 (4)
# ============================================================

def mfi_14(df: pd.DataFrame) -> pd.Series:
    """14日资金流量指标 MFI = 100 - 100/(1 + pos/neg)"""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    raw_money = typical * df["volume"]
    delta = typical.diff()
    pos_flow = raw_money.where(delta > 0, 0).rolling(14).sum()
    neg_flow = raw_money.where(delta < 0, 0).rolling(14).sum()
    mfi_ratio = pos_flow / (neg_flow + EPS)
    return 100 - 100 / (1 + mfi_ratio)


def obv_ratio(df: pd.DataFrame) -> pd.Series:
    """OBV累计值除以20日均值"""
    sign = np.sign(df["close"].diff()).fillna(0)
    obv_inc = sign * df["volume"]
    obv = obv_inc.cumsum()
    return obv / (obv.rolling(20).mean() + EPS)


def vwap_dev(df: pd.DataFrame) -> pd.Series:
    """收盘价相对VWAP偏离: close / MA20(amount/volume) - 1"""
    if "amount" in df.columns:
        daily_vwap = df["amount"] / (df["volume"] + EPS)
    else:
        # 无成交额时用均价近似
        daily_vwap = (df["high"] + df["low"] + df["close"]) / 3
    vwap_ma20 = daily_vwap.rolling(20).mean()
    return df["close"] / (vwap_ma20 + EPS) - 1


def money_flow_5d(df: pd.DataFrame) -> pd.Series:
    """5日资金流向: CMF分子求和 / 5日成交量求和"""
    hl_range = df["high"] - df["low"] + EPS
    # ((close-low)-(high-close))/(high-low) = (2*close - high - low)/(high-low)
    cmf_multiplier = (2 * df["close"] - df["high"] - df["low"]) / hl_range
    mf_raw = cmf_multiplier * df["volume"]
    return mf_raw.rolling(5).sum() / (df["volume"].rolling(5).sum() + EPS)


# ============================================================
# 技术形态因子 (5)
# ============================================================

def macd_hist(df: pd.DataFrame) -> pd.Series:
    """MACD柱: DIF - DEA, DIF=EMA12-EMA26, DEA=EMA9(DIF)"""
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    return dif - dea


def kdj_k_dev(df: pd.DataFrame) -> pd.Series:
    """KDJ K值偏离50的程度: (K-50)/50"""
    low9 = df["low"].rolling(9).min()
    high9 = df["high"].rolling(9).max()
    rsv = (df["close"] - low9) / (high9 - low9 + EPS) * 100
    # 用 EMA(alpha=1/3) 近似 KDJ 的平滑
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    return (k - 50) / 50


def boll_pos(df: pd.DataFrame) -> pd.Series:
    """布林带位置: (close - MA20) / (2*std20)，标准化偏离"""
    ma20 = df["close"].rolling(20).mean()
    std20 = df["close"].rolling(20).std()
    return (df["close"] - ma20) / (2 * std20 + EPS)


def pattern_count(df: pd.DataFrame) -> pd.Series:
    """过去20日内'下影线>上影线3倍且收阳'的形态出现次数"""
    # 下影线 = min(open, close) - low
    lower_shadow = df[["open", "close"]].min(axis=1) - df["low"]
    # 上影线 = high - max(open, close)
    upper_shadow = df["high"] - df[["open", "close"]].max(axis=1)
    # 收阳: close > open
    is_bull = df["close"] > df["open"]
    # 下影线 > 上影线 * 3 且收阳
    condition = (lower_shadow > upper_shadow * 3) & is_bull
    return condition.astype(float).rolling(20, min_periods=1).sum()


def pattern_diversity(df: pd.DataFrame) -> pd.Series:
    """过去60日内涨跌幅绝对值>5%的天数占比"""
    abs_ret = df["close"].pct_change().abs()
    big_move = (abs_ret > 0.05).astype(float)
    return big_move.rolling(60, min_periods=1).mean()


# ============================================================
# 基本面因子 (4) — 等待 daily_basic 数据接入后填充
# ============================================================

def pe_rank(df: pd.DataFrame) -> pd.Series:
    """市盈率因子，无数据时返回0（占位）"""
    if "pe" not in df.columns:
        return pd.Series(0.0, index=df.index)
    return df["pe"].rank(pct=True).fillna(0.0)


def pb_rank(df: pd.DataFrame) -> pd.Series:
    """市净率因子，无数据时返回0（占位）"""
    if "pb" not in df.columns:
        return pd.Series(0.0, index=df.index)
    return df["pb"].rank(pct=True).fillna(0.0)


def ps_rank(df: pd.DataFrame) -> pd.Series:
    """市销率因子，无数据时返回0（占位）"""
    if "ps" not in df.columns:
        return pd.Series(0.0, index=df.index)
    return df["ps"].rank(pct=True).fillna(0.0)


def roe_rank(df: pd.DataFrame) -> pd.Series:
    """ROE因子，无数据时返回0（占位）"""
    if "roe" not in df.columns:
        return pd.Series(0.0, index=df.index)
    return df["roe"].rank(pct=True).fillna(0.0)


# ============================================================
# 市场环境因子 (3)
# ============================================================

def market_up_ratio(df: pd.DataFrame) -> pd.Series:
    """过去20日上涨天数占比 (pct_chg > 0)"""
    if "pct_chg" not in df.columns:
        return pd.Series(0.5, index=df.index)
    up_days = (df["pct_chg"] > 0).astype(float)
    return up_days.rolling(20, min_periods=1).mean()


def index_ret_5d(df: pd.DataFrame) -> pd.Series:
    """5日市场收益代理（个股代理，等 market_index 表接入后替换）"""
    return df["close"].pct_change(5)


def index_ret_20d(df: pd.DataFrame) -> pd.Series:
    """过去20日累计收益率"""
    return df["close"].pct_change(20)


# ============================================================
# 因子注册表
# ============================================================

ALL_FACTORS: dict[str, object] = {
    # 价格动量 (5)
    "ret_5d": ret_5d,
    "ret_10d": ret_10d,
    "ret_20d": ret_20d,
    "ret_60d": ret_60d,
    "momentum_20_60": momentum_20_60,
    # 反转因子 (5)
    "ret_1d": ret_1d,
    "ret_3d": ret_3d,
    "rsi_6": rsi_6,
    "rsi_14": rsi_14,
    "bb_reversal": bb_reversal,
    # 波动率 (4)
    "vol_5d": vol_5d,
    "vol_20d": vol_20d,
    "vol_ratio_5_20": vol_ratio_5_20,
    "atr_pct": atr_pct,
    # 成交量 (6)
    "vol_ma_ratio_5": vol_ma_ratio_5,
    "vol_ma_ratio_20": vol_ma_ratio_20,
    "vol_trend_5": vol_trend_5,
    "vol_trend_20": vol_trend_20,
    "amount_ratio": amount_ratio,
    "turnover_5d": turnover_5d,
    # 均线偏离 (4)
    "ma5_dev": ma5_dev,
    "ma20_dev": ma20_dev,
    "ma60_dev": ma60_dev,
    "ma_5_20_cross": ma_5_20_cross,
    # 资金流量 (4)
    "mfi_14": mfi_14,
    "obv_ratio": obv_ratio,
    "vwap_dev": vwap_dev,
    "money_flow_5d": money_flow_5d,
    # 技术形态 (5)
    "macd_hist": macd_hist,
    "kdj_k_dev": kdj_k_dev,
    "boll_pos": boll_pos,
    "pattern_count": pattern_count,
    "pattern_diversity": pattern_diversity,
    # 基本面 (4)
    "pe_rank": pe_rank,
    "pb_rank": pb_rank,
    "ps_rank": ps_rank,
    "roe_rank": roe_rank,
    # 市场环境 (3)
    "market_up_ratio": market_up_ratio,
    "index_ret_5d": index_ret_5d,
    "index_ret_20d": index_ret_20d,
}


# ============================================================
# 批量计算入口
# ============================================================

def compute_all_factors(df: pd.DataFrame) -> pd.DataFrame:
    """计算全部40个因子，返回 DataFrame，列名为因子名，索引与输入对齐"""
    factors: dict[str, pd.Series] = {}
    for name, func in ALL_FACTORS.items():
        try:
            factors[name] = func(df)
        except Exception:
            factors[name] = pd.Series(np.nan, index=df.index)
    result = pd.DataFrame(factors, index=df.index)
    return result.replace([np.inf, -np.inf], np.nan)
