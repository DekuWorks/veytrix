export const CLOSE_AVERAGE_WINDOW = 20;

function averageEndingAt(closes: readonly number[], end: number, window: number): number | null {
  if (end + 1 < window) {
    return null;
  }
  let sum = 0;
  for (let index = end - window + 1; index <= end; index += 1) {
    const value = closes[index];
    if (value === undefined || !Number.isFinite(value) || value <= 0) {
      return null;
    }
    sum += value;
  }
  const average = sum / window;
  if (!Number.isFinite(average) || average <= 0) {
    return null;
  }
  return average;
}

export function rollingCloseAverage(
  closes: readonly number[],
  window = CLOSE_AVERAGE_WINDOW,
): (number | null)[] {
  return closes.map((_, end) => averageEndingAt(closes, end, window));
}

export function averageOfLastCloses(
  closes: readonly number[],
  window = CLOSE_AVERAGE_WINDOW,
): number | null {
  if (closes.length === 0) {
    return null;
  }
  return rollingCloseAverage(closes, window).at(-1) ?? null;
}
