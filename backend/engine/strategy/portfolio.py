"""策略组合管理器 — 多策略选股 + 权重拼接 + 行业集中度检查"""
import numpy as np
import pandas as pd
from backend.engine.strategy.mean_reversion import MeanReversionStrategy
from backend.engine.risk.stop_manager import (
    DynamicStopManager, VolatilityPositionSizer, MarketRegimeFilter,
)
from backend.config import INITIAL_CAPITAL


class PortfolioManager:
    def __init__(self):
        self.mean_reversion = MeanReversionStrategy(lookback=20, top_k=15, rsi_threshold=40)
        self.strategy_weights = {
            "mean_reversion": 0.50,
            "lightgbm": 0.40,
            "pattern": 0.10,
        }
        self.sector_limit = 0.30
        self.max_positions = 8
        self.stop_manager = DynamicStopManager()
        self.sizer = VolatilityPositionSizer()
        self.regime_filter = MarketRegimeFilter()

    def allocate(self, date, factor_df, signal_df, sector_map, market_df, cash) -> list[dict]:
        """核心分配逻辑：各策略独立选股 → 合并 → 风控过滤 → 返回订单列表"""
        orders = []

        # 市场状态 → 仓位上限
        regime = self.regime_filter.get_regime(market_df) if market_df is not None else "neutral"
        allocation_pct = self.regime_filter.get_allocation(regime)
        target_capital = cash * allocation_pct

        # 1. 均值反转选股
        try:
            mr_df = self.mean_reversion.rank(factor_df)
            if not mr_df.empty:
                mr_df["strategy"] = "mean_reversion"
        except Exception:
            mr_df = pd.DataFrame()

        # 2. LightGBM 选股 (signal_df 已包含 composite_score)
        if signal_df is not None and not signal_df.empty:
            lgb_df = signal_df.nlargest(15, "composite_score").copy()
            lgb_df["strategy"] = "lightgbm"
            lgb_df["score"] = lgb_df["composite_score"]
        else:
            lgb_df = pd.DataFrame()

        # 3. 合并候选
        candidates = []
        seen = set()

        # 去重逻辑：同只股票取最高分策略
        for df_src, weight in [(mr_df, self.strategy_weights["mean_reversion"]),
                                (lgb_df, self.strategy_weights["lightgbm"])]:
            if df_src.empty:
                continue
            for _, row in df_src.iterrows():
                code = row.get("ts_code")
                if code in seen:
                    continue
                seen.add(code)
                candidates.append({
                    "ts_code": code,
                    "score": float(row.get("score", 50)),
                    "strategy": row.get("strategy", "unknown"),
                    "weight": weight,
                })

        if not candidates:
            return orders

        candidates.sort(key=lambda x: x["score"] + x["weight"] * 20, reverse=True)
        positions_needed = min(self.max_positions, len(candidates))
        candidates = candidates[:positions_needed]

        # 4. 行业集中度检查
        position_count_by_sector = {}
        filtered = []

        for c in candidates:
            sector = sector_map.get(c["ts_code"], "未知")
            current = position_count_by_sector.get(sector, 0)
            if current >= int(self.max_positions * self.sector_limit):
                continue
            filtered.append(c)
            position_count_by_sector[sector] = current + 1

        # 5. 生成订单
        per_position_capital = target_capital / max(len(filtered), 1)

        for c in filtered[:self.max_positions]:
            orders.append({
                "ts_code": c["ts_code"],
                "strategy": c["strategy"],
                "score": c["score"],
                "capital_allocated": round(per_position_capital, 2),
            })

        return orders

    def get_stops_for_positions(self, positions: dict, current_prices: dict, atrs: dict) -> dict:
        """返回每个持仓的止损价"""
        stops = {}
        for code, pos in positions.items():
            price = current_prices.get(code)
            atr = atrs.get(code, price * 0.03 if price else 1)
            if price and pos.shares > 0:
                stops[code] = self.stop_manager.get_stop_price(
                    code, pos.avg_cost, price, atr
                )
        return stops
