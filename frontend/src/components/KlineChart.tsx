import React, { useEffect, useRef } from "react";
import { createChart, ColorType } from "lightweight-charts";
import type { KlineData } from "../types";

export function KlineChart({ data, height = 400 }: { data: KlineData[]; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#0f0f1a" },
        textColor: "#94a3b8",
      },
      grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
      timeScale: { borderColor: "#1e293b" },
      rightPriceScale: { borderColor: "#1e293b" },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderUpColor: "#10b981",
      borderDownColor: "#ef4444",
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    candleSeries.setData(
      data.map((d) => ({
        time: d.trade_date,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }))
    );

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
        color: d.close >= d.open ? "rgba(16,185,129,0.4)" : "rgba(239,68,68,0.4)",
      }))
    );

    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [data, height]);

  return <div ref={containerRef} />;
}
