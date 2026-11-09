"""HYPOTHETICAL MAC-01 backtest over fixture bars. Not a track record. Not investment advice.

A signal on session close t fills at the open of session t+1, adjusted by half the spread
plus slippage against the trade, and charged a flat fee. Each BUY spends a fixed notional
(default 100.00) on a fractional quantity; each SELL closes it. Long only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

from veytrix_quant.mac01.data import DailyBar
from veytrix_quant.mac01.strategy import evaluate_crossover

HYPOTHETICAL_LABEL = (
    "HYPOTHETICAL backtest over fixture bars. Not a market record, not a track record, "
    "and not investment advice."
)
BPS = Decimal(10000)
QTY_STEP = Decimal("0.000000001")


@dataclass(frozen=True)
class CostModel:
    fee_per_trade: Decimal = Decimal(0)
    spread_bps: Decimal = Decimal(0)
    slippage_bps: Decimal = Decimal(0)

    def fill_price(self, open_price: Decimal, side: str) -> Decimal:
        adjust = (self.spread_bps / 2 + self.slippage_bps) / BPS
        factor = Decimal(1) + adjust if side == "buy" else Decimal(1) - adjust
        return open_price * factor


@dataclass(frozen=True)
class Trade:
    signal_date: str
    fill_date: str
    side: str
    qty: Decimal
    price: Decimal
    fee: Decimal


@dataclass
class BacktestResult:
    label: str
    trades: list[Trade] = field(default_factory=list)
    strategy_pnl: Decimal = Decimal(0)
    buy_and_hold_pnl: Decimal = Decimal(0)
    open_position: bool = False
    sessions: int = 0


def run_backtest(
    bars: Sequence[DailyBar],
    fast_period: int = 20,
    slow_period: int = 50,
    costs: CostModel | None = None,
    notional: Decimal = Decimal("100.00"),
) -> BacktestResult:
    costs = costs or CostModel()
    ordered = sorted(bars, key=lambda bar: bar.session_date)
    result = BacktestResult(label=HYPOTHETICAL_LABEL, sessions=len(ordered))
    if len(ordered) < slow_period + 2:
        return result
    closes = [bar.close for bar in ordered]
    cash = Decimal(0)
    held = Decimal(0)
    for index in range(slow_period, len(ordered) - 1):
        signal = evaluate_crossover(closes[: index + 1], fast_period, slow_period)
        nxt = ordered[index + 1]
        if signal.side == "BUY" and held == 0:
            price = costs.fill_price(nxt.open, "buy")
            qty = (notional / price).quantize(QTY_STEP, rounding=ROUND_DOWN)
            cash -= qty * price + costs.fee_per_trade
            held = qty
        elif signal.side == "SELL" and held > 0:
            price = costs.fill_price(nxt.open, "sell")
            qty = held
            cash += qty * price - costs.fee_per_trade
            held = Decimal(0)
        else:
            continue
        result.trades.append(
            Trade(
                signal_date=ordered[index].session_date.isoformat(),
                fill_date=nxt.session_date.isoformat(),
                side="buy" if signal.side == "BUY" else "sell",
                qty=qty,
                price=price,
                fee=costs.fee_per_trade,
            )
        )
    last_close = ordered[-1].close
    result.strategy_pnl = cash + held * last_close
    result.open_position = held > 0
    entry_price = costs.fill_price(ordered[slow_period + 1].open, "buy")
    entry_qty = (notional / entry_price).quantize(QTY_STEP, rounding=ROUND_DOWN)
    result.buy_and_hold_pnl = entry_qty * (last_close - entry_price) - costs.fee_per_trade
    return result


def format_result(result: BacktestResult) -> str:
    lines = [
        result.label,
        f"sessions: {result.sessions}",
        f"trades: {len(result.trades)}",
    ]
    for trade in result.trades:
        lines.append(
            f"  {trade.side:<4} {trade.qty} signal {trade.signal_date} "
            f"fill {trade.fill_date} at {trade.price.quantize(Decimal('0.0001'))} "
            f"fee {trade.fee}"
        )
    lines.append(
        f"strategy P&L ($100 notional per buy, marked at last close): "
        f"{result.strategy_pnl.quantize(Decimal('0.01'))}"
    )
    lines.append(
        f"buy-and-hold P&L ($100 from the first tradable open): "
        f"{result.buy_and_hold_pnl.quantize(Decimal('0.01'))}"
    )
    lines.append(f"open position at end: {result.open_position}")
    return "\n".join(lines)
