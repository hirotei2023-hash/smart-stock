import React, { useState } from "react";
import { createChart, ColorType } from "lightweight-charts";
import { api } from "../api";
import type { BacktestResult } from "../types";
import { MetricsGrid } from "../components/MetricsGrid";

export function Backtest() {
  const [config, setConfig] = useState({
    start_date: "2024-01-01", end_date: "2026-05-25",
    capital: "100000", max_positions: "5", stop_loss: "-0.08",
  });
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const chartRef = React.useRef<HTMLDivElement>(null);

  const runBacktest = async () => {
    setLoading(true);
    const res = await api.runBacktest(config);
    setResult(res);
    setLoading(false);

    if (chartRef.current && res.equity_curve?.length > 0) {
      chartRef.current.innerHTML = "";
      const chart = createChart(chartRef.current, {
        height: 300,
        layout: { background: { type: ColorType.Solid, color: "#0f0f1a" }, textColor: "#94a3b8" },
        grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
        timeScale: { borderColor: "#1e293b" },
        rightPriceScale: { borderColor: "#1e293b" },
      });
      const line = chart.addLineSeries({ color: "#38bdf8", lineWidth: 2 });
      line.setData(res.equity_curve.map((p) => ({ time: p.date, value: p.equity })));
      chart.timeScale().fitContent();
    }
  };

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>📈 回测中心</h2>

      <div style={{
        padding: 16, background: "#1a1a2e", borderRadius: 8,
        border: "1px solid #1e293b", marginBottom: 16,
        display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap",
      }}>
        {[
          { label: "起始日期", key: "start_date" },
          { label: "结束日期", key: "end_date" },
          { label: "初始资金", key: "capital" },
          { label: "最大持仓", key: "max_positions" },
          { label: "止损线 %", key: "stop_loss" },
        ].map((f) => (
          <div key={f.key}>
            <label style={{ fontSize: 11, color: "#64748b", display: "block" }}>{f.label}</label>
            <input
              value={(config as any)[f.key]}
              onChange={(e) => setConfig({ ...config, [f.key]: e.target.value })}
              style={{
                padding: "6px 10px", borderRadius: 4, border: "1px solid #334155",
                background: "#0f0f1a", color: "#e2e8f0", width: 130,
              }}
            />
          </div>
        ))}
        <button onClick={runBacktest} disabled={loading} style={{
          padding: "8px 24px", background: "#38bdf8", color: "#0f0f1a",
          border: "none", borderRadius: 4, cursor: "pointer", fontWeight: 600,
        }}>
          {loading ? "运行中..." : "▶ 开始回测"}
        </button>
      </div>

      {result && (
        <>
          <MetricsGrid metrics={result.metrics} />
          <div ref={chartRef} style={{ marginTop: 16, borderRadius: 8, overflow: "hidden" }} />

          <h3 style={{ marginTop: 20, marginBottom: 8 }}>交易记录</h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ color: "#64748b", textAlign: "left" }}>
                <th style={{ padding: 6 }}>日期</th>
                <th style={{ padding: 6 }}>代码</th>
                <th style={{ padding: 6 }}>操作</th>
                <th style={{ padding: 6 }}>股数</th>
                <th style={{ padding: 6 }}>价格</th>
                <th style={{ padding: 6 }}>收益</th>
                <th style={{ padding: 6 }}>原因</th>
              </tr>
            </thead>
            <tbody>
              {result.trades.map((t, i) => (
                <tr key={i} style={{ borderTop: "1px solid #1e293b" }}>
                  <td style={{ padding: 6 }}>{t.date}</td>
                  <td style={{ padding: 6, fontFamily: "monospace" }}>{t.ts_code}</td>
                  <td style={{ padding: 6, color: t.type === "buy" ? "#10b981" : "#ef4444" }}>
                    {t.type === "buy" ? "买入" : "卖出"}
                  </td>
                  <td style={{ padding: 6 }}>{t.shares}</td>
                  <td style={{ padding: 6 }}>{t.price?.toFixed(2)}</td>
                  <td style={{ padding: 6, color: t.pnl > 0 ? "#10b981" : "#ef4444" }}>
                    {t.pnl !== 0 ? `${t.pnl.toFixed(2)}` : "-"}
                  </td>
                  <td style={{ padding: 6, fontSize: 12, color: "#64748b" }}>{t.reason || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
