"""MAC-01 command line. The only entry point that can submit an Alpaca Trading API order.

python -m veytrix_quant.mac01 run [--submit]
python -m veytrix_quant.mac01 schedule [--submit]
python -m veytrix_quant.mac01 status | pause | resume | kill-switch [--release]
python -m veytrix_quant.mac01 backtest [--fee 1] [--spread-bps 2] [--slippage-bps 5]

Exit codes: 0 ok, 1 run error, 2 refused (unsafe config, missing credentials, or the live
gate), 3 run blocked by a safety check or bad data, 4 another instance holds the lock.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import create_engine

from veytrix_api.settings import BootRefused, get_settings
from veytrix_quant.mac01 import DISCLAIMER
from veytrix_quant.mac01.backtest import CostModel, format_result, run_backtest
from veytrix_quant.mac01.config import (
    DEFAULT_CONFIG_PATH,
    Mac01Config,
    MissingCredentials,
    TradingEnvironment,
    UnsafeConfiguration,
    assert_static_live_gate,
    credentials_for,
    load_config,
)
from veytrix_quant.mac01.data import (
    NEW_YORK,
    DataUnavailable,
    FixtureCalendar,
    bars_from_closes,
    synthetic_closes,
)
from veytrix_quant.mac01.engine import Mac01Engine
from veytrix_quant.mac01.ledger import AdvisoryLock, Ledger
from veytrix_quant.mac01.logs import configure, event
from veytrix_quant.mac01.schedule import next_run_at, sleep_until

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REFUSED = 2
EXIT_BLOCKED = 3
EXIT_LOCKED = 4


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def _database_engine():
    settings = get_settings()
    return create_engine(
        settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
    )


def _exit_for(status: str) -> int:
    return {"ok": EXIT_OK, "blocked": EXIT_BLOCKED, "refused": EXIT_REFUSED}.get(status, EXIT_ERROR)


def _prepare(config_path: Path, submit_flag: bool):
    """Every static refusal happens here, before any broker object exists."""

    get_settings()
    config = load_config(config_path)
    env = TradingEnvironment()
    configure(secrets=env.secrets())
    assert_static_live_gate(config, env, submit_flag)
    key, secret = credentials_for(config, env)
    return config, env, key, secret


def _clients(config: Mac01Config, key: str, secret: str):
    from veytrix_quant.mac01.alpaca_data import AlpacaMarketData
    from veytrix_quant.mac01.alpaca_trading import AlpacaTradingBroker

    broker = AlpacaTradingBroker(key, secret, config.mode)
    data = AlpacaMarketData(key, secret, feed=config.data_feed)
    return broker, data


def _announce(config: Mac01Config, submit_flag: bool) -> None:
    money = "REAL MONEY" if config.mode == "live" else "paper money"
    run = "submit requested" if submit_flag else "dry-run"
    print(f"MAC-01 mode={config.mode} ({money}), {run}.", flush=True)


def cmd_run(args: argparse.Namespace) -> int:
    config, env, key, secret = _prepare(Path(args.config), args.submit)
    _announce(config, args.submit)
    engine = _database_engine()
    lock = AdvisoryLock(engine)
    if not lock.acquire():
        _err("Another MAC-01 instance holds the advisory lock. Nothing was run.")
        return EXIT_LOCKED
    try:
        broker, data = _clients(config, key, secret)
        result = Mac01Engine(
            config,
            broker,
            data,
            broker,
            Ledger(engine),
            submit_flag=args.submit,
            env=env,
            secrets=env.secrets(),
        ).run()
    finally:
        lock.release()
        engine.dispose()
    print(f"{result.status}: {result.decision}: {result.reason}")
    return _exit_for(result.status)


def cmd_schedule(args: argparse.Namespace) -> int:
    config, env, key, secret = _prepare(Path(args.config), args.submit)
    _announce(config, args.submit)
    engine = _database_engine()
    lock = AdvisoryLock(engine)
    if not lock.acquire():
        _err("Another MAC-01 instance holds the advisory lock. Not scheduling.")
        return EXIT_LOCKED
    broker, data = _clients(config, key, secret)
    ledger = Ledger(engine)

    def clock() -> datetime:
        return datetime.now(UTC)

    try:
        while True:
            now = clock()
            today = now.astimezone(NEW_YORK).date()
            try:
                sessions = broker.sessions(today, today + timedelta(days=10))
            except DataUnavailable as exc:
                event("schedule_calendar_unavailable", reason=str(exc)[:200])
                time.sleep(900)
                continue
            target = next_run_at(sessions, now)
            if target is None:
                event("schedule_no_session", reason="no session in the next 10 days")
                time.sleep(3600)
                continue
            event("schedule_sleep", until=target.isoformat())
            sleep_until(target, clock, time.sleep)
            result = Mac01Engine(
                config,
                broker,
                data,
                broker,
                ledger,
                submit_flag=args.submit,
                env=env,
                secrets=env.secrets(),
            ).run()
            print(f"{result.status}: {result.decision}: {result.reason}", flush=True)
            if args.once:
                return _exit_for(result.status)
    except KeyboardInterrupt:
        return EXIT_OK
    finally:
        lock.release()
        engine.dispose()


def cmd_status(_args: argparse.Namespace) -> int:
    get_settings()
    engine = _database_engine()
    try:
        state = Ledger(engine).state()
    finally:
        engine.dispose()
    print(
        f"paused={state.paused} kill_switch={state.kill_switch} last_mode={state.last_mode} "
        f"last_run_at={state.last_run_at} last_run_status={state.last_run_status} "
        f"last_run_message={state.last_run_message}"
    )
    print(DISCLAIMER)
    return EXIT_OK


def _set_flags(**flags: bool) -> int:
    get_settings()
    engine = _database_engine()
    try:
        Ledger(engine).set_flags(**flags)
    finally:
        engine.dispose()
    print(", ".join(f"{name}={value}" for name, value in flags.items()))
    return EXIT_OK


def cmd_backtest(args: argparse.Namespace) -> int:
    sessions = FixtureCalendar().sessions(
        datetime(2024, 1, 1).date(), datetime(2026, 6, 30).date()
    )[: args.sessions]
    bars = bars_from_closes(sessions, synthetic_closes(len(sessions), seed=args.seed))
    try:
        costs = CostModel(
            fee_per_trade=Decimal(args.fee),
            spread_bps=Decimal(args.spread_bps),
            slippage_bps=Decimal(args.slippage_bps),
        )
    except InvalidOperation:
        _err("Costs must be decimals.")
        return EXIT_REFUSED
    print(format_result(run_backtest(bars, costs=costs)))
    print("Fixture bars are synthetic. They are not AAPL prices.")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m veytrix_quant.mac01", description=DISCLAIMER)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "schedule"):
        command = sub.add_parser(name)
        command.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
        command.add_argument(
            "--submit",
            action="store_true",
            help=(
                "Submit to Alpaca. Paper also needs submit_orders: true. Live needs every "
                "live-gate condition (see services/quant/README.md)."
            ),
        )
        if name == "schedule":
            command.add_argument("--once", action="store_true", help="Run one session and exit.")
    sub.add_parser("status")
    sub.add_parser("pause")
    sub.add_parser("resume")
    kill = sub.add_parser("kill-switch")
    kill.add_argument("--release", action="store_true")
    backtest = sub.add_parser("backtest")
    backtest.add_argument("--fee", default="0")
    backtest.add_argument("--spread-bps", default="0")
    backtest.add_argument("--slippage-bps", default="0")
    backtest.add_argument("--sessions", type=int, default=500)
    backtest.add_argument("--seed", type=int, default=7)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return cmd_run(args)
        if args.command == "schedule":
            return cmd_schedule(args)
        if args.command == "status":
            return cmd_status(args)
        if args.command == "pause":
            return _set_flags(paused=True)
        if args.command == "resume":
            return _set_flags(paused=False)
        if args.command == "kill-switch":
            return _set_flags(kill_switch=not args.release)
        if args.command == "backtest":
            return cmd_backtest(args)
    except (BootRefused, UnsafeConfiguration, MissingCredentials) as exc:
        _err(f"Refused: {exc}")
        return EXIT_REFUSED
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
