import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import requests
from pydantic import SecretStr

from mac01_helpers import (
    ACCOUNT_NUMBER,
    FakeBroker,
    account,
    config,
    live_config,
    make_engine,
    orders,
    sqlite_engine,
    state,
    trading_env,
)
from veytrix_api.settings import get_settings
from veytrix_quant.mac01 import __main__ as cli
from veytrix_quant.mac01.alpaca_data import AlpacaMarketData
from veytrix_quant.mac01.alpaca_trading import (
    EXPECTED_BASE_URL,
    HTTP_TIMEOUT_SECONDS,
    AlpacaTradingBroker,
    BrokerRejected,
    BrokerTimeout,
    OrderRequest,
)
from veytrix_quant.mac01.config import (
    DEFAULT_CONFIG_PATH,
    LIVE_CONFIRM_PHRASE,
    LiveGateRefused,
    MissingCredentials,
    TradingEnvironment,
    UnsafeConfiguration,
    assert_static_live_gate,
    credentials_for,
    load_config,
    static_live_gate_failures,
)
from veytrix_quant.mac01.ledger import Ledger
from veytrix_quant.mac01.logs import LOGGER_NAME, SecretMaskingFilter, configure

pytestmark = pytest.mark.filterwarnings("ignore::sqlalchemy.exc.SAWarning")

PAPER_KEY = "PK" + "TESTPAPERKEY0001"
LIVE_KEY = "AK" + "TESTLIVEKEY00001"
LIVE_SECRET = "live-secret-" + "y" * 20


# Config


def test_shipped_config_is_paper_dry_run_and_capped_at_100() -> None:
    shipped = load_config(DEFAULT_CONFIG_PATH)

    assert shipped.mode == "paper"
    assert shipped.live_enabled is False
    assert shipped.submit_orders is False
    assert shipped.expected_account_number == ""
    assert shipped.allow_short_selling is False and shipped.long_only is True
    assert shipped.kill_switch is False
    assert shipped.max_notional_per_trade == Decimal("100.00")
    assert shipped.max_position_notional == Decimal("100.00")
    assert shipped.max_orders_per_day == 2
    assert shipped.data_feed == "iex"
    assert (shipped.fast_period, shipped.slow_period, shipped.history_trading_days) == (20, 50, 100)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allow_short_selling", True),
        ("long_only", False),
        ("mode", "margin"),
        ("broker", "alpaca_broker_api"),
        ("symbol", "TSLA"),
        ("max_orders_per_day", 3),
        ("max_notional_per_trade", "100.01"),
        ("max_notional_per_trade", "50.005"),
        ("max_notional_per_trade", 100.0),
        ("max_position_notional", "1000.00"),
        ("daily_loss_cutoff_usd", 0.5),
        ("submit_orders", "yes"),
        ("live_enabled", "true"),
        ("expected_account_number", 12345),
        ("data_feed", "otc"),
    ],
)
def test_unsafe_config_values_fail_closed(tmp_path: Path, field: str, value: object) -> None:
    raw = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if not line.startswith(f"{field}:")]
    lines.append(f"{field}: {json.dumps(value)}")
    path = tmp_path / "mac-01.yaml"
    path.write_text("\n".join(lines), encoding="utf-8")

    with pytest.raises(UnsafeConfiguration):
        load_config(path)


def test_per_trade_cap_cannot_exceed_position_cap() -> None:
    with pytest.raises(UnsafeConfiguration):
        config(max_notional_per_trade="100.00", max_position_notional="50.00")


def test_unknown_config_key_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "mac-01.yaml"
    path.write_text(
        DEFAULT_CONFIG_PATH.read_text(encoding="utf-8") + "\nallow_margin: true\n",
        encoding="utf-8",
    )

    with pytest.raises(UnsafeConfiguration):
        load_config(path)


def test_helper_config_matches_the_shipped_file() -> None:
    assert config(submit_orders=False) == load_config(DEFAULT_CONFIG_PATH)


# Credentials


def test_credentials_are_chosen_by_mode() -> None:
    env = trading_env()

    assert credentials_for(config(), env)[0] == PAPER_KEY
    assert credentials_for(live_config(), env) == (LIVE_KEY, LIVE_SECRET)


