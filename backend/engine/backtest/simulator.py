# smart-stock/backend/engine/backtest/simulator.py
from dataclasses import dataclass, field
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
                 stop_loss=-0.08) -> dict:
    acct = Account(cash=capital)

    dates = sorted(signal_df["trade_date"].unique())

    for date in dates:
        day_signals = signal_df[signal_df["trade_date"] == date]

        # 检查止损
        for code, pos in list(acct.positions.items()):
            if pos.shares <= 0:
                continue
            current_price = get_price(conn, code, date)
            if current_price is None:
                continue
            pnl_pct = current_price / pos.avg_cost - 1
            if pnl_pct <= stop_loss:
                sell_value = pos.shares * current_price * (1 - SLIPPAGE)
                commission = max(sell_value * COMMISSION_RATE, 5)
                tax = sell_value * STAMP_TAX_RATE
                acct.cash += sell_value - commission - tax
                acct.trades.append({
                    "ts_code": code, "date": date, "type": "sell",
                    "reason": "stop_loss",
                    "shares": pos.shares,
                    "price": current_price,
                    "pnl_pct": round(pnl_pct, 4),
                    "pnl": round(sell_value - pos.shares * pos.avg_cost - commission - tax, 2),
                })
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
