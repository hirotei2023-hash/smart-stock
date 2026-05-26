import React, { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import type { KlineData } from "../types";

export function KlineChart({ data, height = 400 }: { data: KlineData[]; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!containerRef.current || data.length === 0) {
      setError("");
      return;
    }

    const container = containerRef.current;
    // 确保容器有宽度（等浏览器布局完成后再初始化图表）
    const w = container.clientWidth || container.parentElement?.clientWidth || 800;

    try {
      const chart = createChart(container, {
        height,
        width: w,
        layout: {
          background: { type: ColorType.Solid, color: "#0f0f1a" },
          textColor: "#94a3b8",
        },
        grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
        timeScale: { borderColor: "#1e293b" },
        rightPriceScale: { borderColor: "#1e293b" },
        crosshair: { mode: CrosshairMode.Normal },
      });

      // A股习惯: 红涨绿跌
      const UP_COLOR = "#ef4444";
      const DOWN_COLOR = "#10b981";

      const candleSeries = chart.addCandlestickSeries({
        upColor: UP_COLOR,
        downColor: DOWN_COLOR,
        borderUpColor: UP_COLOR,
        borderDownColor: DOWN_COLOR,
        wickUpColor: UP_COLOR,
        wickDownColor: DOWN_COLOR,
      });

      const candleData = data.map((d) => ({
        time: d.trade_date,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }));
      candleSeries.setData(candleData);

      // 涨停K线紫色覆盖层（涨停 ≈ pct_chg >= 9.5%，创业板/科创板 20%，主板 10%）
      const limitUpData = data
        .filter((d) => (d.pct_chg ?? 0) >= 9.5)
        .map((d) => ({ time: d.trade_date, open: d.open, high: d.high, low: d.low, close: d.close }));
      if (limitUpData.length > 0) {
        const PURPLE = "#a855f7";
        const luSeries = chart.addCandlestickSeries({
          upColor: PURPLE, downColor: PURPLE,
          borderUpColor: PURPLE, borderDownColor: PURPLE,
          wickUpColor: PURPLE, wickDownColor: PURPLE,
        });
        luSeries.setData(limitUpData);
      }

      // MA5
      const ma5Data = data.map((d, i) => {
        if (i < 4) return { time: d.trade_date, value: undefined as any };
        const sum = data.slice(i - 4, i + 1).reduce((s, x) => s + x.close, 0);
        return { time: d.trade_date, value: sum / 5 };
      }).filter((d) => d.value !== undefined);

      const ma5Series = chart.addLineSeries({
        color: "#ff6b35",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      ma5Series.setData(ma5Data as any);

      // MA21
      const ma21Data = data.map((d, i) => {
        if (i < 20) return { time: d.trade_date, value: undefined as any };
        const sum = data.slice(i - 20, i + 1).reduce((s, x) => s + x.close, 0);
        return { time: d.trade_date, value: sum / 21 };
      }).filter((d) => d.value !== undefined);

      const ma21Series = chart.addLineSeries({
        color: "#00bcd4",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      ma21Series.setData(ma21Data as any);

      const volumeSeries = chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "",
      });
      volumeSeries.priceScale().applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(
        data.map((d) => ({
          time: d.trade_date,
          value: d.volume,
          color: d.close >= d.open ? "rgba(239,68,68,0.4)" : "rgba(16,185,129,0.4)",
        }))
      );

      chart.timeScale().fitContent();

      // 十字光标悬浮 tooltip
      const tooltipEl = document.createElement("div");
      tooltipEl.style.cssText = `
        position: absolute; z-index: 20; pointer-events: none;
        padding: 8px 10px; border-radius: 6px; font-size: 12px;
        background: rgba(15,15,26,0.95); border: 1px solid #334155;
        color: #e2e8f0; display: none; white-space: nowrap;
        font-family: monospace;
      `;
      container.appendChild(tooltipEl);

      chart.subscribeCrosshairMove((param) => {
        if (!param.point || !param.time || param.point.x < 0 || param.point.y < 0) {
          tooltipEl.style.display = "none";
          return;
        }
        const d = param.seriesData.get(candleSeries) as any;
        if (!d) { tooltipEl.style.display = "none"; return; }
        const change = ((d.close - d.open) / d.open * 100).toFixed(2);
        const sign = d.close >= d.open ? "+" : "";
        const color = d.close >= d.open ? UP_COLOR : DOWN_COLOR;
        const open = d.open.toFixed(2);
        const high = d.high.toFixed(2);
        const low = d.low.toFixed(2);
        const close = d.close.toFixed(2);
        tooltipEl.innerHTML =
          '<div style="color:#94a3b8;margin-bottom:4px">' + param.time + '</div>' +
          '<div>开 <span style="color:#e2e8f0">' + open + '</span></div>' +
          '<div>高 <span style="color:#e2e8f0">' + high + '</span></div>' +
          '<div>低 <span style="color:#e2e8f0">' + low + '</span></div>' +
          '<div>收 <span style="color:#e2e8f0">' + close + '</span></div>' +
          '<div style="color:' + color + ';font-weight:600;margin-top:2px">' + sign + change + '%</div>';
        const x = Math.min(param.point.x + 12, container.clientWidth - 130);
        const y = Math.max(param.point.y - 80, 10);
        tooltipEl.style.display = "block";
        tooltipEl.style.left = x + "px";
        tooltipEl.style.top = y + "px";
      });
      setError("");

      // 窗口 resize 时自适应
      const handleResize = () => {
        if (container.clientWidth > 0) {
          chart.applyOptions({ width: container.clientWidth });
        }
      };
      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
        if (tooltipEl.parentNode) tooltipEl.remove();
        chart.remove();
      };
    } catch (e: any) {
      setError(e.message || String(e));
      return;
    }
  }, [data, height]);

  return (
    <div>
      {error && (
        <div style={{ padding: 8, marginBottom: 8, background: "#3b1a1a", color: "#ef4444", borderRadius: 4, fontSize: 13 }}>
          K线渲染失败: {error}
        </div>
      )}
      <div ref={containerRef} style={{ width: "100%", minHeight: data.length > 0 ? height : 0, position: "relative" }}>
        {data.length > 0 && (
          <div style={{
            position: "absolute", top: 8, left: 8, zIndex: 10,
            display: "flex", gap: 12, fontSize: 11,
            background: "rgba(15,15,26,0.85)", padding: "3px 8px",
            borderRadius: 4, pointerEvents: "none",
          }}>
            <span style={{ color: "#ff6b35", fontWeight: 600 }}>MA5</span>
            <span style={{ color: "#00bcd4", fontWeight: 600 }}>MA21</span>
          </div>
        )}
      </div>
    </div>
  );
}
