import React from "react";
import type { SignalData } from "../types";

function parseSignals(jsonStr: string): string[] {
  try {
    const parsed = JSON.parse(jsonStr);
    if (Array.isArray(parsed)) return parsed;
    // 新评分格式: {vp_score, char_score, limit_up_year, limit_up_month, vol_ratio}
    return [
      `量价${parsed.vp_score ?? "?"}`,
      `股性${parsed.char_score ?? "?"}`,
      `年涨停${parsed.limit_up_year ?? 0}次`,
      `月涨停${parsed.limit_up_month ?? 0}次`,
      `量比${parsed.vol_ratio ?? 0}x`,
    ];
  } catch { return []; }
}

export function SignalPanel({ signal, onClose }: { signal: SignalData; onClose: () => void }) {
  const rules = parseSignals(signal.rule_signals);
  const scoreColor = signal.composite_score >= 80 ? "#10b981"
    : signal.composite_score >= 65 ? "#f59e0b" : "#ef4444";

  return (
    <div style={{
      padding: 20, background: "#1a1a2e", borderRadius: 8,
      border: "1px solid #1e293b", minWidth: 280,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>{signal.name || signal.ts_code}</h3>
        <button onClick={onClose}
          style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer" }}>
          ✕
        </button>
      </div>

      <div style={{ textAlign: "center", marginBottom: 16 }}>
        <div style={{ fontSize: 42, fontWeight: "bold", color: scoreColor }}>
          {signal.composite_score}
        </div>
        <div style={{ color: "#64748b", fontSize: 12 }}>综合评分</div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <div style={{ color: "#64748b", fontSize: 12, marginBottom: 4 }}>识别形态</div>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {rules.map((r) => (
            <span key={r} style={{
              padding: "2px 8px", borderRadius: 12, fontSize: 12,
              background: "#1e293b", color: "#38bdf8",
            }}>{r}</span>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 12, color: "#64748b" }}>置信度</div>
          <div style={{ fontSize: 18 }}>{(signal.confidence * 100).toFixed(0)}%</div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: "#64748b" }}>5日上涨概率</div>
          <div style={{ fontSize: 18, color: signal.up_5d_prob > 0.5 ? "#10b981" : "#ef4444" }}>
            {(signal.up_5d_prob * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      <div>
        <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>20日上涨概率</div>
        <div style={{
          height: 6, borderRadius: 3, background: "#1e293b", overflow: "hidden",
        }}>
          <div style={{
            width: `${signal.up_20d_prob * 100}%`, height: "100%",
            background: "linear-gradient(90deg, #ef4444, #f59e0b, #10b981)",
            borderRadius: 3,
          }} />
        </div>
        <div style={{ textAlign: "right", fontSize: 12, color: "#64748b", marginTop: 2 }}>
          {(signal.up_20d_prob * 100).toFixed(0)}%
        </div>
      </div>
    </div>
  );
}
