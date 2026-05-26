import React, { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "../api";
import type { GainerRow, TopData, KlineData } from "../types";
import { KlineChart } from "../components/KlineChart";

type TabKey = "year" | "month" | "new";
type SortKey = "ret_ytd" | "ret_1m" | "ret_mtd" | "pct_chg" | "close" | "lu_year" | "lu_month" | "ipo_ret" | "ipo_date" | "";

const TAB_SORT_DEFAULT: Record<TabKey, SortKey> = { year: "ret_ytd", month: "ret_mtd", new: "ipo_ret" };

const TABS: { key: TabKey; label: (newCount: number) => string }[] = [
  { key: "year", label: () => "今年以来 Top 50" },
  { key: "month", label: () => "本月涨幅 Top 50" },
  { key: "new", label: (n) => `今年次新股 (${n})` },
];

const S = {
  cell: { padding: "8px 10px", fontSize: 13 } as React.CSSProperties,
  cellR: { padding: "8px 10px", fontSize: 13, textAlign: "right" as const } as React.CSSProperties,
  th: { padding: "8px 10px", fontSize: 12, color: "#64748b", textAlign: "left" as const, whiteSpace: "nowrap" as const } as React.CSSProperties,
  thR: { padding: "8px 10px", fontSize: 12, color: "#64748b", textAlign: "right" as const, whiteSpace: "nowrap" as const } as React.CSSProperties,
};

export function Ranking() {
  const [data, setData] = useState<TopData | null>(null);
  const [tab, setTab] = useState<TabKey>("month");
  const [selectedDate, setSelectedDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>(TAB_SORT_DEFAULT.month);
  const [sortDesc, setSortDesc] = useState(true);
  const [analysis, setAnalysis] = useState<{ date: string; top_count: number; summary: string; detail: Record<string, any> } | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [klineStock, setKlineStock] = useState<{ ts_code: string; name: string } | null>(null);
  const [klineData, setKlineData] = useState<KlineData[]>([]);
  const [klineLoading, setKlineLoading] = useState(false);

  const openKline = async (tsCode: string, name: string) => {
    setKlineStock({ ts_code: tsCode, name });
    setKlineLoading(true);
    setKlineData([]);
    try { const d = await api.getKline(tsCode, 120); setKlineData(d); }
    catch { setKlineData([]); }
    setKlineLoading(false);
  };

  const fetchData = useCallback(async (date?: string) => {
    setLoading(true);
    try {
      const d = await api.getTopGainers(date) as TopData;
      setData(d);
      if (!date) setSelectedDate(d.date);
      setAnalysisLoading(true);
      try { const a = await api.getGainerAnalysis(date); setAnalysis(a); }
      catch { setAnalysis(null); }
      setAnalysisLoading(false);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => { setSortKey(TAB_SORT_DEFAULT[tab]); setSortDesc(true); }, [tab]);

  const rawRows: GainerRow[] = tab === "year" ? (data?.year_top ?? [])
    : tab === "month" ? (data?.month_top ?? [])
    : (data?.new_listings ?? []);

  const rows = useMemo(() => {
    if (!sortKey) return rawRows;
    return [...rawRows].sort((a, b) => {
      const va = (a as any)[sortKey];
      const vb = (b as any)[sortKey];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp = typeof va === "string" ? va.localeCompare(vb) : (va as number) - (vb as number);
      return sortDesc ? -cmp : cmp;
    });
  }, [rawRows, sortKey, sortDesc]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDesc(!sortDesc); else { setSortKey(key); setSortDesc(true); }
  };

  const SortTH = ({ sk, style, children }: { sk: SortKey; style?: React.CSSProperties; children: React.ReactNode }) => (
    <th onClick={() => handleSort(sk)} style={{ ...style, cursor: "pointer", userSelect: "none" }}>
      {children}
      <span style={{ marginLeft: 3, fontSize: 10, color: sortKey === sk ? "#38bdf8" : "#334155" }}>
        {sortKey === sk ? (sortDesc ? "▼" : "▲") : "⇅"}
      </span>
    </th>
  );

  const rankChange = (code: string) => {
    const rc = tab === "year" ? data?.rank_change_year : data?.rank_change_month;
    if (!rc || rc[code] === undefined) return null;
    const d = rc[code];
    if (d > 0) return <span style={{ color: "#ef4444", marginLeft: 4, fontSize: 11, fontWeight: 700 }}>↑{d}</span>;
    if (d < 0) return <span style={{ color: "#10b981", marginLeft: 4, fontSize: 11 }}>↓{Math.abs(d)}</span>;
    return <span style={{ color: "#64748b", marginLeft: 4, fontSize: 11 }}>─</span>;
  };

  const fmtPct = (v: number | null | undefined, forceSign = true, decimals?: number) => {
    if (v == null) return "-";
    const sign = forceSign && v >= 0 ? "+" : "";
    const val = decimals !== undefined ? v.toFixed(decimals) : v;
    return `${sign}${val}%`;
  };

  const pctColor = (v: number | null | undefined) => (v ?? 0) >= 0 ? "#ef4444" : "#10b981";

  return (
    <div>
      {/* 头部 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <h2 style={{ margin: 0 }}>涨幅排行</h2>
        {data?.available_dates && (
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)}
              style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #334155", background: "#1a1a2e", color: "#e2e8f0", fontSize: 13, cursor: "pointer" }}>
              {data.available_dates.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <button onClick={() => fetchData(selectedDate)}
              style={{ padding: "6px 16px", borderRadius: 6, fontSize: 13, cursor: "pointer", border: "1px solid #38bdf8", background: "#1e293b", color: "#38bdf8", fontWeight: 600 }}>
              确认
            </button>
          </div>
        )}
      </div>
      <p style={{ fontSize: 12, color: "#64748b", marginBottom: 12 }}>
        数据截止: {selectedDate || data?.date || "-"} &nbsp;|&nbsp; 已剔除今年上市新股
      </p>
      <p style={{ fontSize: 11, color: "#475569", marginBottom: 16, lineHeight: 1.6 }}>
        <span style={{ color: "#ef4444", fontWeight: 600 }}>↑N</span>/<span style={{ color: "#10b981" }}>↓N</span> = 对比上月最后一个交易日近一月涨幅排名的变化。
        例：4月30日某股近一月涨幅排第2000名，5月15日本月涨幅排第1000名 → <span style={{ color: "#ef4444", fontWeight: 600 }}>↑1000</span>
      </p>

      {/* Tab 切换 */}
      <div style={{ display: "flex", gap: 0, marginBottom: 16 }}>
        {TABS.map((opt, i, arr) => (
          <button key={opt.key} onClick={() => setTab(opt.key)} style={{
            padding: "8px 20px", fontSize: 13, cursor: "pointer",
            border: tab === opt.key ? "1px solid #38bdf8" : "1px solid #334155",
            borderTopLeftRadius: i === 0 ? 6 : 0, borderBottomLeftRadius: i === 0 ? 6 : 0,
            borderTopRightRadius: i === arr.length - 1 ? 6 : 0, borderBottomRightRadius: i === arr.length - 1 ? 6 : 0,
            background: tab === opt.key ? "#1e293b" : "transparent",
            color: tab === opt.key ? "#38bdf8" : "#94a3b8",
          }}>{opt.label(data?.new_listings?.length || 0)}</button>
        ))}
      </div>

      {/* 月榜智能分析面板 */}
      {tab === "month" && (
        <div style={{ padding: 16, marginBottom: 16, background: "linear-gradient(135deg, #1a1a2e, #1e1a30)", borderRadius: 10, border: "1px solid #2d2450" }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#a78bfa", marginBottom: 10 }}>
            本月涨幅 Top 30 上涨初期量化共性分析
            {analysisLoading && <span style={{ fontSize: 12, color: "#64748b", marginLeft: 8 }}>计算中...</span>}
          </div>
          {analysis
            ? <div style={{ fontSize: 13, color: "#c4b5fd", lineHeight: 1.8, textAlign: "justify" }}>{analysis.summary}</div>
            : !analysisLoading && <div style={{ fontSize: 12, color: "#64748b" }}>暂无分析数据</div>
          }
        </div>
      )}

      {/* 排行表格 */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #1e293b" }}>
              <th style={S.th}>排名</th>
              <th style={S.th}>代码</th>
              <th style={S.th}>名称</th>
              {tab === "new" ? (
                <>
                  <SortTH sk="ipo_date" style={S.th}>上市日期</SortTH>
                  <SortTH sk="ipo_ret" style={S.thR}>上市以来涨幅</SortTH>
                </>
              ) : tab === "year" ? (
                <>
                  <SortTH sk="ret_ytd" style={S.thR}>本年涨幅</SortTH>
                  <SortTH sk="ret_mtd" style={S.thR}>本月涨幅</SortTH>
                </>
              ) : (
                <>
                  <SortTH sk="ret_mtd" style={S.thR}>本月涨幅</SortTH>
                  <SortTH sk="ret_1m" style={S.thR}>近一月涨幅</SortTH>
                </>
              )}
              <SortTH sk="pct_chg" style={S.thR}>涨跌幅</SortTH>
              <SortTH sk="close" style={S.thR}>最新收盘</SortTH>
              <SortTH sk="lu_month" style={S.thR}>近一月涨停</SortTH>
              <SortTH sk="lu_year" style={S.thR}>近一年涨停</SortTH>
              {tab === "year" && <SortTH sk="ret_1m" style={S.thR}>近一月涨幅</SortTH>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const isTop3 = i < 3 && tab !== "new";
              return (
                <tr key={r.ts_code}
                  style={{ borderTop: "1px solid #1e293b", background: isTop3 ? "rgba(245,158,11,0.05)" : "transparent" }}>
                  <td style={{ ...S.cell, color: isTop3 ? "#f59e0b" : "#94a3b8", fontWeight: isTop3 ? 700 : 400 }}>
                    {i + 1}
                  </td>
                  <td style={{ ...S.cell, fontFamily: "monospace" }}>{r.ts_code}</td>
                  <td style={S.cell}>
                    <span onClick={(e) => { e.stopPropagation(); openKline(r.ts_code, r.name); }}
                      style={{ cursor: "pointer", color: "#e2e8f0", borderBottom: "1px dashed #64748b" }}
                      title="点击查看K线图">{r.name}</span>
                    {tab !== "new" && rankChange(r.ts_code)}
                  </td>

                  {tab === "new" ? (
                    <>
                      <td style={{ ...S.cell, fontSize: 12, color: "#94a3b8" }}>{r.ipo_date}</td>
                      <td style={{ ...S.cellR, color: pctColor(r.ipo_ret), fontWeight: 600 }}>{fmtPct(r.ipo_ret)}</td>
                    </>
                  ) : tab === "year" ? (
                    <>
                      <td style={{ ...S.cellR, color: pctColor(r.ret_ytd), fontWeight: 600 }}>{fmtPct(r.ret_ytd)}</td>
                      <td style={{ ...S.cellR, color: pctColor(r.ret_mtd) }}>{fmtPct(r.ret_mtd)}</td>
                    </>
                  ) : (
                    <>
                      <td style={{ ...S.cellR, color: pctColor(r.ret_mtd), fontWeight: 600 }}>{fmtPct(r.ret_mtd)}</td>
                      <td style={{ ...S.cellR, color: pctColor(r.ret_1m) }}>{fmtPct(r.ret_1m)}</td>
                    </>
                  )}

                  <td style={{ ...S.cellR, color: pctColor(r.pct_chg), fontWeight: 600 }}>{fmtPct(r.pct_chg, true, 2)}</td>
                  <td style={{ ...S.cellR, fontFamily: "monospace" }}>{r.close?.toFixed(2) ?? "-"}</td>
                  <td style={S.cellR}>{r.lu_month}次</td>
                  <td style={S.cellR}>{r.lu_year}次</td>

                  {tab === "year" && <td style={{ ...S.cellR, color: pctColor(r.ret_1m) }}>{fmtPct(r.ret_1m)}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>

        {loading && <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>加载中...</div>}
        {!loading && rows.length === 0 && <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>暂无数据</div>}
      </div>

      {/* K线弹窗 */}
      {klineStock && (
        <div onClick={() => setKlineStock(null)} style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.7)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            background: "#0f0f1a", borderRadius: 12, border: "1px solid #334155",
            width: "90%", maxWidth: 900, maxHeight: "85vh", overflow: "auto", padding: 20,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3 style={{ margin: 0, color: "#e2e8f0" }}>
                {klineStock.name} <span style={{ color: "#64748b", fontSize: 14 }}>{klineStock.ts_code}</span>
              </h3>
              <button onClick={() => setKlineStock(null)}
                style={{ padding: "4px 12px", fontSize: 18, cursor: "pointer", background: "transparent", border: "none", color: "#94a3b8" }}>✕</button>
            </div>
            {klineLoading
              ? <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>加载中...</div>
              : klineData.length > 0
                ? <KlineChart data={klineData} height={450} />
                : <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>暂无K线数据</div>
            }
          </div>
        </div>
      )}
    </div>
  );
}
