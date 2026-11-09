import { useEffect, useRef } from "react";
import {
  ColorType,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import type { Mac01ChartResponse } from "../api/types";

const DECIMAL = /^\d+(?:\.\d+)?$/;
const CLOSE_COLOUR = "#e7f3ec";
const FAST_COLOUR = "#e6c15a";
const SLOW_COLOUR = "#7aa2ff";
const BUY_COLOUR = "#3dbe8b";
const SELL_COLOUR = "#e07a7a";

function chartValue(value: string | null): number | null {
  if (value === null || !DECIMAL.test(value)) {
    return null;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

type StrategyChartProps = {
  chart: Mac01ChartResponse;
  caption: string;
};

export function StrategyChart({ chart, caption }: StrategyChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return undefined;
    }
    const instance = createChart(container, {
      height: 384,
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#121a17" },
        textColor: "#e7f3ec",
        fontFamily: "IBM Plex Sans, sans-serif",
      },
      grid: {
        vertLines: { color: "#24332c" },
        horzLines: { color: "#24332c" },
      },
      rightPriceScale: { borderColor: "#2a3b34" },
      timeScale: { borderColor: "#2a3b34", timeVisible: false },
    });
    const line = (key: "close" | "sma_fast" | "sma_slow") =>
      chart.points.flatMap((point) => {
        const value = chartValue(point[key]);
        return value === null ? [] : [{ time: point.session_date as Time, value }];
      });
    const close = instance.addSeries(LineSeries, {
      color: CLOSE_COLOUR,
      lineWidth: 2,
      priceLineVisible: false,
      title: "Close",
    });
    close.setData(line("close"));
    instance
      .addSeries(LineSeries, {
        color: FAST_COLOUR,
        lineWidth: 2,
        priceLineVisible: false,
        title: `SMA ${chart.fast_period ?? ""}`,
      })
      .setData(line("sma_fast"));
    instance
      .addSeries(LineSeries, {
        color: SLOW_COLOUR,
        lineWidth: 2,
        priceLineVisible: false,
        title: `SMA ${chart.slow_period ?? ""}`,
      })
      .setData(line("sma_slow"));
    const markers: SeriesMarker<Time>[] = chart.markers.map((marker) => ({
      time: marker.session_date as Time,
      position: marker.side === "BUY" ? "belowBar" : "aboveBar",
      color: marker.side === "BUY" ? BUY_COLOUR : SELL_COLOUR,
      shape: marker.side === "BUY" ? "arrowUp" : "arrowDown",
      text: marker.side === "BUY" ? "Cross up" : "Cross down",
    }));
    createSeriesMarkers(close, markers);
    instance.timeScale().fitContent();
    return () => {
      instance.remove();
    };
  }, [chart]);

  return (
    <figure>
      <figcaption className="mb-3 text-sm text-muted">{caption}</figcaption>
      <div
        ref={containerRef}
        role="img"
        aria-label={`AAPL daily adjusted closes with SMA ${chart.fast_period ?? ""} and SMA ${chart.slow_period ?? ""}. Alpaca market data.`}
        className="h-96 w-full overflow-hidden rounded-md border border-line bg-panel"
      />
    </figure>
  );
}
