import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";
import type { IChartApi, Time } from "lightweight-charts";
import type { StockKline } from "../types";

export function CandlestickChart({
  kline,
  addedDate,
}: {
  kline: StockKline;
  addedDate: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || !kline || kline.dates.length === 0) return;

    const containerWidth = containerRef.current.clientWidth || 600;
    const containerHeight = 320;

    const chart = createChart(containerRef.current, {
      width: containerWidth,
      height: containerHeight,
      layout: { background: { color: "#ffffff" }, textColor: "#333" },
      grid: {
        vertLines: { color: "#e2e8e8" },
        horzLines: { color: "#e2e8e8" },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: "#999", labelBackgroundColor: "#333" },
        horzLine: { color: "#999", labelBackgroundColor: "#333" },
      },
      rightPriceScale: { borderColor: "#e2e8e8" },
      timeScale: { borderColor: "#e2e8e8", timeVisible: true },
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#e74c3c",
      downColor: "#27ae60",
      borderUpColor: "#e74c3c",
      borderDownColor: "#27ae60",
      wickUpColor: "#e74c3c",
      wickDownColor: "#27ae60",
    });

    const candleData = kline.dates.map((date, i) => {
      const normalizedDate =
        date.includes("-") ? date : (
          `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`
        );
      return {
        time: normalizedDate as Time,
        open: kline.opens[i] ?? kline.closes[i],
        high: kline.highs[i] ?? kline.closes[i],
        low: kline.lows[i] ?? kline.closes[i],
        close: kline.closes[i],
      };
    });
    candlestickSeries.setData(candleData);

    if (addedDate) {
      const addedIdx = kline.dates.findIndex((d) => d >= addedDate);
      if (addedIdx >= 0) {
        candlestickSeries.createPriceLine({
          price: kline.closes[addedIdx],
          color: "#3498db",
          lineWidth: 2,
          lineStyle: 2,
          axisLabelVisible: true,
          title: "入局",
        });
        chart.timeScale().scrollToPosition(20, false);
      }
    }

    chartRef.current = chart;
    const resizeObserver = new ResizeObserver((entries) => {
      if (entries[0] && chartRef.current) {
        chartRef.current.applyOptions({
          width: entries[0].contentRect.width,
          height: containerHeight,
        });
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [kline, addedDate]);

  if (!kline || kline.dates.length === 0) return null;

  return (
    <div
      style={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "8px",
      }}
    >
      <div ref={containerRef} style={{ width: "100%", minHeight: "320px" }} />
      <div style={{ fontSize: "12px", color: "#999" }}>
        可拖动查看历史K线 | 蓝线标记入局价格
      </div>
    </div>
  );
}
