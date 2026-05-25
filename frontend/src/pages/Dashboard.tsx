import React, { useState, useEffect, useCallback } from "react";
import { api } from "../api";
import type { SignalData, SummaryData, KlineData } from "../types";
import { KlineChart } from "../components/KlineChart";
import { SignalPanel } from "../components/SignalPanel";

export function Dashboard() {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [signals, setSignals] = useState<SignalData[]>([]);
  const [selectedStock, setSelectedStock] = useState<string>("");
  const [selectedSignal, setSelectedSignal] = useState<SignalData | null>(null);
  const [klineData, setKlineData] = useState<KlineData[]>([]);

  useEffect(() => {
    api.getTodaySummary().then(setSummary);
    api.getTodaySignals(50, 60).then(setSignals);
  }, []);

  const loadKline = useCallback(async (tsCode: string) => {
    setSelectedStock(tsCode);
    const data = await api.getKline(tsCode, 120);
    setKlineData(data);
  }, []);

  const handleSignalClick = (s: SignalData) => {
    setSelectedSignal(s);
    loadKline(s.ts_code);
  };

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { label: "今日信号均分", value: summary?.avg_score ?? "-", color: "#38bdf8" },
          { label: "高分信号数", value: summary?.high_signal_count ?? "-", color: "#10b981" },
          { label: "市场环境", value: "震荡", color: "#f59e0b" },
          { label: "活跃预警", value: summary?.active_alerts ?? "-", color: "#ef4444" },
        ].map((card) => (
          <div key={card.label} style={{
            padding: 16, background: "#1a1a2e", borderRadius: 8,
            border: "1px solid #1e293b", textAlign: "center",
          }}>
            <div style={{ fontSize: 28, fontWeight: "bold", color: card.color }}>
              {card.value}
            </div>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>{card.label}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ flex: 3 }}>
          <h3 style={{ marginBottom: 12 }}>
            {selectedStock ? `📈 ${selectedStock}` : "选择信号查看K线"}
          </h3>
          <KlineChart data={klineData} height={420} />
        </div>

        <div style={{ flex: 2 }}>
          {selectedSignal ? (
            <SignalPanel signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
          ) : (
            <div style={{ padding: 20, color: "#64748b", textAlign: "center" }}>
              点击右侧信号查看详情
            </div>
          )}
        </div>
      </div>

      <div style={{ marginTop: 20 }}>
        <h3 style={{ marginBottom: 12 }}>🔥 今日信号 (评分 ≥ 60)</h3>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "#64748b", fontSize: 12, textAlign: "left" }}>
              <th style={{ padding: 8 }}>代码</th>
              <th style={{ padding: 8 }}>名称</th>
              <th style={{ padding: 8 }}>评分</th>
              <th style={{ padding: 8 }}>识别形态</th>
              <th style={{ padding: 8 }}>5日概率</th>
              <th style={{ padding: 8 }}>20日概率</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((s) => (
              <tr key={s.id}
                onClick={() => handleSignalClick(s)}
                style={{
                  cursor: "pointer", borderTop: "1px solid #1e293b",
                  background: selectedSignal?.id === s.id ? "#1e293b" : "transparent",
                }}>
                <td style={{ padding: 8, fontFamily: "monospace" }}>{s.ts_code}</td>
                <td style={{ padding: 8 }}>{s.name}</td>
                <td style={{ padding: 8, color: s.composite_score >= 80 ? "#10b981" : "#f59e0b" }}>
                  {s.composite_score}
                </td>
                <td style={{ padding: 8, fontSize: 12 }}>
                  {(() => { try { return JSON.parse(s.rule_signals).slice(0, 3).join(", "); } catch { return ""; } })()}
                </td>
                <td style={{ padding: 8 }}>{(s.up_5d_prob * 100).toFixed(0)}%</td>
                <td style={{ padding: 8 }}>{(s.up_20d_prob * 100).toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        {signals.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>
            暂无数据，请先运行信号扫描
          </div>
        )}
      </div>
    </div>
  );
}