@pytest.mark.parametrize(
    ("mode", "missing"),
    [
        ("paper", "paper_api_key"),
        ("paper", "paper_secret_key"),
        ("live", "live_api_key"),
        ("live", "live_secret_key"),
    ],
)
def test_missing_credentials_fail_closed(mode: str, missing: str) -> None:
    cfg = config() if mode == "paper" else live_config()

    with pytest.raises(MissingCredentials):
        credentials_for(cfg, trading_env(**{missing: SecretStr("  ")}))
    with pytest.raises(MissingCredentials):
        credentials_for(cfg, trading_env(**{missing: None}))


def test_a_key_from_the_other_mode_is_refused() -> None:
    with pytest.raises(UnsafeConfiguration, match="other mode"):
        credentials_for(config(), trading_env(paper_api_key=SecretStr(LIVE_KEY)))
    with pytest.raises(UnsafeConfiguration, match="other mode"):
        credentials_for(live_config(), trading_env(live_api_key=SecretStr(PAPER_KEY)))


def test_paper_mode_never_reads_the_live_keys() -> None:
    env = trading_env(paper_api_key=None)

    with pytest.raises(MissingCredentials, match="ALPACA_PAPER"):
        credentials_for(config(), env)


# Live gate: each condition alone refuses


LIVE_GATE_BREAKS = {
    "mode": ({"mode": "paper"}, {}),
    "live_enabled": ({"live_enabled": False}, {}),
    "confirm_missing": ({}, {"live_confirm": None}),
    "confirm_wrong": ({}, {"live_confirm": SecretStr("yes")}),
    "submit_orders": ({"submit_orders": False}, {}),
    "expected_account_number": ({"expected_account_number": ""}, {}),
    "kill_switch": ({"kill_switch": True}, {}),
}


def test_static_live_gate_passes_only_when_everything_holds() -> None:
    assert static_live_gate_failures(live_config(), trading_env(), submit_flag=True) == []
    assert_static_live_gate(live_config(), trading_env(), submit_flag=True)


@pytest.mark.parametrize("name", sorted(LIVE_GATE_BREAKS))
def test_each_static_live_condition_alone_blocks_live(name: str) -> None:
    config_change, env_change = LIVE_GATE_BREAKS[name]
    cfg = live_config(**config_change)
    env = trading_env(**env_change)

    assert static_live_gate_failures(cfg, env, submit_flag=True), name
    if cfg.mode == "live":
        with pytest.raises(LiveGateRefused):
            assert_static_live_gate(cfg, env, submit_flag=True)
        with pytest.raises(LiveGateRefused):
            make_engine(sqlite_engine(), FakeBroker(mode="live"), cfg=cfg, env=env)


def test_missing_submit_flag_blocks_live_and_runs_dry() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(mode="live")

    assert "the --submit flag is absent" in static_live_gate_failures(
        live_config(), trading_env(), submit_flag=False
    )
    result = make_engine(engine, broker, cfg=live_config(), submit_flag=False).run()

    assert result.decision == "DRY_RUN" and "--submit flag is absent" in result.reason
    assert broker.submitted == [] and orders(engine) == []


def test_live_dry_run_lists_every_missing_condition() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(mode="live")
    cfg = live_config(live_enabled=False, submit_orders=False)

    result = make_engine(
        engine, broker, cfg=cfg, env=trading_env(live_confirm=None), submit_flag=False
    ).run()

    assert result.decision == "DRY_RUN"
    for text in ("--submit", "submit_orders", "live_enabled", "MAC01_LIVE_CONFIRM"):
        assert text in result.reason
    assert broker.submitted == []


def test_mode_mismatch_between_config_and_broker_refuses() -> None:
    with pytest.raises(LiveGateRefused, match="mode"):
        make_engine(sqlite_engine(), FakeBroker(mode="paper"), cfg=live_config())
    with pytest.raises(LiveGateRefused, match="mode"):
        make_engine(sqlite_engine(), FakeBroker(mode="live"), cfg=config())


