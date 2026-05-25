import React, { useState, useEffect } from "react";
import { api } from "../api";
import type { AlertData, StockInfo } from "../types";
import { AlertBadge } from "../components/AlertBadge";

export function Alerts() {
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [watchlist, setWatchlist] = useState<StockInfo[]>([]);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<StockInfo[]>([]);

  useEffect(() => {
    api.getAlerts(100).then(setAlerts);
    api.getWatchlist().then(setWatchlist);
  }, []);

  const handleSearch = async () => {
    if (searchQ.trim()) {
      const results = await api.searchStocks(searchQ);
      setSearchResults(results);
    }
  };

  const handleAddWatch = async (tsCode: string, name: string) => {
    await api.addToWatchlist(tsCode, name);
    const updated = await api.getWatchlist();
    setWatchlist(updated);
  };

  const handleCheckAll = async () => {
    for (const item of watchlist) {
      await api.checkStock(item.ts_code);
    }
    const updated = await api.getAlerts(100);
    setAlerts(updated);
  };

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>⚡ 预警管理</h2>

      <div style={{
        padding: 16, background: "#1a1a2e", borderRadius: 8,
        border: "1px solid #1e293b", marginBottom: 16,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>关注列表 ({watchlist.length})</h3>
          <button onClick={handleCheckAll} style={{
            padding: "6px 16px", background: "#f59e0b", color: "#0f0f1a",
            border: "none", borderRadius: 4, cursor: "pointer", fontWeight: 600,
          }}>
            🔍 全部检查
          </button>
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="搜索股票..."
            style={{
              flex: 1, padding: "6px 10px", borderRadius: 4,
              border: "1px solid #334155", background: "#0f0f1a", color: "#e2e8f0",
            }}
          />
          <button onClick={handleSearch} style={{
            padding: "6px 12px", background: "#334155", color: "#e2e8f0",
            border: "none", borderRadius: 4, cursor: "pointer",
          }}>搜索</button>
        </div>

        {searchResults.length > 0 && (
          <div style={{ marginBottom: 8, fontSize: 13 }}>
            {searchResults.map((s) => (
              <div key={s.ts_code} style={{
                display: "flex", justifyContent: "space-between", padding: "4px 0",
              }}>
                <span>{s.ts_code} {s.name}</span>
                <button onClick={() => handleAddWatch(s.ts_code, s.name)} style={{
                  padding: "2px 12px", background: "#10b981", color: "#fff",
                  border: "none", borderRadius: 4, cursor: "pointer", fontSize: 12,
                }}>添加</button>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {watchlist.map((w) => (
            <span key={w.ts_code} style={{
              padding: "4px 10px", borderRadius: 14, fontSize: 12,
              background: "#1e293b", color: "#e2e8f0",
            }}>{w.name || w.ts_code}</span>
          ))}
          {watchlist.length === 0 && (
            <span style={{ color: "#64748b", fontSize: 13 }}>尚未添加关注股票</span>
          )}
        </div>
      </div>

      <h3 style={{ marginBottom: 12 }}>预警记录</h3>
      {alerts.map((a) => (
        <div key={a.id} style={{
          padding: 12, marginBottom: 8, background: "#1a1a2e",
          borderRadius: 8, border: "1px solid #1e293b",
          borderLeft: `3px solid ${a.severity === "danger" ? "#ef4444" : a.severity === "warning" ? "#f59e0b" : "#3b82f6"}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <span style={{ fontFamily: "monospace", marginRight: 8 }}>{a.ts_code}</span>
              <AlertBadge severity={a.severity} />
              <span style={{ marginLeft: 8 }}>{a.message}</span>
            </div>
            <span style={{ fontSize: 11, color: "#64748b" }}>{a.triggered_at}</span>
          </div>
          {a.suggestion && (
            <div style={{ marginTop: 8, fontSize: 13, color: "#fcd34d" }}>
              💡 {a.suggestion}
            </div>
          )}
        </div>
      ))}
      {alerts.length === 0 && (
        <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>
          暂无预警 🎉
        </div>
      )}
    </div>
  );
}
