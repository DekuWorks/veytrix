"""Alpaca Trading API adapter for MAC-01 (alpaca-py TradingClient, paper or live).

Only this module and `alpaca_data.py` import alpaca-py. Credentials are never logged, never
put in exceptions, and never shown by repr.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

import requests
from alpaca.common.enums import BaseURL
from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetCalendarRequest, GetOrdersRequest, MarketOrderRequest

from veytrix_quant.mac01.config import CENT, NOTIONAL_CEILING, Mode
from veytrix_quant.mac01.data import NEW_YORK, DataUnavailable, TradingSession

HTTP_TIMEOUT_SECONDS = 10.0
EXPECTED_BASE_URL = {"paper": BaseURL.TRADING_PAPER.value, "live": BaseURL.TRADING_LIVE.value}


class BrokerError(RuntimeError):
    """A broker call failed with a definite answer that is not a rejection."""


class BrokerTimeout(BrokerError):
    """The outcome is unknown. Never retry a submit blindly; look it up instead."""


class BrokerRejected(BrokerError):
    """The broker refused the request."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class _NotFound(BrokerError):
    pass


@dataclass(frozen=True)
class AccountSnapshot:
    account_number: str
    status: str
    trading_blocked: bool
    account_blocked: bool
    cash: Decimal
    buying_power: Decimal
    equity: Decimal | None
    last_equity: Decimal | None


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    side: str
    qty: Decimal
    qty_available: Decimal
    avg_entry_price: Decimal | None
    current_price: Decimal | None
    market_value: Decimal | None
    unrealized_pl: Decimal | None


@dataclass(frozen=True)
class AssetFlags:
    tradable: bool
    fractionable: bool


@dataclass(frozen=True)
class BrokerOrder:
    id: str
    client_order_id: str
    symbol: str
    side: str
    qty: Decimal | None
    notional: Decimal | None
    status: str
    filled_qty: Decimal
    filled_avg_price: Decimal | None
    submitted_at: datetime | None


@dataclass(frozen=True)
class OrderRequest:
    """BUY is a notional market DAY order. SELL is a quantity market DAY order."""

    symbol: Literal["AAPL"]
    side: Literal["buy", "sell"]
    client_order_id: str
    notional: Decimal | None = None
    qty: Decimal | None = None
    type: Literal["market"] = "market"
    time_in_force: Literal["day"] = "day"

    def __post_init__(self) -> None:
        if self.symbol != "AAPL":
            raise ValueError("MAC-01 trades AAPL only.")
        if self.side == "buy":
            if self.notional is None or self.qty is not None:
                raise ValueError("A MAC-01 buy is notional only.")
            if self.notional != self.notional.quantize(CENT):
                raise ValueError("Notional must have at most two decimal places.")
            if not Decimal(1) <= self.notional <= NOTIONAL_CEILING:
                raise ValueError("Notional must be between 1.00 and 100.00.")
        elif self.side == "sell":
            if self.qty is None or self.notional is not None or self.qty <= 0:
                raise ValueError("A MAC-01 sell closes a held quantity and nothing else.")
        else:
            raise ValueError("Side must be buy or sell.")
        if self.type != "market" or self.time_in_force != "day":
            raise ValueError("MAC-01 submits DAY market orders only.")


class Broker(Protocol):
    mode: Mode

    def get_account(self) -> AccountSnapshot: ...

    def get_position(self, symbol: str) -> PositionSnapshot | None: ...

    def asset_flags(self, symbol: str) -> AssetFlags: ...

    def list_open_orders(self, symbol: str) -> list[BrokerOrder]: ...

    def submit_order(self, request: OrderRequest) -> BrokerOrder: ...

    def get_order_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None: ...


