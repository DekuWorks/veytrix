import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  type AutoscaleInfoProvider,
  type IPriceLine,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { rollingCloseAverage } from "../quant/average";

const DECIMAL = /^\d+(?:\.\d+)?$/;
const UP_COLOUR = "#3dbe8b";
const DOWN_COLOUR = "#e07a7a";
const AVERAGE_COLOUR = "#e6c15a";
const LAST_TRADE_COLOUR = "#7aa2ff";
const PREVIOUS_CLOSE_COLOUR = "#e36ad4";
const DAY_HIGH_COLOUR = "#f97316";
const DAY_LOW_COLOUR = "#22d3ee";

function chartPrice(value: string | null | undefined): number | null {
  if (value == null || !DECIMAL.test(value)) {
    return null;
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  return numeric;
}

export type ChartBar = {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: string;
};

function chartVolume(value: string): number | null {
  return chartPrice(value);
}

type SampleChartProps = {
  bars: readonly ChartBar[];
  caption: string;
  label: string;
  lastTrade?: string | null;
  previousClose?: string | null;
  dayHigh?: string | null;
  dayLow?: string | null;
};

function syncPriceLine(
  series: ISeriesApi<"Candlestick">,
  current: IPriceLine | null,
  value: string | null,
  color: string,
  title: string,
): IPriceLine | null {
  const price = chartPrice(value);
  if (price === null) {
    if (current) {
      series.removePriceLine(current);
    }
    return null;
  }
  if (current) {
    current.applyOptions({ price });
    return current;
  }
  return series.createPriceLine({
    price,
    color,
    lineWidth: 2,
    lineStyle: LineStyle.Solid,
    axisLabelVisible: true,
    title,
  });
}

export function SampleChart({
  bars,
  caption,
  label,
  lastTrade = null,
  previousClose = null,
  dayHigh = null,
  dayLow = null,
}: SampleChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const priceLineRef = useRef<IPriceLine | null>(null);
  const previousCloseLineRef = useRef<IPriceLine | null>(null);
  const dayHighLineRef = useRef<IPriceLine | null>(null);
  const dayLowLineRef = useRef<IPriceLine | null>(null);
  const scalePricesRef = useRef<Array<string | null>>([]);
  scalePricesRef.current = [lastTrade, previousClose, dayHigh, dayLow];

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return undefined;
    }
    const intraday = bars.some((bar) => typeof bar.time === "number");
    const chart = createChart(container, {
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
      timeScale: { borderColor: "#2a3b34", timeVisible: intraday, secondsVisible: false },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOUR,
      downColor: DOWN_COLOUR,
      borderVisible: false,
      wickUpColor: "#8ee0b8",
      wickDownColor: "#f0a8a8",
      priceLineVisible: false,
      autoscaleInfoProvider: ((original) => {
        const info = original();
        const extras = scalePricesRef.current
          .map((value) => chartPrice(value))
          .filter((value): value is number => value !== null);
        if (info?.priceRange == null || extras.length === 0) {
          return info;
        }
        return {
          priceRange: {
            minValue: Math.min(info.priceRange.minValue, ...extras),
            maxValue: Math.max(info.priceRange.maxValue, ...extras),
          },
          margins: info.margins,
        };
      }) satisfies AutoscaleInfoProvider,
    });
    seriesRef.current = series;
    priceLineRef.current = null;
    previousCloseLineRef.current = null;
    dayHighLineRef.current = null;
    dayLowLineRef.current = null;
    const candleData = bars.map((bar) => ({
      time: typeof bar.time === "number" ? (bar.time as UTCTimestamp) : bar.time,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));
    series.setData(candleData);
    const averages = rollingCloseAverage(bars.map((bar) => bar.close));
    const lineData = candleData.flatMap((bar, index) => {
      const value = averages[index];
      return value === null || value === undefined ? [] : [{ time: bar.time, value }];
    });
    if (lineData.length > 0) {
      const average = chart.addSeries(LineSeries, {
        color: AVERAGE_COLOUR,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
      });
      average.setData(lineData);
    }
    const volumeData = bars.flatMap((bar, index) => {
      if (bar.volume === undefined) {
        return [];
      }
      const value = chartVolume(bar.volume);
      const candle = candleData[index];
      if (value === null || candle === undefined) {
        return [];
      }
      return [
        {
          time: candle.time,
          value,
          color: candle.close > candle.open ? UP_COLOUR : DOWN_COLOUR,
        },
      ];
    });
    if (volumeData.length > 0) {
      const histogram = chart.addSeries(
        HistogramSeries,
        {
          color: DOWN_COLOUR,
          priceFormat: { type: "volume" },
          priceLineVisible: false,
          lastValueVisible: false,
        },
        1,
      );
      histogram.setData(volumeData);
      const [pricePane, volumePane] = chart.panes();
      pricePane?.setStretchFactor(3);
      volumePane?.setStretchFactor(1);
    }
    chart.timeScale().fitContent();
    return () => {
      priceLineRef.current = null;
      previousCloseLineRef.current = null;
      dayHighLineRef.current = null;
      dayLowLineRef.current = null;
      seriesRef.current = null;
      chart.remove();
    };
  }, [bars]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) {
      return undefined;
    }
    priceLineRef.current = syncPriceLine(
      series,
      priceLineRef.current,
      lastTrade,
      LAST_TRADE_COLOUR,
      "Last trade",
    );
    previousCloseLineRef.current = syncPriceLine(
      series,
      previousCloseLineRef.current,
      previousClose,
      PREVIOUS_CLOSE_COLOUR,
      "Previous close",
    );
    dayHighLineRef.current = syncPriceLine(
      series,
      dayHighLineRef.current,
      dayHigh,
      DAY_HIGH_COLOUR,
      "Day high",
    );
    dayLowLineRef.current = syncPriceLine(
      series,
      dayLowLineRef.current,
      dayLow,
      DAY_LOW_COLOUR,
      "Day low",
    );
    series.applyOptions({});
    return undefined;
  }, [bars, lastTrade, previousClose, dayHigh, dayLow]);

  return (
    <figure>
      <figcaption className="mb-3 text-sm text-muted">{caption}</figcaption>
      <div
        ref={containerRef}
        role="img"
        aria-label={label}
        className="h-96 w-full overflow-hidden rounded-md border border-line bg-panel"
      />
    </figure>
  );
}
