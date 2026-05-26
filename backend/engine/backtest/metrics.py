# smart-stock/backend/engine/backtest/metrics.py
import numpy as np
import pandas as pd


def annual_return(daily_returns: pd.Series) -> float:
    total = (1 + daily_returns).prod()
    years = len(daily_returns) / 252
    return float(total ** (1 / max(years, 0.01)) - 1)


def max_drawdown(equity_curve: pd.Series) -> dict:
    peak = equity_curve.cummax()
    drawdown = (equity_curve - peak) / peak
    max_dd = float(drawdown.min())

    in_dd = drawdown < 0
    dd_periods = []
    count = 0
    for b in in_dd:
        if b:
            count += 1
        else:
            if count > 0:
                dd_periods.append(count)
            count = 0
    if count > 0:
        dd_periods.append(count)

    return {
        "max_drawdown": round(max_dd, 4),
        "max_dd_days": max(dd_periods) if dd_periods else 0,
        "avg_dd_days": round(np.mean(dd_periods), 1) if dd_periods else 0,
    }


def sharpe_ratio(daily_returns: pd.Series, risk_free=0.03) -> float:
    excess = daily_returns - risk_free / 252
    if excess.std() < 1e-9:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(252))


def calmar_ratio(annual_ret: float, max_dd: float) -> float:
    if abs(max_dd) < 1e-9:
        return 0.0
    return round(annual_ret / abs(max_dd), 4)


def win_rate(trades: list[dict]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t["pnl"] > 0)
    return round(wins / len(trades), 4)


def profit_loss_ratio(trades: list[dict]) -> float:
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [abs(t["pnl"]) for t in trades if t["pnl"] < 0]
    if not losses or not wins:
        return 0.0
    return round(float(np.mean(wins) / np.mean(losses)), 4)


def compute_all_metrics(equity_curve: pd.Series, trades: list[dict]) -> dict:
    daily_ret = equity_curve.pct_change().dropna()
    ann_ret = annual_return(daily_ret)
    dd = max_drawdown(equity_curve)
    return {
        "annual_return": round(ann_ret, 4),
        "max_drawdown": dd["max_drawdown"],
        "max_dd_days": dd["max_dd_days"],
        "sharpe_ratio": round(sharpe_ratio(daily_ret), 4),
        "calmar_ratio": calmar_ratio(ann_ret, dd["max_drawdown"]),
        "win_rate": win_rate(trades),
        "profit_loss_ratio": profit_loss_ratio(trades),
        "total_trades": len(trades),
        "total_return": round(float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1), 4),
    }