@pytest.mark.parametrize(
    ("snapshot", "reason"),
    [
        (account(account_number="PA9OTHERACCT"), "does not match expected_account_number"),
        (account(account_number=""), "does not match expected_account_number"),
        (account(trading_blocked=True), "trading_blocked"),
        (account(account_blocked=True), "account_blocked"),
        (account(status="SUBMISSION_FAILED"), "account status"),
    ],
)
def test_each_runtime_live_condition_refuses(snapshot, reason: str) -> None:
    engine = sqlite_engine()
    broker = FakeBroker(mode="live", account_snapshot=snapshot)

    result = make_engine(engine, broker, cfg=live_config()).run()

    assert result.status == "refused" and result.decision == "LIVE_REFUSED", result.reason
    assert reason in result.reason
    assert broker.submitted == [] and broker.lookups == []
    assert orders(engine) == []


def test_account_mismatch_reports_only_the_last_four_characters() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(mode="live", account_snapshot=account(account_number="PA9OTHER7788"))

    result = make_engine(engine, broker, cfg=live_config()).run()

    assert "...7788" in result.reason
    assert "PA9OTHER7788" not in result.reason


def test_live_account_lookup_failure_refuses() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(mode="live", account_error=BrokerTimeout("network down"))

    result = make_engine(engine, broker, cfg=live_config()).run()

    assert result.decision == "LIVE_REFUSED" and broker.submitted == []


def test_live_kill_switch_in_the_ledger_blocks() -> None:
    engine = sqlite_engine()
    Ledger(engine).set_flags(kill_switch=True)
    broker = FakeBroker(mode="live")

    result = make_engine(engine, broker, cfg=live_config()).run()

    assert result.decision == "BLOCKED" and "kill switch" in result.reason
    assert broker.submitted == []


def test_live_submits_only_when_every_condition_holds() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(mode="live")

    result = make_engine(engine, broker, cfg=live_config()).run()

    assert result.decision == "SUBMITTED", result.reason
    [request] = broker.submitted
    assert request.notional == Decimal("100.00")
    assert request.client_order_id.startswith("mac01-live-")
    assert orders(engine)[0].mode == "live"
    assert state(engine).last_mode == "live"


# CLI: refusals happen before any broker object exists


class _NoClients:
    def __call__(self, *_args, **_kwargs):
        raise AssertionError("a broker client must not be constructed")


class _ReachedDatabase(Exception):
    pass


@pytest.fixture
def isolated_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(cli, "_clients", _NoClients())

    def no_database():
        raise _ReachedDatabase

    monkeypatch.setattr(cli, "_database_engine", no_database)
    monkeypatch.setattr(cli, "TradingEnvironment", lambda: TradingEnvironment(_env_file=None))
    monkeypatch.setenv("VEYTRIX_ENV", "local")
    monkeypatch.setenv("VEYTRIX_ENABLE_LIVE_BROKER", "0")
    for name in (
        "ALPACA_PAPER_API_KEY",
        "ALPACA_PAPER_SECRET_KEY",
        "ALPACA_LIVE_API_KEY",
        "ALPACA_LIVE_SECRET_KEY",
        "MAC01_LIVE_CONFIRM",
    ):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield monkeypatch, tmp_path
    get_settings.cache_clear()


def _write_config(tmp_path: Path, **overrides: object) -> str:
    values = config(submit_orders=False).model_dump(mode="json")
    values.update(overrides)
    path = tmp_path / "mac-01.yaml"
    path.write_text(json.dumps(values), encoding="utf-8")
    return str(path)


def test_cli_exits_non_zero_without_credentials_before_any_broker_call(isolated_cli) -> None:
    _monkeypatch, tmp_path = isolated_cli
    path = _write_config(tmp_path)

    assert cli.main(["run", "--config", path]) == cli.EXIT_REFUSED
    assert cli.main(["run", "--config", path, "--submit"]) == cli.EXIT_REFUSED
    assert cli.main(["schedule", "--config", path]) == cli.EXIT_REFUSED


