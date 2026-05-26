import React from "react";

const NAV_ITEMS = [
  { label: "信号看板", key: "dashboard" },
  { label: "回测中心", key: "backtest" },
  { label: "涨幅排行", key: "ranking" },
  { label: "预警管理", key: "alerts" },
];

export function Layout({
  active,
  onNavigate,
  children,
}: {
  active: string;
  onNavigate: (key: string) => void;
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", height: "100vh", background: "#0f0f1a", color: "#e2e8f0" }}>
      <nav style={{
        width: 180, flexShrink: 0, borderRight: "1px solid #1e293b",
        padding: "20px 0", display: "flex", flexDirection: "column",
      }}>
        <h2 style={{ padding: "0 16px", fontSize: 18, marginBottom: 24, color: "#38bdf8" }}>
          📈 SmartStock
        </h2>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            onClick={() => onNavigate(item.key)}
            style={{
              padding: "10px 16px", textAlign: "left", border: "none",
              background: active === item.key ? "#1e293b" : "transparent",
              color: active === item.key ? "#38bdf8" : "#94a3b8",
              cursor: "pointer", fontSize: 14,
              borderLeft: active === item.key ? "3px solid #38bdf8" : "3px solid transparent",
            }}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <main style={{ flex: 1, overflow: "auto", padding: 24 }}>{children}</main>
    </div>
  );
}
