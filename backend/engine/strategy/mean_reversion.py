"""A股短期均值反转策略

核心逻辑: A股短期(5-20日)存在显著的反转效应 ——
涨多了会跌，跌多了会涨。尤其在小盘股中更为明显。

策略: 买入最近20日跌幅最大的股票中RSI超卖+放量的那些，
持有5-20个交易日，赚取反弹收益。
"""
import numpy as np
import pandas as pd


class MeanReversionStrategy:
    """A股短期均值反转策略"""

    def __init__(self, lookback: int = 20, top_k: int = 20,
                 rsi_threshold: float = 40, vol_filter: bool = True):
        """
        Parameters
        ----------
        lookback : int
            回看天数，默认20
        top_k : int
            每期最多选多少只
        rsi_threshold : float
            RSI上限（低于此值视为超卖）
        vol_filter : bool
            是否启用放量过滤
        """
        self.lookback = lookback
        self.top_k = top_k
        self.rsi_threshold = rsi_threshold
        self.vol_filter = vol_filter

    # ------------------------------------------------------------------
    # 因子计算 (静态方法, 方便外部复用)
    # ------------------------------------------------------------------

    @staticmethod
    def calc_ret_n(df: pd.DataFrame, n: int, price_col: str = "close") -> pd.Series:
        """计算 N 日收益率"""
        return df.groupby("ts_code")[price_col].pct_change(n)

    @staticmethod
    def calc_rsi(df: pd.DataFrame, period: int = 14, price_col: str = "close") -> pd.Series:
        """计算 RSI 指标"""
        delta = df.groupby("ts_code")[price_col].diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.groupby("ts_code").transform(
            lambda x: x.ewm(alpha=1/period, adjust=False).mean()
        )
        avg_loss = loss.groupby("ts_code").transform(
            lambda x: x.ewm(alpha=1/period, adjust=False).mean()
        )
        rs = avg_gain / (avg_loss + 1e-9)
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def calc_vol_ratio(df: pd.DataFrame, short: int = 5, long: int = 20,
                       vol_col: str = "volume") -> pd.Series:
        """计算成交量放大比率：短期均量 / 长期均量"""
        vol_short = df.groupby("ts_code")[vol_col].transform(
            lambda x: x.rolling(short, min_periods=1).mean()
        )
        vol_long = df.groupby("ts_code")[vol_col].transform(
            lambda x: x.rolling(long, min_periods=1).mean()
        )
        return vol_short / (vol_long + 1e-9)

    # ------------------------------------------------------------------
    # 主排名方法
    # ------------------------------------------------------------------

    def rank(self, df_pool: pd.DataFrame) -> pd.DataFrame:
        """对股票池打分排序

        Parameters
        ----------
        df_pool : pd.DataFrame
            每行一只股票在某日的最新数据。
            必须包含: ts_code, close, volume
            可选包含: pct_chg, high, low
            按 ts_code 分组，每组至少有 lookback+20 条历史数据。

        Returns
        -------
        pd.DataFrame
            columns: ts_code, score, ret_Nd, rsi, vol_ratio, rank
            按 score 降序排列，只返回 top_k 只
        """
        # --- 1. 按 ts_code 取每组的最后一行（横截面） ---
        latest = df_pool.groupby("ts_code").tail(1).copy()

        # --- 2. 计算或读取 ret_{lookback}d ---
        ret_col = f"ret_{self.lookback}d"
        if ret_col not in df_pool.columns and "close" in df_pool.columns:
            df_pool[ret_col] = self.calc_ret_n(df_pool, self.lookback, "close")

        if ret_col in df_pool.columns:
            ret_series = df_pool.groupby("ts_code")[ret_col].last()
            latest[ret_col] = latest["ts_code"].map(ret_series)
        else:
            # 兜底：当前日涨跌幅仅作参考
            if "pct_chg" in latest.columns:
                latest[ret_col] = latest["pct_chg"] / 100.0
            else:
                return pd.DataFrame(columns=["ts_code", "score", f"ret_{self.lookback}d",
                                             "rsi_14", "vol_ma_ratio_5", "rank"])

        # --- 3. 计算或读取 RSI ---
        rsi_col = "rsi_14"
        if rsi_col not in df_pool.columns and "close" in df_pool.columns:
            df_pool[rsi_col] = self.calc_rsi(df_pool, period=14, price_col="close")

        if rsi_col in df_pool.columns:
            rsi_series = df_pool.groupby("ts_code")[rsi_col].last()
            latest[rsi_col] = latest["ts_code"].map(rsi_series)
        else:
            latest[rsi_col] = 50.0

        # --- 4. 计算或读取量比 ---
        vol_ratio_col = "vol_ma_ratio_5"
        if vol_ratio_col not in df_pool.columns and "volume" in df_pool.columns:
            df_pool[vol_ratio_col] = self.calc_vol_ratio(df_pool, short=5, long=20, vol_col="volume")

        if vol_ratio_col in df_pool.columns:
            vol_ratio_series = df_pool.groupby("ts_code")[vol_ratio_col].last()
            latest[vol_ratio_col] = latest["ts_code"].map(vol_ratio_series)
        else:
            latest[vol_ratio_col] = 1.0

        # --- 5. 过滤 ---
        # 只考虑下跌的股票
        mask = (latest[ret_col] < 0) & (latest[rsi_col] < self.rsi_threshold)
        if self.vol_filter:
            mask = mask & (latest[vol_ratio_col] > 1.2)

        candidates = latest.loc[mask].dropna(subset=[ret_col, rsi_col, vol_ratio_col]).copy()

        if candidates.empty:
            return pd.DataFrame(columns=["ts_code", "score", f"ret_{self.lookback}d",
                                         "rsi_14", "vol_ma_ratio_5", "rank"])

        # --- 6. 综合打分 ---
        # 跌得越多(-ret)、越超卖(1-rsi/100)、量越大 → 分数越高
        candidates["score"] = (
            -candidates[ret_col]                     # 跌幅（正值）
            * (1.0 - candidates[rsi_col] / 100.0)    # 超卖程度
            * candidates[vol_ratio_col]               # 放量程度
        )

        # --- 7. 取 top_k ---
        result = candidates.nlargest(self.top_k, "score").copy()
        result["rank"] = range(1, len(result) + 1)

        out_cols = ["ts_code", "score", f"ret_{self.lookback}d", "rsi_14", "vol_ma_ratio_5", "rank"]
        return result[out_cols].reset_index(drop=True)