def test_cli_with_mode_paper_never_uses_live_keys(isolated_cli) -> None:
    monkeypatch, tmp_path = isolated_cli
    monkeypatch.setenv("ALPACA_LIVE_API_KEY", LIVE_KEY)
    monkeypatch.setenv("ALPACA_LIVE_SECRET_KEY", LIVE_SECRET)
    monkeypatch.setenv("MAC01_LIVE_CONFIRM", LIVE_CONFIRM_PHRASE)
    path = _write_config(
        tmp_path,
        mode="paper",
        live_enabled=True,
        submit_orders=True,
        expected_account_number=ACCOUNT_NUMBER,
    )

    assert cli.main(["run", "--config", path, "--submit"]) == cli.EXIT_REFUSED


@pytest.mark.parametrize("name", sorted(set(LIVE_GATE_BREAKS) - {"mode"}))
def test_cli_live_submit_refuses_each_broken_condition_before_any_broker_call(
    isolated_cli, name: str
) -> None:
    monkeypatch, tmp_path = isolated_cli
    config_change, env_change = LIVE_GATE_BREAKS[name]
    monkeypatch.setenv("ALPACA_LIVE_API_KEY", LIVE_KEY)
    monkeypatch.setenv("ALPACA_LIVE_SECRET_KEY", LIVE_SECRET)
    if "live_confirm" not in env_change:
        monkeypatch.setenv("MAC01_LIVE_CONFIRM", LIVE_CONFIRM_PHRASE)
    elif env_change["live_confirm"] is not None:
        monkeypatch.setenv("MAC01_LIVE_CONFIRM", env_change["live_confirm"].get_secret_value())
    live = {
        "mode": "live",
        "live_enabled": True,
        "submit_orders": True,
        "expected_account_number": ACCOUNT_NUMBER,
        **config_change,
    }
    path = _write_config(tmp_path, **live)

    assert cli.main(["run", "--config", path, "--submit"]) == cli.EXIT_REFUSED
    assert cli.main(["schedule", "--config", path, "--submit"]) == cli.EXIT_REFUSED


def test_cli_live_submit_with_every_static_condition_reaches_the_database(isolated_cli) -> None:
    monkeypatch, tmp_path = isolated_cli
    monkeypatch.setenv("ALPACA_LIVE_API_KEY", LIVE_KEY)
    monkeypatch.setenv("ALPACA_LIVE_SECRET_KEY", LIVE_SECRET)
    monkeypatch.setenv("MAC01_LIVE_CONFIRM", LIVE_CONFIRM_PHRASE)
    path = _write_config(
        tmp_path,
        mode="live",
        live_enabled=True,
        submit_orders=True,
        expected_account_number=ACCOUNT_NUMBER,
    )

    with pytest.raises(_ReachedDatabase):
        cli.main(["run", "--config", path, "--submit"])


@pytest.mark.parametrize(
    ("name", "value"),
    [("VEYTRIX_ENABLE_LIVE_BROKER", "1"), ("VEYTRIX_ENV", "production")],
)
def test_cli_keeps_the_api_boot_refusals(isolated_cli, name: str, value: str) -> None:
    monkeypatch, tmp_path = isolated_cli
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", PAPER_KEY)
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "paper-secret")
    monkeypatch.setenv(name, value)
    get_settings.cache_clear()

    assert cli.main(["run", "--config", _write_config(tmp_path), "--submit"]) == cli.EXIT_REFUSED


# Adapter: hardening and mapping, with requests intercepted (no network)


class _Response:
    def __init__(self, status: int, body: object) -> None:
        self.response = requests.Response()
        self.response.status_code = status
        self.response._content = json.dumps(body).encode("utf-8")
        self.response.url = "intercepted"


