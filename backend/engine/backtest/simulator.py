# smart-stock/backend/engine/backtest/simulator.py
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from backend.engine.data.schema import get_connection
from backend.engine.backtest.metrics import compute_all_metrics
from backend.config import (INITIAL_CAPITAL, COMMISSION_RATE, STAMP_TAX_RATE,
                             SLIPPAGE, SINGLE_POSITION_MAX, TOTAL_POSITION_MAX)


@dataclass
class Position:
    ts_code: str
    shares: int = 0
    avg_cost: float = 0.0


@dataclass
class Account:
    cash: float = INITIAL_CAPITAL
    positions: dict = field(default_factory=dict)
    trades: list = field(default_factory=list)
    equity_history: list = field(default_factory=list)


def get_price(conn, ts_code: str, trade_date: str, field="close") -> float | None:
    row = conn.execute(
        f"SELECT {field} FROM daily_kline WHERE ts_code=? AND trade_date=?",
        (ts_code, trade_date)
    ).fetchone()
    return row[0] if row else None


def run_backtest(conn, signal_df: pd.DataFrame,
                 capital=INITIAL_CAPITAL,
                 max_positions=5,
                 stop_loss=-0.08,
                 trailing_stop=0.05) -> dict:
    """V1 回测: 固定止损 + 回撤止盈"""
    acct = Account(cash=capital)
    dates = sorted(signal_df["trade_date"].unique())
    # 记录每只持仓的历史最高价（用于回撤止盈）
    highest_since_entry: dict[str, float] = {}

    for date in dates:
        day_signals = signal_df[signal_df["trade_date"] == date]

        # 检查止损 + 止盈
        for code, pos in list(acct.positions.items()):
            if pos.shares <= 0:
                continue
            current_price = get_price(conn, code, date)
            if current_price is None:
                continue

            # 更新历史最高价
            prev_high = highest_since_entry.get(code, pos.avg_cost)
            if current_price > prev_high:
                highest_since_entry[code] = current_price

            pnl_pct = current_price / pos.avg_cost - 1
            drawdown_from_peak = current_price / max(prev_high, pos.avg_cost) - 1

            reason = ""
            # 固定止损: 从入场价跌超 stop_loss
            if pnl_pct <= stop_loss:
                reason = "stop_loss"
            # 回撤止盈: 从最高点回撤超 trailing_stop（且已盈利）
            elif pnl_pct > 0 and drawdown_from_peak <= -trailing_stop:
                reason = "trailing_stop"

            if reason:
                sell_value = pos.shares * current_price * (1 - SLIPPAGE)
                commission = max(sell_value * COMMISSION_RATE, 5)
                tax = sell_value * STAMP_TAX_RATE
                acct.cash += sell_value - commission - tax
                acct.trades.append({
                    "ts_code": code, "date": date, "type": "sell",
                    "reason": reason,
                    "shares": pos.shares,
                    "price": current_price,
                    "pnl_pct": round(pnl_pct, 4),
                    "pnl": round(sell_value - pos.shares * pos.avg_cost - commission - tax, 2),
                })
                pos.shares = 0
                highest_since_entry.pop(code, None)

        # 处理买入信号
        buy_candidates = day_signals.sort_values("composite_score", ascending=False)
        current_positions = sum(1 for p in acct.positions.values() if p.shares > 0)

        for _, sig in buy_candidates.iterrows():
            if current_positions >= max_positions:
                break
            code = sig["ts_code"]
            if code in acct.positions and acct.positions[code].shares > 0:
                continue

            price = get_price(conn, code, date)
            if price is None:
                continue

            position_size = min(acct.cash * SINGLE_POSITION_MAX,
                                acct.cash * TOTAL_POSITION_MAX / max(max_positions, 1))
            shares = int(position_size / price / 100) * 100
            if shares < 100:
                continue

            cost = shares * price * (1 + SLIPPAGE)
            commission = max(cost * COMMISSION_RATE, 5)
            total_cost = cost + commission
            if total_cost > acct.cash:
                continue

            acct.cash -= total_cost
            acct.positions[code] = Position(code, shares, price)
            acct.trades.append({
                "ts_code": code, "date": date, "type": "buy",
                "shares": shares, "price": price, "pnl_pct": 0, "pnl": 0,
            })
            current_positions += 1

        # 每日计算权益
        equity = acct.cash
        for code, pos in acct.positions.items():
            if pos.shares > 0:
                p = get_price(conn, code, date)
                if p:
                    equity += pos.shares * p
        acct.equity_history.append({"date": date, "equity": equity})

    # 最终清仓
    last_date = dates[-1]
    for code, pos in acct.positions.items():
        if pos.shares > 0:
            p = get_price(conn, code, last_date)
            if p:
                sell_value = pos.shares * p * (1 - SLIPPAGE)
                commission = max(sell_value * COMMISSION_RATE, 5)
                tax = sell_value * STAMP_TAX_RATE
                acct.cash += sell_value - commission - tax
                acct.trades.append({
                    "ts_code": code, "date": last_date, "type": "sell",
                    "reason": "end", "shares": pos.shares, "price": p,
                    "pnl_pct": round(p / pos.avg_cost - 1, 4),
                    "pnl": round(sell_value - pos.shares * pos.avg_cost - commission - tax, 2),
                })
                pos.shares = 0

    equity_curve = pd.DataFrame(acct.equity_history).set_index("date")["equity"]
    metrics = compute_all_metrics(equity_curve, acct.trades)

    return {
        "metrics": metrics,
        "trades": acct.trades,
        "equity_curve": [{"date": d, "equity": e}
                         for d, e in zip(equity_curve.index, equity_curve.values)],
    }


