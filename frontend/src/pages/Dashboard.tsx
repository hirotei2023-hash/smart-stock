import React, { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../api";
import type { SignalData, SummaryData, KlineData, StockInfo } from "../types";
import { KlineChart } from "../components/KlineChart";
import { SignalPanel } from "../components/SignalPanel";

type SortKey = "composite" | "vp" | "char";

function parseRule(s: SignalData) {
  try {
    const p = JSON.parse(s.rule_signals);
    return {
      vp_score: p.vp_score ?? 0,
      char_score: p.char_score ?? 0,
      limit_up_year: p.limit_up_year ?? 0,
      limit_up_month: p.limit_up_month ?? 0,
      vol_ratio: p.vol_ratio ?? 0,
    };
  } catch {
    return { vp_score: 0, char_score: 0, limit_up_year: 0, limit_up_month: 0, vol_ratio: 0 };
  }
}

export function Dashboard() {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [signals, setSignals] = useState<SignalData[]>([]);
  const [signalDates, setSignalDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState("");  // "" = 最新日期
  const [sortBy, setSortBy] = useState<SortKey>("composite");
  const [selectedStock, setSelectedStock] = useState("");
  const [selectedSignal, setSelectedSignal] = useState<SignalData | null>(null);
  const [klineData, setKlineData] = useState<KlineData[]>([]);
  const [klineError, setKlineError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<StockInfo[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // 加载可用日期列表
  useEffect(() => {
    api.getSignalDates().then((dates) => {
      setSignalDates(dates);
      if (dates.length > 0) setSelectedDate(dates[0]);  // 默认最新
    });
  }, []);

  // 日期变化时重新加载
  useEffect(() => {
    const dateParam = selectedDate || undefined;
    api.getTodaySummary().then(setSummary);  // summary 暂时还用最新日期
    api.getTodaySignals(100, 40, dateParam).then(setSignals);
  }, [selectedDate]);

  // 搜索防抖
  useEffect(() => {
    if (searchQuery.trim().length < 1) {
      setSearchResults([]);
      setShowDropdown(false);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const results = await api.searchStocks(searchQuery.trim());
        setSearchResults(results);
        setShowDropdown(true);
      } catch { setSearchResults([]); }
    }, 200);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // 点击外部关闭下拉
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const loadKline = useCallback(async (tsCode: string) => {
    setSelectedStock(tsCode);
    setKlineError("");
    try {
      const data = await api.getKline(tsCode, 120);
      setKlineData(data);
    } catch (e: any) {
      setKlineError(e.message || "加载K线失败");
      setKlineData([]);
    }
  }, []);

  const handleSignalClick = (s: SignalData) => {
    setSelectedSignal(s);
    loadKline(s.ts_code);
  };

  // 排序
  const sortedSignals = [...signals].sort((a, b) => {
    if (sortBy === "composite") return b.composite_score - a.composite_score;
    const pa = parseRule(a), pb = parseRule(b);
    if (sortBy === "vp") return pb.vp_score - pa.vp_score;
    return pb.char_score - pa.char_score;
  });

  const thStyle: React.CSSProperties = {
    padding: "8px 6px", fontSize: 12, color: "#64748b", textAlign: "left" as const,
    cursor: "default", whiteSpace: "nowrap" as const,
  };
  const sortableTH: React.CSSProperties = {
    ...thStyle, cursor: "pointer", userSelect: "none" as const,
  };
  const activeTH: React.CSSProperties = {
    ...sortableTH, color: "#38bdf8", borderBottom: "2px solid #38bdf8",
  };

  return (
    <div>
      {/* ====== 顶部卡片 ====== */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { label: "信号均分", value: summary?.avg_score ?? "-", color: "#38bdf8" },
          { label: "高分信号数", value: summary?.high_signal_count ?? "-", color: "#10b981" },
          { label: "信号总数", value: summary?.total_signals ?? "-", color: "#f59e0b" },
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

      {/* ====== K线图 + 信号详情 ====== */}
      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ flex: 3 }}>
          {/* 搜索框 */}
          <div ref={searchRef} style={{ position: "relative", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索代码或名称..."
                style={{
                  flex: 1, padding: "8px 12px", borderRadius: 6,
                  border: "1px solid #334155", background: "#0f0f23",
                  color: "#e2e8f0", fontSize: 14, outline: "none",
                }}
                onFocus={() => { if (searchResults.length > 0) setShowDropdown(true); }}
              />
              {selectedStock && (
                <span style={{ fontSize: 14, color: "#38bdf8", whiteSpace: "nowrap" }}>
                  {selectedStock}
                  {klineData.length > 0 && (
                    <span style={{ fontSize: 12, color: "#64748b", marginLeft: 6 }}>
                      ({klineData.length})
                    </span>
                  )}
                </span>
              )}
            </div>
            {showDropdown && searchResults.length > 0 && (
              <div style={{
                position: "absolute", top: "100%", left: 0, right: 0, zIndex: 50,
                background: "#1a1a2e", border: "1px solid #334155", borderRadius: 6,
                maxHeight: 240, overflowY: "auto", marginTop: 4,
              }}>
                {searchResults.map((stock) => (
                  <div key={stock.ts_code}
                    onClick={() => {
                      setSearchQuery(stock.ts_code);
                      setShowDropdown(false);
                      setSelectedSignal(null);
                      loadKline(stock.ts_code);
                    }}
                    style={{
                      padding: "8px 12px", cursor: "pointer",
                      borderBottom: "1px solid #1e293b",
                      display: "flex", justifyContent: "space-between",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#1e293b")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <span style={{ fontFamily: "monospace", fontSize: 13, color: "#e2e8f0" }}>
                      {stock.ts_code}
                    </span>
                    <span style={{ fontSize: 13, color: "#94a3b8" }}>
                      {stock.name}
                      {stock.industry && (
                        <span style={{ fontSize: 11, color: "#64748b", marginLeft: 6 }}>
                          {stock.industry}
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
          {klineError && (
            <div style={{ padding: 8, marginBottom: 8, background: "#3b1a1a", color: "#ef4444", borderRadius: 4, fontSize: 13 }}>
              {klineError}
            </div>
          )}
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

      {/* ====== 信号列表 ====== */}
      <div style={{ marginTop: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>📊 信号列表 (评分 ≥ 40)</h3>

          {/* 日期选择 */}
          <select value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            style={{
              padding: "6px 10px", borderRadius: 6, border: "1px solid #334155",
              background: "#1a1a2e", color: "#e2e8f0", fontSize: 13,
            }}>
            {signalDates.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>

          {/* 排序切换 */}
          <div style={{ display: "flex", gap: 0, marginLeft: "auto" }}>
            {([
              { key: "composite" as SortKey, label: "综合评分" },
              { key: "vp" as SortKey, label: "量价评分" },
              { key: "char" as SortKey, label: "股性评分" },
            ]).map((opt) => (
              <button key={opt.key}
                onClick={() => setSortBy(opt.key)}
                style={{
                  padding: "5px 12px", fontSize: 12,
                  border: sortBy === opt.key ? "1px solid #38bdf8" : "1px solid #334155",
                  borderRadius: 0,
                  borderTopLeftRadius: opt.key === "composite" ? 6 : 0,
                  borderBottomLeftRadius: opt.key === "composite" ? 6 : 0,
                  borderTopRightRadius: opt.key === "char" ? 6 : 0,
                  borderBottomRightRadius: opt.key === "char" ? 6 : 0,
                  background: sortBy === opt.key ? "#1e293b" : "transparent",
                  color: sortBy === opt.key ? "#38bdf8" : "#94a3b8",
                  cursor: "pointer",
                }}>
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "#64748b", fontSize: 12, textAlign: "left" }}>
              <th style={thStyle}>代码</th>
              <th style={thStyle}>名称</th>
              <th style={sortBy === "composite" ? activeTH : sortableTH}
                onClick={() => setSortBy("composite")}>综合评分 ▾</th>
              <th style={sortBy === "vp" ? activeTH : sortableTH}
                onClick={() => setSortBy("vp")}>量价 ▾</th>
              <th style={sortBy === "char" ? activeTH : sortableTH}
                onClick={() => setSortBy("char")}>股性 ▾</th>
              <th style={thStyle}>近一年涨停</th>
              <th style={thStyle}>近一月涨停</th>
              <th style={thStyle}>量比</th>
            </tr>
          </thead>
          <tbody>
            {sortedSignals.map((s) => {
              const p = parseRule(s);
              return (
                <tr key={s.id}
                  onClick={() => handleSignalClick(s)}
                  style={{
                    cursor: "pointer", borderTop: "1px solid #1e293b",
                    background: selectedSignal?.id === s.id ? "#1e293b" : "transparent",
                  }}>
                  <td style={{ padding: "8px 6px", fontFamily: "monospace", fontSize: 13 }}>{s.ts_code}</td>
                  <td style={{ padding: "8px 6px", fontSize: 13 }}>{s.name}</td>
                  <td style={{ padding: "8px 6px", color: s.composite_score >= 80 ? "#10b981" : s.composite_score >= 60 ? "#f59e0b" : "#e2e8f0", fontWeight: 600 }}>
                    {s.composite_score}
                  </td>
                  <td style={{ padding: "8px 6px", fontSize: 13, color: "#38bdf8" }}>{p.vp_score}</td>
                  <td style={{ padding: "8px 6px", fontSize: 13, color: "#a78bfa" }}>{p.char_score}</td>
                  <td style={{ padding: "8px 6px", fontSize: 13 }}>{p.limit_up_year}次</td>
                  <td style={{ padding: "8px 6px", fontSize: 13 }}>{p.limit_up_month}次</td>
                  <td style={{ padding: "8px 6px", fontSize: 13 }}>{p.vol_ratio}x</td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {signals.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>
            该日期暂无信号，请先运行信号扫描
          </div>
        )}
      </div>
    </div>
  );
}