@pytest.fixture
def intercepted(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict] = []
    replies: list[object] = []

    def fake_request(_session, method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        reply = replies.pop(0) if replies else _Response(200, {})
        if isinstance(reply, Exception):
            raise reply
        return reply.response

    monkeypatch.setattr(requests.Session, "request", fake_request)
    return calls, replies


ORDER_BODY = {
    "id": "61e69015-8549-4bfd-b9c3-01e75843f47d",
    "client_order_id": "mac01-paper-abc",
    "created_at": "2026-11-09T14:35:01Z",
    "updated_at": "2026-11-09T14:35:01Z",
    "submitted_at": "2026-11-09T14:35:01Z",
    "asset_id": "b0b6dd9d-8b9b-48a9-ba46-b9d54906e415",
    "symbol": "AAPL",
    "asset_class": "us_equity",
    "notional": "100",
    "qty": None,
    "filled_qty": "0",
    "filled_avg_price": None,
    "order_class": "",
    "order_type": "market",
    "type": "market",
    "side": "buy",
    "time_in_force": "day",
    "status": "accepted",
    "extended_hours": False,
}


@pytest.mark.parametrize("mode", ["paper", "live"])
def test_trading_client_uses_the_mode_host_no_retries_and_a_timeout(intercepted, mode) -> None:
    calls, replies = intercepted
    key = PAPER_KEY if mode == "paper" else LIVE_KEY
    broker = AlpacaTradingBroker(key, "s3cret-value", mode)
    replies.append(_Response(200, ORDER_BODY))

    order = broker.submit_order(
        OrderRequest("AAPL", "buy", "mac01-paper-abc", notional=Decimal("100.00"))
    )

    assert order.status == "accepted" and order.notional == Decimal(100) and order.qty is None
    [call] = calls
    assert call["method"] == "POST"
    assert call["url"] == EXPECTED_BASE_URL[mode] + "/v2/orders"
    assert call["timeout"] == HTTP_TIMEOUT_SECONDS
    assert call["allow_redirects"] is False
    assert call["json"] == {
        "symbol": "AAPL",
        "notional": 100.0,
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
        "client_order_id": "mac01-paper-abc",
    }
    assert broker._client._retry == 0
    assert "s3cret-value" not in repr(broker) and key not in repr(broker)


def test_rate_limited_submit_is_not_retried(intercepted) -> None:
    calls, replies = intercepted
    broker = AlpacaTradingBroker(PAPER_KEY, "s3cret-value", "paper")
    replies.extend([_Response(429, {"message": "rate limit"}), _Response(200, ORDER_BODY)])

    with pytest.raises(BrokerRejected):
        broker.submit_order(OrderRequest("AAPL", "buy", "mac01-x", notional=Decimal("10.00")))
    assert len(calls) == 1


def test_sell_sends_the_held_quantity(intercepted) -> None:
    calls, replies = intercepted
    broker = AlpacaTradingBroker(PAPER_KEY, "s3cret-value", "paper")
    body = {**ORDER_BODY, "side": "sell", "notional": None, "qty": "0.906618314"}
    replies.append(_Response(200, body))

    broker.submit_order(OrderRequest("AAPL", "sell", "mac01-s", qty=Decimal("0.906618314")))

    assert calls[0]["json"]["qty"] == 0.906618314 and "notional" not in calls[0]["json"]


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        (requests.exceptions.ReadTimeout("slow"), BrokerTimeout),
        (requests.exceptions.ConnectionError("down"), BrokerTimeout),
        (_Response(504, {"message": "gateway"}), BrokerTimeout),
        (_Response(422, {"message": "client_order_id must be unique"}), BrokerTimeout),
        (_Response(403, {"message": "insufficient buying power"}), BrokerRejected),
    ],
)
def test_adapter_maps_errors_so_unknown_outcomes_get_looked_up(intercepted, reply, error) -> None:
    _calls, replies = intercepted
    broker = AlpacaTradingBroker(PAPER_KEY, "s3cret-value", "paper")
    replies.append(reply)

    with pytest.raises(error) as caught:
        broker.submit_order(OrderRequest("AAPL", "buy", "mac01-e", notional=Decimal("5.00")))
    assert "s3cret-value" not in str(caught.value) and PAPER_KEY not in str(caught.value)


