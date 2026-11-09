import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SampleChart } from "./SampleChart";

const { createChart, setData } = vi.hoisted(() => {
  const setData = vi.fn();
  const createChart = vi.fn(() => ({
    addSeries: vi.fn(() => ({ setData, applyOptions: () => undefined })),
    remove: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn() }),
  }));
  return { createChart, setData };
});

vi.mock("lightweight-charts", () => ({
  CandlestickSeries: { type: "Candlestick" },
  HistogramSeries: { type: "Histogram" },
  LineSeries: { type: "Line" },
  ColorType: { Solid: "solid" },
  createChart,
}));

describe("SampleChart", () => {
  it("plots the supplied synthetic bars with lightweight-charts", () => {
    const bars = [{ time: "2026-01-05", open: 100, high: 101, low: 99, close: 100.5 }];

    render(
      <SampleChart
        bars={bars}
        caption="SAMPLE on SIM. Source synthetic-sample."
        label="Synthetic SAMPLE candlestick chart. Not a market price."
      />,
    );

    expect(
      screen.getByRole("img", { name: "Synthetic SAMPLE candlestick chart. Not a market price." }),
    ).toBeInTheDocument();
    expect(createChart).toHaveBeenCalled();
    expect(setData).toHaveBeenCalledWith([
      { time: "2026-01-05", open: 100, high: 101, low: 99, close: 100.5 },
    ]);
  });
});
