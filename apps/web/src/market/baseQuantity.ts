const DECIMAL = /^\d+(?:\.\d+)?$/;

export const TICKER_SIZE_NOTE =
  "From the Coinbase ticker. Base currency, not USD. Not a consolidated quote. No order is sent.";

export function formatBaseQuantity(value: string): string | null {
  if (!DECIMAL.test(value)) {
    return null;
  }
  const [whole, fraction = ""] = value.split(".");
  const units = BigInt(`${whole}${fraction}`);
  const digits = units.toString().padStart(fraction.length + 1, "0");
  const normalizedWhole = fraction.length === 0 ? digits : digits.slice(0, -fraction.length);
  const normalizedFraction = fraction.length === 0 ? "" : digits.slice(-fraction.length).replace(/0+$/, "");
  const grouped = normalizedWhole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return normalizedFraction.length === 0 ? grouped : `${grouped}.${normalizedFraction}`;
}

export function volumeLine(value: string, asset: string): string {
  const formatted = formatBaseQuantity(value);
  if (formatted === null) {
    return "Volume is unavailable.";
  }
  return `24-hour base volume ${formatted} ${asset}.`;
}

export function lastSizeLine(value: string, asset: string): string {
  const formatted = formatBaseQuantity(value);
  if (formatted === null) {
    return "Last size is unavailable.";
  }
  return `Last trade size ${formatted} ${asset}.`;
}
