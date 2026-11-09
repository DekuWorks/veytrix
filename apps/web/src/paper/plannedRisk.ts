const DECIMAL = /^-?\d+(?:\.\d+)?$/;

type Scaled = {
  negative: boolean;
  units: bigint;
  scale: number;
};

export const PLANNED_RISK_PERCENT_NOTE =
  "Planned risk as a share of the equity you entered. The stop is not enforced. No order is sent.";

function parseDecimal(value: string): Scaled | null {
  if (!DECIMAL.test(value)) {
    return null;
  }
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [whole, fraction = ""] = unsigned.split(".");
  const units = BigInt(`${whole}${fraction}`);
  if (units === 0n) {
    return { negative: false, units: 0n, scale: fraction.length };
  }
  return { negative, units, scale: fraction.length };
}

function formatPercent(units: bigint): string {
  if (units === 0n) {
    return "0.00%";
  }
  const negative = units < 0n;
  const digits = (negative ? -units : units).toString().padStart(3, "0");
  const whole = digits.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const body = `${whole}.${digits.slice(-2)}%`;
  return negative ? `-${body}` : body;
}

export function plannedRiskPercent(plannedRisk: string, equity: string): string | null {
  const risk = parseDecimal(plannedRisk);
  const account = parseDecimal(equity);
  if (risk === null || account === null || account.negative || account.units === 0n) {
    return null;
  }
  if (risk.units === 0n) {
    return "0.00%";
  }
  const scale = Math.max(risk.scale, account.scale);
  const riskUnits = risk.units * 10n ** BigInt(scale - risk.scale);
  const equityUnits = account.units * 10n ** BigInt(scale - account.scale);
  const numerator = riskUnits * 10_000n;
  const quotient = numerator / equityUnits;
  const remainder = numerator % equityUnits;
  const rounded = remainder * 2n >= equityUnits ? quotient + 1n : quotient;
  return formatPercent(risk.negative ? -rounded : rounded);
}

export function plannedRiskPercentLine(plannedRisk: string, equity: string): string {
  const percent = plannedRiskPercent(plannedRisk, equity);
  if (percent === null) {
    return "Planned risk percent is unavailable.";
  }
  return `Planned risk percent ${percent}.`;
}
