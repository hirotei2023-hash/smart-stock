import React from "react";

export function AlertBadge({ severity }: { severity: "warning" | "danger" | "info" }) {
  const colors = {
    danger: { bg: "#7f1d1d", text: "#fca5a5", label: "危险" },
    warning: { bg: "#78350f", text: "#fcd34d", label: "警告" },
    info: { bg: "#1e3a5f", text: "#93c5fd", label: "提示" },
  };
  const c = colors[severity];
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 10, fontSize: 11,
      background: c.bg, color: c.text, fontWeight: 600,
    }}>{c.label}</span>
  );
}
