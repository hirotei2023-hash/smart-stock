"""风控模块: 动态止盈止损 + 波动率仓位管理 + 市场状态过滤"""
import numpy as np
import pandas as pd
from typing import Tuple


# ============================================================
# 动态止盈止损管理器
# ============================================================

class DynamicStopManager:
    """动态止盈止损管理器

    结合 ATR 初始止损、追踪止损和利润锁定三种机制，
    根据当前盈亏状态动态调整止损价位。
    内部追踪每只持仓的入场价和历史最高价。
    """

    def __init__(self, atr_mult: float = 2.0, trailing_pct: float = 0.05,
                 profit_lock: float = 0.10):
        self.atr_mult = atr_mult
        self.trailing_pct = trailing_pct
        self.profit_lock = profit_lock
        self._positions: dict[str, dict] = {}  # code -> {entry_price, highest}

    def init_position(self, code: str, entry_price: float, atr: float):
        """注册新持仓"""
        self._positions[code] = {
            "entry_price": entry_price,
            "highest": entry_price,
            "atr": atr,
        }

    def clear_position(self, code: str):
        """清除已平仓持仓"""
        self._positions.pop(code, None)

    def should_exit(self, code: str, entry_price: float,
                    current_price: float, atr: float) -> Tuple[bool, str]:
        """判断是否应平仓（与 simulator 调用签名一致）"""
        pos = self._positions.get(code)
        if pos is None:
            return False, ""

        # 更新历史最高价
        if current_price > pos["highest"]:
            pos["highest"] = current_price

        # 计算 ATR 止损价
        atr_stop = entry_price - atr * self.atr_mult

        # 追踪止损：从最高点回撤 trailing_pct
        trailing_stop = pos["highest"] * (1.0 - self.trailing_pct)

        # 利润锁定：盈利超阈值后止损上提到成本价
        pnl_pct = current_price / entry_price - 1.0
        if pnl_pct > self.profit_lock:
            stop_price = max(atr_stop, trailing_stop, entry_price)
        else:
            stop_price = max(atr_stop, trailing_stop)

        if current_price <= stop_price:
            if pnl_pct > 0:
                return True, "trailing_stop"
            elif current_price <= entry_price - atr * self.atr_mult:
                return True, "atr_stop"
            else:
                return True, "profit_lock"

        return False, ""


# ============================================================
# 波动率仓位管理器
# ============================================================

class VolatilityPositionSizer:
    """波动率仓位管理

    根据 ATR 衡量的波动率倒算仓位：高波动 → 小仓位，低波动 → 大仓位，
    使每笔持仓对组合的波动贡献保持稳定。
    """

    def __init__(self, target_vol: float = 0.02, max_single: float = 0.25,
                 min_single: float = 0.05):
        """
        Parameters
        ----------
        target_vol : float
            目标波动贡献，默认 2%
        max_single : float
            单票最大仓位，默认 25%
        min_single : float
            单票最小仓位，默认 5%
        """
        self.target_vol = target_vol
        self.max_single = max_single
        self.min_single = min_single

    def get_position_pct(self, current_price: float, atr: float) -> float:
        """根据波动率计算建议仓位比例

        Parameters
        ----------
        current_price : float
            当前价格
        atr : float
            当前 ATR 值

        Returns
        -------
        float
            建议仓位比例，在 [min_single, max_single] 之间
        """
        # 波动率 = ATR / 价格
        vol = atr / max(current_price, 1e-9)
        if vol <= 0:
            return self.min_single

        # 目标波动贡献 / 个股波动率 → 仓位
        pct = self.target_vol / vol
        return float(np.clip(pct, self.min_single, self.max_single))


# ============================================================
# 市场状态过滤器
# ============================================================

class MarketRegimeFilter:
    """市场状态过滤

    使用指数 K 线判断当前市场处于牛市/中性/熊市/危机，
    并据此调整整体仓位上限。
    """

    @staticmethod
    def get_regime(market_df: pd.DataFrame) -> str:
        """用指数K线判断市场状态

        Parameters
        ----------
        market_df : pd.DataFrame
            需包含 close 列，至少应提供120条数据。
            不足60条时返回 "neutral"。

        Returns
        -------
        str
            "bull" | "neutral" | "bear" | "crisis"

        Notes
        -----
        判断逻辑:
        - 价格 > MA60 且 MA20 斜率 > 1% → bull
        - 价格 > MA60 且 MA20 斜率 <= 1% → neutral
        - 价格 <= MA60 且 MA20 斜率 > -2% → bear
        - 价格 <= MA60 且 MA20 斜率 <= -2% → crisis
        """
        if len(market_df) < 60:
            return "neutral"

        close = market_df["close"]
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()

        latest = close.iloc[-1]
        ma60_latest = ma60.iloc[-1]

        # MA20 斜率：过去20个交易日的相对变化
        ma20_slope = 0.0
        if len(ma20) >= 20:
            ma20_20d_ago = ma20.iloc[-20]
            if ma20_20d_ago > 0:
                ma20_slope = ma20.iloc[-1] / ma20_20d_ago - 1.0

        # 状态判断
        if latest > ma60_latest and ma20_slope > 0.01:
            return "bull"
        elif latest > ma60_latest and ma20_slope <= 0.01:
            return "neutral"
        elif latest <= ma60_latest and ma20_slope > -0.02:
            return "bear"
        else:
            return "crisis"

    @staticmethod
    def get_allocation(regime: str) -> float:
        """根据市场状态返回建议仓位上限

        Parameters
        ----------
        regime : str
            "bull" | "neutral" | "bear" | "crisis"

        Returns
        -------
        float
            建议仓位上限比例
        """
        alloc_map = {
            "bull":    0.80,
            "neutral": 0.60,
            "bear":    0.30,
            "crisis":  0.00,
        }
        return alloc_map.get(regime, 0.50)
