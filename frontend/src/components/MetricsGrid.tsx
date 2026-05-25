import React from "react";
import type { BacktestMetrics } from "../types";

function MetricCard({ label, value, format = "number" }: {
  label: string; value: number; format?: "percent" | "number" | "days";
}) {
  const display = format === "percent" ? `${(value * 100).toFixed(2)}%`
    : format === "days" ? `${value}d` : value.toFixed(4);
  return (
    <div style={{ padding: 12, background: "#1a1a2e", borderRadius: 6, textAlign: "center" }}>
      <div style={{ fontSize: 20, fontWeight: "bold", color: "#38bdf8" }}>{display}</div>
      <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>{label}</div>
    </div>
  );
}

export function MetricsGrid({ metrics }: { metrics: BacktestMetrics }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
      <MetricCard label="年化收益" value={metrics.annual_return} format="percent" />
      <MetricCard label="最大回撤" value={metrics.max_drawdown} format="percent" />
      <MetricCard label="夏普比率" value={metrics.sharpe_ratio} />
      <MetricCard label="胜率" value={metrics.win_rate} format="percent" />
      <MetricCard label="盈亏比" value={metrics.profit_loss_ratio} />
      <MetricCard label="总收益" value={metrics.total_return} format="percent" />
      <MetricCard label="交易次数" value={metrics.total_trades} />
      <MetricCard label="最大回撤天" value={metrics.max_dd_days} format="days" />
    </div>
  );
}
