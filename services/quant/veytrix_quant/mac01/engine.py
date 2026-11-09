"""MAC-01 run: validate data, record one signal, gate, reconcile, size, then dry-run or submit.

Only the CLI runner constructs this engine. No API route, LLM output, note, or source event
can reach `Mac01Engine.run`. The only decider is the SMA crossover in `strategy.py`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Literal

from veytrix_api.models import Mac01OrderRow, Mac01SignalRow
from veytrix_quant.mac01.alpaca_trading import (
    AccountSnapshot,
    Broker,
    BrokerError,
    BrokerRejected,
    BrokerTimeout,
    OrderRequest,
    PositionSnapshot,
)
from veytrix_quant.mac01.config import (
    CENT,
    LiveGateRefused,
    Mac01Config,
    TradingEnvironment,
    mask,
    static_live_gate_failures,
)
from veytrix_quant.mac01.data import (
    NEW_YORK,
    CloseSeries,
    DataUnavailable,
    MarketDataProvider,
    TradingCalendar,
    TradingSession,
    completed_and_next,
    validate_closes,
)
from veytrix_quant.mac01.ledger import Ledger
from veytrix_quant.mac01.logs import event
from veytrix_quant.mac01.strategy import evaluate_crossover

MINIMUM_NOTIONAL = Decimal("1.00")
SUBMIT_CUTOFF_BEFORE_CLOSE = timedelta(minutes=15)
RunStatus = Literal["ok", "blocked", "refused", "error"]


@dataclass(frozen=True)
class RunResult:
    status: RunStatus
    decision: str
    reason: str
    session_date: date | None
    side: str | None
    client_order_id: str | None = None


def client_order_id_for(
    mode: str, strategy_version: str, symbol: str, session_date: date, side: str
) -> str:
    material = f"{mode}|{strategy_version}|{symbol}|{session_date.isoformat()}|{side}"
    return f"mac01-{mode}-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:40]


def inputs_hash(config: Mac01Config, series: CloseSeries) -> str:
    window = config.slow_period + 1
    payload = {
        "strategy_version": config.strategy_version,
        "symbol": config.symbol,
        "fast": config.fast_period,
        "slow": config.slow_period,
        "closes": [
            [day.isoformat(), format(close, "f")]
            for day, close in zip(series.dates[-window:], series.closes[-window:], strict=True)
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def buy_notional(config: Mac01Config, held_value: Decimal) -> Decimal:
    """Dollar amount for one BUY: the per-trade cap, limited by room under the position cap."""

    room = config.max_position_notional - max(held_value, Decimal(0))
    amount = min(config.max_notional_per_trade, room)
    if amount <= 0:
        return Decimal("0.00")
    return amount.quantize(CENT, rounding=ROUND_DOWN)


def account_tail(account_number: str) -> str:
    return f"...{account_number[-4:]}" if len(account_number) >= 4 else "(short or empty)"


def live_account_failures(config: Mac01Config, account: AccountSnapshot) -> list[str]:
    failures: list[str] = []
    if not config.expected_account_number:
        failures.append("config expected_account_number is empty")
    elif account.account_number != config.expected_account_number:
        failures.append(
            "account number does not match expected_account_number "
            f"(broker account ends {account_tail(account.account_number)})"
        )
    if account.trading_blocked:
        failures.append("account is trading_blocked")
    if account.account_blocked:
        failures.append("account is account_blocked")
    if account.status != "ACTIVE":
        failures.append(f"account status is {account.status}")
    return failures


def in_submit_window(next_session: TradingSession, now: datetime) -> bool:
    """Regular hours of the session after the signal session, minus a cutoff before close."""

    return next_session.open <= now < next_session.close - SUBMIT_CUTOFF_BEFORE_CLOSE


@dataclass(frozen=True)
class _Decision:
    kind: Literal["NO_ACTION", "BLOCKED", "PROCEED"]
    reason: str
    order_side: Literal["buy", "sell"] | None = None
    notional: Decimal | None = None
    qty: Decimal | None = None
    note: str = ""


class Mac01Engine:
    def __init__(
        self,
        config: Mac01Config,
        broker: Broker,
        market_data: MarketDataProvider,
        calendar: TradingCalendar,
        ledger: Ledger,
        *,
        submit_flag: bool,
        env: TradingEnvironment | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        secrets: tuple[str, ...] = (),
    ) -> None:
        if broker.mode != config.mode:
            raise LiveGateRefused("Broker mode does not match config mode. Refusing.")
        self.config = config
        self.mode = config.mode
        self.broker = broker
        self.market_data = market_data
        self.calendar = calendar
        self.ledger = ledger
        self.clock = clock
        self.secrets = secrets
        self.submit_flag = submit_flag
        self.live_gate_failures: list[str] = []
        if self.mode == "live":
            self.live_gate_failures = static_live_gate_failures(
                config, env or TradingEnvironment(_env_file=None), submit_flag
            )
            if submit_flag and self.live_gate_failures:
                raise LiveGateRefused(
                    "Live submission refused: " + "; ".join(self.live_gate_failures) + "."
                )
        self.submit_enabled = bool(
            config.submit_orders and submit_flag and not self.live_gate_failures
        )

    def _safe(self, text: object) -> str:
        return mask(str(text), self.secrets)[:300]

    def _run_kind(self) -> str:
        return "submit" if self.submit_enabled else "dry_run"

    def _finish(
        self,
        status: RunStatus,
        decision: str,
        reason: str,
        session_date: date | None,
        side: str | None = None,
        client_order_id: str | None = None,
    ) -> RunResult:
        reason = self._safe(reason)
        self.ledger.record_run(status, f"{decision}: {reason}", session_date, self.mode)
        event(
            "run_finished",
            status=status,
            decision=decision,
            reason=reason,
            session_date=session_date.isoformat() if session_date else None,
            side=side,
            client_order_id=client_order_id,
            mode=self.mode,
            run=self._run_kind(),
        )
        return RunResult(status, decision, reason, session_date, side, client_order_id)

    def run(self) -> RunResult:
        try:
            return self._run()
        except Exception as exc:
            reason = f"unexpected {type(exc).__name__}: {self._safe(exc)}"
            try:
                return self._finish("error", "ERROR", reason, None)
            except Exception:
                event("run_failed", reason=reason)
                return RunResult("error", "ERROR", reason, None, None)

    def _run(self) -> RunResult:
        config = self.config
        now = self.clock()
        today = now.astimezone(NEW_YORK).date()
        event(
            "run_started",
            mode=self.mode,
            run=self._run_kind(),
            submit_flag=self.submit_flag,
            config_submit_orders=config.submit_orders,
            symbol=config.symbol,
            strategy_version=config.strategy_version,
        )

        try:
            sessions = self.calendar.sessions(
                today - timedelta(days=config.history_trading_days * 2 + 30),
                today + timedelta(days=10),
            )
        except DataUnavailable as exc:
            return self._finish("blocked", "DATA_BLOCKED", str(exc), None)
        completed, _upcoming = completed_and_next(sessions, now)
        if len(completed) < config.history_trading_days:
            return self._finish("blocked", "DATA_BLOCKED", "calendar window too short", None)
        start = completed[-config.history_trading_days].session_date
        try:
            bars = self.market_data.daily_bars(config.symbol, start, today)
        except DataUnavailable as exc:
            return self._finish("blocked", "DATA_BLOCKED", str(exc), completed[-1].session_date)
        check = validate_closes(
            bars, sessions, now, config.history_trading_days, config.slow_period + 1
        )
        latest = check.latest_completed
        if not check.ok or check.series is None or latest is None or check.next_session is None:
            event("data_rejected", reason=check.reason)
            return self._finish(
                "blocked", "DATA_BLOCKED", check.reason, latest.session_date if latest else None
            )
        series = check.series
        session_date = latest.session_date
        signal = evaluate_crossover(list(series.closes), config.fast_period, config.slow_period)
        digest = inputs_hash(config, series)
        self.ledger.record_chart(self._chart(series, now))

        row, created = self.ledger.insert_signal(
            Mac01SignalRow(
                strategy_version=config.strategy_version,
                symbol=config.symbol,
                session_date=session_date,
                close=series.closes[-1],
                fast_prev=signal.fast_prev,
                slow_prev=signal.slow_prev,
                fast_cur=signal.fast_cur,
                slow_cur=signal.slow_cur,
                side=signal.side,
                reason=signal.reason,
                decision="PENDING",
                decision_reason="evaluating",
                inputs_hash=digest,
                created_at=now,
                decided_at=now,
            )
        )
        if not created and row.inputs_hash != digest:
            event(
                "signal_inputs_changed",
                session_date=session_date.isoformat(),
                stored_side=row.side,
                new_side=signal.side,
                reason="stored signal kept; one signal per completed session",
            )
        side = row.side
        event(
            "signal",
            session_date=session_date.isoformat(),
            side=side,
            signal_created=created,
            fast_prev=str(row.fast_prev),
            slow_prev=str(row.slow_prev),
            fast_cur=str(row.fast_cur),
            slow_cur=str(row.slow_cur),
            dropped_incomplete=series.dropped_incomplete,
        )

        account: AccountSnapshot | None = None
        if self.mode == "live":
            try:
                account = self.broker.get_account()
            except BrokerError as exc:
                reason = f"live account check failed: {self._safe(exc)}"
                self.ledger.set_decision(row.id, "LIVE_REFUSED", reason)
                return self._finish("refused", "LIVE_REFUSED", reason, session_date, side)
            failures = live_account_failures(config, account)
            if failures:
                reason = "live gate: " + "; ".join(failures)
                event("live_gate_refused", reason=reason)
                self.ledger.set_decision(row.id, "LIVE_REFUSED", reason)
                return self._finish("refused", "LIVE_REFUSED", reason, session_date, side)

        try:
            self._reconcile()
        except BrokerError as exc:
            reason = f"reconcile failed: {self._safe(exc)}"
            self.ledger.set_decision(row.id, "BLOCKED", reason)
            return self._finish("error", "BLOCKED", reason, session_date, side)

        try:
            position = self.broker.get_position(config.symbol)
        except BrokerError as exc:
            reason = f"position unavailable: {self._safe(exc)}"
            self.ledger.set_decision(row.id, "BLOCKED", reason)
            return self._finish("error", "BLOCKED", reason, session_date, side)
        self.ledger.record_position(position)

        decision = self._decide(side, session_date, position, now, check.next_session, account)
        if decision.kind != "PROCEED" or decision.order_side is None:
            event("decision", decision=decision.kind, reason=decision.reason, side=side)
            self.ledger.set_decision(row.id, decision.kind, decision.reason)
            status: RunStatus = "blocked" if decision.kind == "BLOCKED" else "ok"
            return self._finish(status, decision.kind, decision.reason, session_date, side)

        client_order_id = client_order_id_for(
            self.mode, config.strategy_version, config.symbol, session_date, side
        )
        request = OrderRequest(
            symbol=config.symbol,
            side=decision.order_side,
            client_order_id=client_order_id,
            notional=decision.notional,
            qty=decision.qty,
        )
        if not self.submit_enabled:
            reason = f"would submit {describe(request)} ({self.mode}); dry-run: {self._why_dry()}"
            if decision.note:
                reason += f"; {decision.note}"
            event(
                "dry_run_order",
                side=request.side,
                notional=_text(request.notional),
                qty=_text(request.qty),
                symbol=request.symbol,
                client_order_id=client_order_id,
                mode=self.mode,
            )
            self.ledger.set_decision(row.id, "DRY_RUN", reason)
            return self._finish("ok", "DRY_RUN", reason, session_date, side, client_order_id)

        return self._submit(row.id, request, session_date, side, now)

    def _why_dry(self) -> str:
        missing = []
        if not self.submit_flag:
            missing.append("the --submit flag is absent")
        if not self.config.submit_orders:
            missing.append("config submit_orders is not true")
        for failure in self.live_gate_failures:
            if failure not in missing:
                missing.append(failure)
        return "; ".join(missing) or "submission disabled"

    def _chart(self, series: CloseSeries, now: datetime) -> dict:
        return {
            "as_of": now.astimezone(UTC).isoformat(),
            "source": getattr(self.market_data, "source", "unknown"),
            "symbol": self.config.symbol,
            "fast_period": self.config.fast_period,
            "slow_period": self.config.slow_period,
            "points": [
                {"session_date": day.isoformat(), "close": format(close, "f")}
                for day, close in zip(series.dates, series.closes, strict=True)
            ],
        }

    def _reconcile(self) -> None:
        for order in self.ledger.non_terminal_orders(self.mode):
            found = self.broker.get_order_by_client_order_id(order.client_order_id)
            if found is None:
                self.ledger.mark_order(
                    order.client_order_id,
                    "not_found",
                    "Broker has no order for this client_order_id.",
                )
                event(
                    "reconcile",
                    client_order_id=order.client_order_id,
                    previous_status=order.status,
                    status="not_found",
                )
                continue
            updated = self.ledger.apply_broker_order(order.client_order_id, found)
            event(
                "reconcile",
                client_order_id=order.client_order_id,
                previous_status=order.status,
                status=updated.status,
                filled_qty=str(updated.filled_qty),
            )

    def _decide(
        self,
        side: str,
        session_date: date,
        position: PositionSnapshot | None,
        now: datetime,
        next_session: TradingSession,
        account: AccountSnapshot | None,
    ) -> _Decision:
        config = self.config
        if side == "HOLD":
            return _Decision("NO_ACTION", "hold: no crossover")
        state = self.ledger.state()
        if config.kill_switch or state.kill_switch:
            return _Decision("BLOCKED", "kill switch engaged")
        if state.paused:
            return _Decision("BLOCKED", "strategy paused")
        held = position.qty if position is not None else Decimal(0)
        if held < 0 or (position is not None and position.side == "short"):
            return _Decision("BLOCKED", "short position present; MAC-01 is long only")
        if side == "BUY" and held > 0:
            return _Decision("NO_ACTION", "already long; long only, one position")
        if side == "SELL" and held <= 0:
            return _Decision("NO_ACTION", "no position to sell")
        client_order_id = client_order_id_for(
            self.mode, config.strategy_version, config.symbol, session_date, side
        )
        if self.ledger.find_order(client_order_id) is not None:
            return _Decision("NO_ACTION", "order already recorded for this session")
        note = ""
        if not in_submit_window(next_session, now):
            reason = (
                "outside regular hours of the session after the signal "
                f"({next_session.session_date.isoformat()}); scheduler runs 09:35 ET"
            )
            if self.submit_enabled:
                return _Decision("BLOCKED", reason)
            note = f"timing: {reason}"

        try:
            if account is None:
                account = self.broker.get_account()
            open_orders = self.broker.list_open_orders(config.symbol)
            asset = self.broker.asset_flags(config.symbol)
        except BrokerError as exc:
            return _Decision("BLOCKED", f"account check failed: {self._safe(exc)}")
        if account.status != "ACTIVE":
            return _Decision("BLOCKED", f"account status {account.status}")
        if account.trading_blocked or account.account_blocked:
            return _Decision("BLOCKED", "account trading blocked")
        if not asset.tradable:
            return _Decision("BLOCKED", f"{config.symbol} is not tradable")
        if open_orders:
            return _Decision(
                "BLOCKED", f"{len(open_orders)} open order(s) for {config.symbol}; one at a time"
            )
        today = now.astimezone(NEW_YORK).date()
        if self.ledger.orders_created_on(today, self.mode) >= config.max_orders_per_day:
            return _Decision("BLOCKED", "max orders per day reached")

        if side == "SELL":
            assert position is not None
            if position.qty_available != position.qty:
                return _Decision("BLOCKED", "part of the position is held by another order")
            return _Decision("PROCEED", "checks passed", "sell", qty=position.qty, note=note)

        if not asset.fractionable:
            return _Decision("BLOCKED", f"{config.symbol} is not fractionable; notional refused")
        if account.equity is None or account.last_equity is None:
            return _Decision("BLOCKED", "daily loss cannot be evaluated")
        if account.last_equity - account.equity >= config.daily_loss_cutoff_usd:
            return _Decision("BLOCKED", "daily loss cutoff reached")
        notional = buy_notional(config, Decimal(0))
        if notional < MINIMUM_NOTIONAL:
            return _Decision("BLOCKED", "no room under max_position_notional")
        if notional > account.cash or notional > account.buying_power:
            return _Decision("BLOCKED", "insufficient cash or buying power")
        return _Decision("PROCEED", "checks passed", "buy", notional=notional, note=note)

    def _submit(
        self,
        signal_id: object,
        request: OrderRequest,
        session_date: date,
        side: str,
        now: datetime,
    ) -> RunResult:
        cid = request.client_order_id
        claimed = self.ledger.insert_pending_order(
            Mac01OrderRow(
                client_order_id=cid,
                mode=self.mode,
                strategy_version=self.config.strategy_version,
                symbol=request.symbol,
                session_date=session_date,
                side=request.side,
                notional=request.notional,
                qty=request.qty,
                order_type=request.type,
                time_in_force=request.time_in_force,
                status="pending_submit",
                filled_qty=Decimal(0),
                created_at=now,
                updated_at=now,
            )
        )
        if not claimed:
            reason = "order already recorded for this session"
            self.ledger.set_decision(signal_id, "NO_ACTION", reason)
            return self._finish("ok", "NO_ACTION", reason, session_date, side, cid)

        event(
            "order_submitting",
            client_order_id=cid,
            side=request.side,
            notional=_text(request.notional),
            qty=_text(request.qty),
            mode=self.mode,
        )
        try:
            order = self.broker.submit_order(request)
        except BrokerRejected as exc:
            reason = f"broker rejected: {self._safe(exc)}"
            self.ledger.mark_order(cid, "rejected", reason)
            self.ledger.set_decision(signal_id, "REJECTED", reason)
            event("order_rejected", client_order_id=cid, reason=reason)
            return self._finish("blocked", "REJECTED", reason, session_date, side, cid)
        except BrokerTimeout as exc:
            event("order_submit_timeout", client_order_id=cid, reason=self._safe(exc))
            return self._lookup_after_timeout(signal_id, cid, session_date, side)
        except BrokerError as exc:
            reason = f"submit outcome unknown: {self._safe(exc)}"
            self.ledger.mark_order(cid, "unconfirmed", reason)
            self.ledger.set_decision(signal_id, "UNCONFIRMED", reason)
            return self._finish("error", "UNCONFIRMED", reason, session_date, side, cid)

        stored = self.ledger.apply_broker_order(cid, order)
        decision = "REJECTED" if stored.status == "rejected" else "SUBMITTED"
        reason = f"broker status {stored.status}; filled {stored.filled_qty}"
        self.ledger.set_decision(signal_id, decision, reason)
        event(
            "order_submitted",
            client_order_id=cid,
            broker_order_id=stored.broker_order_id,
            status=stored.status,
            filled_qty=str(stored.filled_qty),
            mode=self.mode,
        )
        status: RunStatus = "blocked" if decision == "REJECTED" else "ok"
        return self._finish(status, decision, reason, session_date, side, cid)

    def _lookup_after_timeout(
        self, signal_id: object, cid: str, session_date: date, side: str
    ) -> RunResult:
        try:
            found = self.broker.get_order_by_client_order_id(cid)
        except BrokerError as exc:
            reason = f"timeout, and lookup failed: {self._safe(exc)}; not retried"
            self.ledger.mark_order(cid, "unconfirmed", reason)
            self.ledger.set_decision(signal_id, "UNCONFIRMED", reason)
            return self._finish("error", "UNCONFIRMED", reason, session_date, side, cid)
        if found is None:
            reason = "timeout; broker has no record yet; not retried"
            self.ledger.mark_order(cid, "unconfirmed", reason)
            self.ledger.set_decision(signal_id, "UNCONFIRMED", reason)
            return self._finish("error", "UNCONFIRMED", reason, session_date, side, cid)
        stored = self.ledger.apply_broker_order(cid, found)
        reason = f"timeout; found by client_order_id; broker status {stored.status}"
        self.ledger.set_decision(signal_id, "SUBMITTED", reason)
        event("order_found_after_timeout", client_order_id=cid, status=stored.status)
        return self._finish("ok", "SUBMITTED", reason, session_date, side, cid)


def _text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def describe(request: OrderRequest) -> str:
    if request.side == "buy":
        return f"buy ${_text(request.notional)} notional {request.symbol} market DAY"
    return f"sell {_text(request.qty)} {request.symbol} (full position) market DAY"
