"""Simulated paper-swap CLI. Testnets only. Not exposed through the API.

python -m veytrix_ai.swapbot quote --chain ethereum ETH USDC 0.01
python -m veytrix_ai.swapbot swap --chain ethereum ETH USDC 0.01
python -m veytrix_ai.swapbot portfolio
python -m veytrix_ai.swapbot status
python -m veytrix_ai.swapbot kill --reason "stop"
python -m veytrix_ai.swapbot resume
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from veytrix_ai.config import DEFAULT_CONFIG_PATH, DEFAULT_STATE_DIR, ConfigError, load_config
from veytrix_ai.engine import SwapEngine
from veytrix_ai.guards import GuardError, KillSwitch, refuse_key_material
from veytrix_ai.quote import HttpTransport, MarketReader, QuoteError

KILL_FILE = "swapbot.KILL"


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, default=str, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m veytrix_ai.swapbot")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("quote", "swap"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--chain", required=True)
        cmd.add_argument("token_in")
        cmd.add_argument("token_out")
        cmd.add_argument("amount", help="decimal amount in whole-token units, e.g. 0.01")
        cmd.add_argument("--slippage-bps", type=int, default=None)
    portfolio = sub.add_parser("portfolio")
    portfolio.add_argument("--chain", default=None)
    sub.add_parser("status")
    kill = sub.add_parser("kill")
    kill.add_argument("--reason", default="")
    sub.add_parser("resume")
    return parser


def open_session() -> Session:
    from sqlalchemy.orm import Session as SessionClass

    from veytrix_api.db import create_db_engine
    from veytrix_api.settings import assert_boot_allowed, get_settings

    settings = get_settings()
    assert_boot_allowed(settings)
    return SessionClass(create_db_engine(settings))


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    session: Session | None = None,
    transport: Any = None,
) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args_list = list(sys.argv[1:] if argv is None else argv)
    if any(item == "--broadcast" for item in args_list):
        _emit({"refused": "broadcast is not available; swaps are simulated"})
        return 2
    try:
        args = _parser().parse_args(args_list)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    kill_switch = KillSwitch(args.state_dir / KILL_FILE)
    if args.command == "kill":
        kill_switch.engage(args.reason)
        _emit({"kill_switch": "engaged", "simulated": True})
        return 0
    if args.command == "resume":
        released = kill_switch.release()
        _emit({"kill_switch": "released" if released else "was not engaged", "simulated": True})
        return 0

    env = dict(environ if environ is not None else os.environ)
    owned = False
    try:
        refuse_key_material(env)
        config = load_config(args.config)
        needs_db = args.command in {"swap", "portfolio"}
        if needs_db and session is None:
            try:
                session = open_session()
            except Exception:
                _emit({"refused": "paper swap ledger is unavailable", "simulated": True})
                return 2
            owned = True
        reader = MarketReader(config, env, transport if transport is not None else HttpTransport())
        engine = SwapEngine(config, reader, kill_switch, session)
        if args.command == "quote":
            _emit(
                engine.quote(
                    args.chain, args.token_in, args.token_out, args.amount, args.slippage_bps
                )
            )
        elif args.command == "swap":
            _emit(
                engine.swap(
                    args.chain, args.token_in, args.token_out, args.amount, args.slippage_bps
                )
            )
        elif args.command == "portfolio":
            payload = engine.portfolio()
            if args.chain:
                payload["networks"] = [
                    item for item in payload["networks"] if item["chain"] == args.chain
                ]
                if not payload["networks"]:
                    raise GuardError(f"unknown chain {args.chain}")
            _emit(payload)
        elif args.command == "status":
            _emit(engine.status())
    except (GuardError, ConfigError, QuoteError) as exc:
        _emit({"refused": str(exc), "simulated": True})
        return 2
    finally:
        if owned and session is not None:
            session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