def _enum(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise BrokerError("Unexpected boolean where a decimal was expected.")
    try:
        number = Decimal(str(value))
    except Exception as exc:
        raise BrokerError("Broker returned a non-decimal number.") from exc
    if not number.is_finite():
        raise BrokerError("Broker returned a non-finite number.")
    return number


def _required(value: Any, field: str) -> Decimal:
    number = _decimal(value)
    if number is None:
        raise BrokerError(f"Broker response is missing {field}.")
    return number


def _as_float(value: Decimal) -> float:
    """alpaca-py takes floats; refuse any amount that would not survive the trip exactly."""

    number = float(value)
    if Decimal(repr(number)) != value.normalize():
        raise ValueError("Amount cannot be represented exactly for the broker.")
    return number


def to_order(order: Any) -> BrokerOrder:
    return BrokerOrder(
        id=str(order.id),
        client_order_id=str(order.client_order_id or ""),
        symbol=str(order.symbol),
        side=_enum(order.side),
        qty=_decimal(order.qty),
        notional=_decimal(order.notional),
        status=_enum(order.status) or "unknown",
        filled_qty=_decimal(order.filled_qty) or Decimal(0),
        filled_avg_price=_decimal(order.filled_avg_price),
        submitted_at=order.submitted_at,
    )


def to_account(account: Any) -> AccountSnapshot:
    return AccountSnapshot(
        account_number=str(account.account_number or ""),
        status=_enum(account.status).upper() or "UNKNOWN",
        trading_blocked=account.trading_blocked is not False,
        account_blocked=account.account_blocked is not False,
        cash=_required(account.cash, "cash"),
        buying_power=_required(account.buying_power, "buying_power"),
        equity=_decimal(account.equity),
        last_equity=_decimal(account.last_equity),
    )


def to_position(position: Any) -> PositionSnapshot:
    qty = _required(position.qty, "qty")
    available = _decimal(getattr(position, "qty_available", None))
    return PositionSnapshot(
        symbol=str(position.symbol),
        side=_enum(position.side),
        qty=qty,
        qty_available=available if available is not None else qty,
        avg_entry_price=_decimal(position.avg_entry_price),
        current_price=_decimal(position.current_price),
        market_value=_decimal(position.market_value),
        unrealized_pl=_decimal(position.unrealized_pl),
    )


def _api_status(exc: APIError) -> int | None:
    try:
        return int(exc.status_code)
    except Exception:
        return None


def _api_message(exc: APIError) -> str:
    try:
        message = exc.message
    except Exception:
        message = "no message"
    return str(message)[:300]


def harden_client(client: Any) -> None:
    """alpaca-py sets no HTTP timeout and retries 429/504, even on POST /orders.

    A retried submit after a lost response is exactly what MAC-01 must never do, and
    `retry_attempts=0` is ignored by the constructor, so both are set here.
    """

    client._retry = 0
    session = client._session
    original = session.request

    def request_with_timeout(method: str, url: str, **kwargs: Any):
        kwargs.setdefault("timeout", HTTP_TIMEOUT_SECONDS)
        return original(method, url, **kwargs)

    session.request = request_with_timeout


def call_broker[T](action: Callable[[], T], what: str) -> T:
    try:
        return action()
    except requests.exceptions.Timeout as exc:
        raise BrokerTimeout(f"Timed out: {what}. Outcome unknown.") from exc
    except requests.exceptions.RequestException as exc:
        raise BrokerTimeout(f"Network error: {what}. Outcome unknown.") from exc
    except APIError as exc:
        status = _api_status(exc)
        message = _api_message(exc)
        if status is None or status >= 500:
            raise BrokerTimeout(f"Broker returned HTTP {status}: {what}.") from exc
        if status == 404:
            raise _NotFound(what) from exc
        if status == 422 and "client_order_id" in message.lower():
            raise BrokerTimeout(
                f"Broker reports the client_order_id already exists: {what}. Look it up."
            ) from exc
        raise BrokerRejected(status, message) from exc


class AlpacaTradingBroker:
    """The user's Alpaca Trading API account. paper=True for paper, paper=False for live."""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        mode: Mode,
        *,
        client: Any | None = None,
    ) -> None:
        if mode not in ("paper", "live"):
            raise ValueError("mode must be paper or live.")
        if client is None:
            if not api_key or not secret_key:
                raise ValueError("Alpaca Trading API credentials are required.")
            client = TradingClient(api_key, secret_key, paper=(mode == "paper"))
            if client._base_url != EXPECTED_BASE_URL[mode]:
                raise ValueError("alpaca-py chose an unexpected base URL. Refusing.")
            harden_client(client)
        self.mode: Mode = mode
        self._client = client

    def __repr__(self) -> str:
        return f"AlpacaTradingBroker(mode={self.mode!r})"

    def get_account(self) -> AccountSnapshot:
        return to_account(call_broker(self._client.get_account, "get account"))

    def get_position(self, symbol: str) -> PositionSnapshot | None:
        positions = call_broker(self._client.get_all_positions, "get positions")
        matches = [to_position(item) for item in positions if str(item.symbol) == symbol]
        if len(matches) > 1:
            raise BrokerError("More than one position reported for one symbol.")
        return matches[0] if matches else None

    def asset_flags(self, symbol: str) -> AssetFlags:
        asset = call_broker(lambda: self._client.get_asset(symbol), "get asset")
        return AssetFlags(tradable=asset.tradable is True, fractionable=asset.fractionable is True)

    def list_open_orders(self, symbol: str) -> list[BrokerOrder]:
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        orders = call_broker(lambda: self._client.get_orders(filter=request), "list orders")
        return [to_order(item) for item in orders]

    def get_order_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None:
        try:
            order = call_broker(
                lambda: self._client.get_order_by_client_id(client_order_id), "order lookup"
            )
        except _NotFound:
            return None
        return to_order(order)

    def submit_order(self, request: OrderRequest) -> BrokerOrder:
        fields: dict[str, Any] = {
            "symbol": request.symbol,
            "side": OrderSide.BUY if request.side == "buy" else OrderSide.SELL,
            "time_in_force": TimeInForce.DAY,
            "client_order_id": request.client_order_id,
        }
        if request.side == "buy":
            assert request.notional is not None
            fields["notional"] = _as_float(request.notional)
        else:
            assert request.qty is not None
            fields["qty"] = _as_float(request.qty)
        order_request = MarketOrderRequest(**fields)
        try:
            order = call_broker(lambda: self._client.submit_order(order_request), "submit order")
        except _NotFound as exc:
            raise BrokerRejected(404, "order endpoint not found") from exc
        return to_order(order)

    def sessions(self, start: date, end: date) -> list[TradingSession]:
        try:
            days = call_broker(
                lambda: self._client.get_calendar(GetCalendarRequest(start=start, end=end)),
                "calendar",
            )
        except BrokerError as exc:
            raise DataUnavailable(f"Calendar unavailable: {exc}") from exc
        out: list[TradingSession] = []
        for day in days:
            open_at, close_at = day.open, day.close
            if open_at.tzinfo is None:
                open_at = open_at.replace(tzinfo=NEW_YORK)
            if close_at.tzinfo is None:
                close_at = close_at.replace(tzinfo=NEW_YORK)
            out.append(TradingSession(day.date, open_at, close_at))
        return out
