import React, { useState, useEffect } from "react";
import { createChart, ColorType } from "lightweight-charts";
import { api } from "../api";
import type { BacktestResult, KlineData } from "../types";
import { MetricsGrid } from "../components/MetricsGrid";
import { KlineChart } from "../components/KlineChart";

const TODAY = new Date().toISOString().slice(0, 10);

function drawEquityChart(el: HTMLDivElement, data: BacktestResult) {
  if (!data.equity_curve?.length) return;
  el.innerHTML = "";
  const chart = createChart(el, {
    height: 300,
    width: el.clientWidth,
    layout: { background: { type: ColorType.Solid, color: "#0f0f1a" }, textColor: "#94a3b8" },
    grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
    timeScale: { borderColor: "#1e293b" },
    rightPriceScale: { borderColor: "#1e293b" },
  });
  const line = chart.addLineSeries({ color: "#38bdf8", lineWidth: 2 });
  line.setData(data.equity_curve.map((p) => ({ time: p.date, value: p.equity })));
  chart.timeScale().fitContent();
}

export function Backtest() {
  const [config, setConfig] = useState({
    start_date: "2026-01-01",
    end_date: TODAY,
    capital: "100000",
    max_positions: "5",
    stop_loss: "5",
    trailing_stop: "10",
    version: "v1",
  });
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const chartRef = React.useRef<HTMLDivElement>(null);
  // K线弹窗
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

  useEffect(() => {
    if (result && chartRef.current) {
      // 等 DOM 渲染完再画图
      setTimeout(() => drawEquityChart(chartRef.current!, result), 100);
    }
  }, [result]);

  const update = (key: string, value: string) =>
    setConfig((c) => ({ ...c, [key]: value }));

  const runBacktest = async () => {
    setLoading(true);
    try {
      const payload = {
        start_date: config.start_date,
        end_date: config.end_date,
        capital: parseFloat(config.capital) || 100000,
        max_positions: parseInt(config.max_positions) || 5,
        stop_loss: -(parseFloat(config.stop_loss) || 8) / 100,
        trailing_stop: (parseFloat(config.trailing_stop) || 5) / 100,
        version: config.version,
      };
      const data = await api.runBacktest(payload);
      setResult(data);
    } catch (e: any) {
      alert("回测请求失败: " + (e.message || "网络错误"));
    } finally {
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    padding: "8px 12px", borderRadius: 6, border: "1px solid #334155",
    background: "#0f0f1a", color: "#e2e8f0", width: "100%", fontSize: 14,
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 12, color: "#94a3b8", marginBottom: 4, display: "block",
  };

  const hintStyle: React.CSSProperties = {
    fontSize: 11, color: "#64748b", marginTop: 2,
  };

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>回测中心</h2>

      {/* ====== 选股策略说明 ====== */}
      <div style={{
        padding: "12px 16px", marginBottom: 20, background: "#0f1729",
        borderRadius: 8, border: "1px solid #1e3a5f",
        fontSize: 13, color: "#94a3b8", lineHeight: 1.8,
      }}>
        <span style={{ color: "#38bdf8", fontWeight: 600 }}>选股策略：</span>
        综合评分 = <span style={{ color: "#e2e8f0" }}>量价得分 × 60%</span>
        + <span style={{ color: "#e2e8f0" }}>股性得分（涨停次数排名）× 40%</span>
        &nbsp;→&nbsp; 取 composite_score ≥ 50 的股票，按评分降序买入前 N 只。
        每只仓位 = 总资金 × 20% / N，买入 100 股整数倍。
        <span style={{ color: "#64748b" }}>|</span>
        <span style={{ color: "#f59e0b" }}>V1</span> 固定止损+回撤止盈
        <span style={{ color: "#64748b" }}>|</span>
        <span style={{ color: "#a78bfa" }}>V2</span> ATR动态止损+波动率仓位+市场状态过滤
      </div>

      {/* ====== 参数配置 ====== */}
      <div style={{
        padding: 20, background: "#1a1a2e", borderRadius: 10,
        border: "1px solid #1e293b", marginBottom: 20,
      }}>
        <h3 style={{ marginBottom: 16, fontSize: 16 }}>回测参数</h3>

        {/* 第一行: 日期范围 */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>起始日期</label>
            <input type="date" value={config.start_date}
              onChange={(e) => update("start_date", e.target.value)}
              style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>结束日期</label>
            <input type="date" value={config.end_date}
              onChange={(e) => update("end_date", e.target.value)}
              style={inputStyle} />
          </div>
        </div>

        {/* 第二行: 资金 + 最大持仓 */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>初始资金</label>
            <input type="number" value={config.capital}
              onChange={(e) => update("capital", e.target.value)}
              style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>最大持仓数</label>
            <select value={config.max_positions}
              onChange={(e) => update("max_positions", e.target.value)}
              style={inputStyle}>
              {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => (
                <option key={n} value={n}>{n} 只</option>
              ))}
            </select>
          </div>
        </div>

        {/* 第三行: 止损 + 止盈 */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>止损线 (%)</label>
            <input type="number" value={config.stop_loss}
              onChange={(e) => update("stop_loss", e.target.value)}
              min="1" max="30" step="0.5"
              style={inputStyle} />
            <div style={hintStyle}>从买入价下跌超过此比例立即卖出</div>
          </div>
          <div>
            <label style={labelStyle}>回撤止盈 (%)</label>
            <input type="number" value={config.trailing_stop}
              onChange={(e) => update("trailing_stop", e.target.value)}
              min="1" max="20" step="0.5"
              style={inputStyle} />
            <div style={hintStyle}>从最高点回撤超过此比例止盈卖出</div>
          </div>
        </div>

        {/* 第四行: 策略版本 + 按钮 */}
        <div style={{ display: "flex", gap: 16, alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>策略版本</label>
            <div style={{ display: "flex", gap: 0 }}>
              {[
                { key: "v1", label: "V1 简单", desc: "固定止损+回撤止盈" },
                { key: "v2", label: "V2 增强", desc: "ATR动态止损+波动率仓位+市场状态" },
              ].map((opt) => (
                <button key={opt.key}
                  onClick={() => update("version", opt.key)}
                  style={{
                    flex: 1,
                    padding: "8px 12px",
                    border: config.version === opt.key ? "2px solid #38bdf8" : "1px solid #334155",
                    borderRadius: config.version === opt.key ? undefined : 0,
                    borderTopLeftRadius: opt.key === "v1" ? 6 : 0,
                    borderBottomLeftRadius: opt.key === "v1" ? 6 : 0,
                    borderTopRightRadius: opt.key === "v2" ? 6 : 0,
                    borderBottomRightRadius: opt.key === "v2" ? 6 : 0,
                    background: config.version === opt.key ? "#1e293b" : "transparent",
                    color: config.version === opt.key ? "#38bdf8" : "#94a3b8",
                    cursor: "pointer", textAlign: "center",
                  }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{opt.label}</div>
                  <div style={{ fontSize: 10, color: "#64748b", marginTop: 2 }}>{opt.desc}</div>
                </button>
              ))}
            </div>
          </div>
          <button onClick={runBacktest} disabled={loading}
            style={{
              padding: "10px 32px", background: loading ? "#334155" : "#38bdf8",
              color: "#0f0f1a", border: "none", borderRadius: 8,
              cursor: loading ? "not-allowed" : "pointer",
              fontWeight: 700, fontSize: 15, whiteSpace: "nowrap",
            }}>
            {loading ? "运行中..." : "开始回测"}
          </button>
        </div>
      </div>

      {/* ====== 回测结果 ====== */}
      {result && (
        <>
          <MetricsGrid metrics={result.metrics} />

          <div style={{
            marginTop: 20, padding: 16, background: "#1a1a2e",
            borderRadius: 10, border: "1px solid #1e293b",
          }}>
            <h3 style={{ marginBottom: 12, fontSize: 16 }}>权益曲线</h3>
            <div ref={chartRef} style={{ width: "100%" }} />
          </div>

          <div style={{
            marginTop: 20, padding: 16, background: "#1a1a2e",
            borderRadius: 10, border: "1px solid #1e293b",
          }}>
            <h3 style={{ marginBottom: 12, fontSize: 16 }}>
              交易记录
              <span style={{ fontSize: 12, color: "#64748b", marginLeft: 8 }}>
                ({result.trades.length} 笔)
              </span>
            </h3>
            <div style={{ maxHeight: 400, overflow: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ color: "#64748b", textAlign: "left", position: "sticky", top: 0, background: "#1a1a2e" }}>
                    <th style={{ padding: "6px 8px" }}>日期</th>
                    <th style={{ padding: "6px 8px" }}>股票</th>
                    <th style={{ padding: "6px 8px" }}>操作</th>
                    <th style={{ padding: "6px 8px", textAlign: "right" }}>股数</th>
                    <th style={{ padding: "6px 8px", textAlign: "right" }}>价格</th>
                    <th style={{ padding: "6px 8px", textAlign: "right" }}>盈亏</th>
                    <th style={{ padding: "6px 8px" }}>原因</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.map((t, i) => (
                    <tr key={i} style={{ borderTop: "1px solid #1e293b" }}>
                      <td style={{ padding: "6px 8px", fontSize: 12 }}>{t.date}</td>
                      <td style={{ padding: "6px 8px", fontSize: 12 }}>
                        <span style={{ fontFamily: "monospace" }}>{t.ts_code}</span>
                        {t.name && <span onClick={() => openKline(t.ts_code, t.name || t.ts_code)}
                          style={{ color: "#94a3b8", marginLeft: 6, cursor: "pointer", borderBottom: "1px dashed #64748b" }}
                          title="点击查看K线图">{t.name}</span>}
                      </td>
                      <td style={{
                        padding: "6px 8px", fontSize: 12,
                        color: t.type === "buy" ? "#10b981" : "#ef4444",
                        fontWeight: 600,
                      }}>
                        {t.type === "buy" ? "买入" : "卖出"}
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right", fontSize: 12 }}>
                        {t.shares.toLocaleString()}
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right", fontSize: 12 }}>
                        {t.price?.toFixed(2)}
                      </td>
                      <td style={{
                        padding: "6px 8px", textAlign: "right", fontSize: 12,
                        color: t.pnl >= 0 ? "#10b981" : "#ef4444",
                      }}>
                        {t.pnl !== 0 ? `${t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(0)}` : "-"}
                      </td>
                      <td style={{ padding: "6px 8px", fontSize: 11, color: "#94a3b8" }}>
                        {t.reason === "stop_loss" ? "止损" :
                         t.reason === "trailing_stop" ? "止盈" :
                         t.reason === "end" ? "期末清仓" :
                         t.reason || "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

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