def test_missing_order_lookup_returns_none(intercepted) -> None:
    calls, replies = intercepted
    broker = AlpacaTradingBroker(PAPER_KEY, "s3cret-value", "paper")
    replies.append(_Response(404, {"message": "order not found"}))

    assert broker.get_order_by_client_order_id("mac01-missing") is None
    assert calls[0]["url"].endswith("/v2/orders:by_client_order_id")
    assert calls[0]["params"] == {"client_order_id": "mac01-missing"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"notional": Decimal("100.01")},
        {"notional": Decimal("0.99")},
        {"notional": Decimal("10.001")},
        {"notional": Decimal("10.00"), "qty": Decimal(1)},
        {"qty": Decimal(1)},
    ],
)
def test_buy_requests_outside_the_caps_cannot_be_built(kwargs) -> None:
    with pytest.raises(ValueError):
        OrderRequest("AAPL", "buy", "mac01-x", **kwargs)


def test_sell_requests_must_be_a_positive_quantity() -> None:
    for kwargs in ({"qty": Decimal(0)}, {"qty": Decimal(-1)}, {"notional": Decimal("10.00")}):
        with pytest.raises(ValueError):
            OrderRequest("AAPL", "sell", "mac01-x", **kwargs)


def test_market_data_requests_adjusted_iex_daily_bars_as_decimals(intercepted) -> None:
    calls, replies = intercepted
    replies.append(
        _Response(
            200,
            {
                "bars": {
                    "AAPL": [
                        {
                            "t": "2026-11-05T05:00:00Z",
                            "o": 227.1,
                            "h": 228.9,
                            "l": 226.05,
                            "c": 227.52,
                            "v": 1000,
                            "n": 10,
                            "vw": 227.4,
                        }
                    ]
                },
                "next_page_token": None,
            },
        )
    )
    data = AlpacaMarketData(PAPER_KEY, "s3cret-value", feed="iex")

    [bar] = data.daily_bars("AAPL", date(2026, 11, 1), date(2026, 11, 6))

    assert bar.session_date == date(2026, 11, 5)
    assert bar.close == Decimal("227.52") and isinstance(bar.close, Decimal)
    params = calls[0]["params"]
    assert calls[0]["url"].startswith("https://data.alpaca.markets/v2/stocks/bars")
    assert params["adjustment"] == "all" and params["feed"] == "iex"
    assert str(params["timeframe"]) == "1Day" and params["symbols"] == "AAPL"
    assert calls[0]["timeout"] == HTTP_TIMEOUT_SECONDS
    assert "s3cret-value" not in repr(data)


# Secrets never appear in logs or repr


def test_secret_masking_filter_masks_messages_and_extras() -> None:
    record = logging.makeLogRecord(
        {"msg": f"failed with key {PAPER_KEY}", "detail": "secret s3cret here"}
    )

    SecretMaskingFilter((PAPER_KEY, "s3cret")).filter(record)

    assert PAPER_KEY not in record.getMessage()
    assert "s3cret" not in record.__dict__["detail"]


def test_trading_environment_repr_hides_every_secret() -> None:
    env = trading_env()
    text = repr(env) + str(env) + str(env.model_dump())

    for value in env.secrets():
        assert value not in text
    assert LIVE_CONFIRM_PHRASE not in text


def test_secrets_never_reach_logs_or_output(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    env = trading_env()
    secrets = env.secrets()
    logger = configure(secrets=secrets)
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    leaked = f"bad key {PAPER_KEY} secret paper-secret-{'x' * 20}"
    broker = FakeBroker(submit_error=BrokerRejected(401, leaked))
    engine = sqlite_engine()
    try:
        runner = make_engine(engine, broker, env=env, secrets=secrets)
        logging.getLogger(LOGGER_NAME).info("planted", extra={"event": "planted", "detail": leaked})
        result = runner.run()
        real = AlpacaTradingBroker(PAPER_KEY, "paper-secret-" + "x" * 20, "paper")
        print(repr(real), repr(AlpacaMarketData(PAPER_KEY, "paper-secret", feed="iex")))
        print(repr(env), str(env))
    finally:
        logger.removeHandler(caplog.handler)

    captured = capsys.readouterr()
    logged = caplog.text + " ".join(str(record.__dict__) for record in caplog.records)
    assert result.decision == "REJECTED"
    assert caplog.records, "expected structured log records"
    for value in secrets:
        assert value not in captured.out
        assert value not in captured.err
        assert value not in logged
        assert value not in result.reason
        assert value not in (orders(engine)[0].last_error or "")