def run_backtest_v2(conn, signal_df: pd.DataFrame,
                    capital=INITIAL_CAPITAL,
                    max_positions=8,
                    stop_loss=-0.08,
                    trailing_stop=0.05,
                    atr_mult=2.0) -> dict:
    """V2 回测: ATR 止损 + 追踪止损 + 波动率仓位 + 市场状态"""
    acct = Account(cash=capital)
    dates = sorted(signal_df["trade_date"].unique())

    from backend.engine.risk.stop_manager import (
        DynamicStopManager, VolatilityPositionSizer, MarketRegimeFilter,
    )

    stop_mgr = DynamicStopManager(atr_mult=atr_mult, trailing_pct=trailing_stop, profit_lock=0.10)
    sizer = VolatilityPositionSizer(target_vol=0.02, max_single=0.25, min_single=0.05)
    regime_filter = MarketRegimeFilter()

    # 加载市场指数用于 regime 判断
    market_df = pd.read_sql_query(
        "SELECT trade_date, close FROM daily_kline WHERE ts_code='000300' ORDER BY trade_date",
        conn
    ) if conn.execute("SELECT 1 FROM sqlite_master WHERE name='market_index'").fetchone() else pd.DataFrame()

    for date in dates:
        day_signals = signal_df[signal_df["trade_date"] == date]

        # 市场状态 → 仓位上限
        regime = regime_filter.get_regime(market_df) if not market_df.empty else "neutral"
        allocation = regime_filter.get_allocation(regime)
        active_capital = acct.cash * allocation

        # 检查止损 + 止盈
        for code, pos in list(acct.positions.items()):
            if pos.shares <= 0:
                continue
            current_price = get_price(conn, code, date)
            if current_price is None:
                continue

            atr = _calc_atr(conn, code, date)
            should_exit, reason = stop_mgr.should_exit(code, pos.avg_cost, current_price, atr)

            if should_exit or (current_price / pos.avg_cost - 1) <= stop_loss:
                reason = reason or "stop_loss"
                sell_value = pos.shares * current_price * (1 - SLIPPAGE)
                commission = max(sell_value * COMMISSION_RATE, 5)
                tax = sell_value * STAMP_TAX_RATE
                acct.cash += sell_value - commission - tax
                acct.trades.append({
                    "ts_code": code, "date": date, "type": "sell",
                    "reason": reason,
                    "shares": pos.shares,
                    "price": current_price,
                    "pnl_pct": round(current_price / pos.avg_cost - 1, 4),
                    "pnl": round(sell_value - pos.shares * pos.avg_cost - commission - tax, 2),
                    "strategy": getattr(pos, "strategy", ""),
                })
                stop_mgr.clear_position(code)
                pos.shares = 0

        # 处理买入信号
        buy_candidates = day_signals.sort_values("composite_score", ascending=False)
        current_positions = sum(1 for p in acct.positions.values() if p.shares > 0)

        for _, sig in buy_candidates.iterrows():
            if current_positions >= max_positions:
                break
            code = sig["ts_code"]
            if code in acct.positions and acct.positions[code].shares > 0:
                continue

            price = get_price(conn, code, date)
            if price is None:
                continue

            # 波动率仓位
            atr = _calc_atr(conn, code, date)
            position_pct = sizer.get_position_pct(price, atr)
            position_capital = min(active_capital * position_pct,
                                   acct.cash * SINGLE_POSITION_MAX)

            shares = int(position_capital / price / 100) * 100
            if shares < 100:
                continue

            cost = shares * price * (1 + SLIPPAGE)
            commission = max(cost * COMMISSION_RATE, 5)
            total_cost = cost + commission
            if total_cost > acct.cash:
                continue

            acct.cash -= total_cost
            pos = Position(code, shares, price)
            pos.strategy = sig.get("strategy", "")
            acct.positions[code] = pos
            stop_mgr.init_position(code, price, atr)

            acct.trades.append({
                "ts_code": code, "date": date, "type": "buy",
                "shares": shares, "price": price, "pnl_pct": 0, "pnl": 0,
                "reason": "", "strategy": getattr(pos, "strategy", ""),
            })
            current_positions += 1

        # 每日权益计算
        equity = acct.cash
        for code, pos in acct.positions.items():
            if pos.shares > 0:
                p = get_price(conn, code, date)
                if p:
                    equity += pos.shares * p
        acct.equity_history.append({"date": date, "equity": equity})

    # 最终清仓
    last_date = dates[-1]
    for code, pos in acct.positions.items():
        if pos.shares > 0:
            p = get_price(conn, code, last_date)
            if p:
                sell_value = pos.shares * p * (1 - SLIPPAGE)
                commission = max(sell_value * COMMISSION_RATE, 5)
                tax = sell_value * STAMP_TAX_RATE
                acct.cash += sell_value - commission - tax
                acct.trades.append({
                    "ts_code": code, "date": last_date, "type": "sell",
                    "reason": "end", "shares": pos.shares, "price": p,
                    "pnl_pct": round(p / pos.avg_cost - 1, 4),
                    "pnl": round(sell_value - pos.shares * pos.avg_cost - commission - tax, 2),
                    "strategy": getattr(pos, "strategy", ""),
                })
                pos.shares = 0

    equity_curve = pd.DataFrame(acct.equity_history).set_index("date")["equity"]
    metrics = compute_all_metrics(equity_curve, acct.trades)

    return {
        "metrics": metrics,
        "trades": acct.trades,
        "equity_curve": [{"date": d, "equity": e}
                         for d, e in zip(equity_curve.index, equity_curve.values)],
    }


def _calc_atr(conn, ts_code: str, trade_date: str, period=14) -> float:
    """计算单只股票在某个日期的 ATR"""
    rows = conn.execute(
        """SELECT high, low, close FROM daily_kline
           WHERE ts_code=? AND trade_date <= ?
           ORDER BY trade_date DESC LIMIT ?""",
        (ts_code, trade_date, period + 1)
    ).fetchall()
    if len(rows) < 2:
        return 0.02  # default 2%

    rows = list(reversed(rows))
    trs = []
    for i in range(1, len(rows)):
        h, l, c_prev = rows[i]["high"], rows[i]["low"], rows[i - 1]["close"]
        tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
        trs.append(tr)

    return float(np.mean(trs)) if trs else 0.02
