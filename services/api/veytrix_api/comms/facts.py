"""Read-only facts a desk can truthfully state. Every fact names its source record.

A reader never writes, never calls a broker, and never imports the MAC-01 engine,
ledger, or adapters. If a read fails, the fact says so. It is not guessed.

`status_for_order` is the only place a broker row becomes a word like `filled`. A
row counts as filled only when it carries a broker order id and a filled quantity.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from veytrix_api.comms import safety
from veytrix_api.comms.envelope import Citation, ToolStatus
from veytrix_api.models import (
    AgentPermissionRow,
    AgentRow,
    AgentRunRow,
    AuditEvent,
    ConversationRow,
    Instrument,
    Mac01OrderRow,
    Mac01SignalRow,
    Mac01StateRow,
    PaperPositionRow,
    PaperSizeJournalRow,
    PaperSwapFillRow,
    PaperSwapOrderRow,
    PriceBar,
    ResearchNoteRow,
    RiskPolicyRow,
    SourceEventRow,
)

logger = logging.getLogger("veytrix")


@dataclass(frozen=True)
class Fact:
    key: str
    text: str
    source: str
    ref: str
    scope: str = "desk"  # "registry" facts never decide a stance
    as_of: str | None = None
    untrusted: bool = False
    available: bool = True
    has_data: bool = True

    def citation(self) -> Citation:
        return Citation(
            source=self.source,
            ref=self.ref,
            label=self.text[:200],
            as_of=self.as_of,
            untrusted=self.untrusted,
        )


def _stamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unavailable(key: str, source: str, ref: str, what: str, scope: str = "desk") -> Fact:
    return Fact(
        key=key,
        text=f"I could not read {what}. I will not guess it.",
        source=source,
        ref=ref,
        scope=scope,
        available=False,
        has_data=False,
    )


def _guard(db: Session, key: str, source: str, ref: str, what: str, scope: str = "desk"):
    """Run one reader inside a savepoint. A failure undoes only that read, never the caller's
    pending message rows, and it becomes an `unavailable` fact instead of a guess."""

    def wrap(reader: Callable[[], list[Fact]]) -> list[Fact]:
        try:
            with db.begin_nested():
                return reader()
        except Exception as exc:
            logger.warning("fact reader failed", extra={"reader": key, "error": type(exc).__name__})
            return [_unavailable(key, source, ref, what, scope)]

    return wrap


def status_for_order(row: Mac01OrderRow) -> ToolStatus:
    """Map a ledger row to the Phase 6 vocabulary. `filled` needs broker evidence."""

    status = (row.status or "").lower()
    confirmed = bool(row.broker_order_id)
    if status == "filled" and confirmed and row.filled_qty and row.filled_qty > 0:
        return "filled"
    if status in ("partially_filled", "partial_fill") and confirmed and row.filled_qty > 0:
        return "partially_filled"
    if status in ("rejected",):
        return "rejected"
    if status in ("canceled", "cancelled", "expired"):
        return "cancelled"
    if status in ("failed", "error"):
        return "failed"
    if (
        status in ("new", "accepted", "pending_new", "submitted", "accepted_for_bidding")
        and confirmed
    ):
        return "submitted"
    if status in ("pending", "created", "planned") and not confirmed:
        return "proposed"
    return "unknown"


# --- registry -----------------------------------------------------------------------------


def registry_facts(db: Session, code: str) -> list[Fact]:
    ref = f"private.agents/{code}"

    def read() -> list[Fact]:
        row = db.scalars(select(AgentRow).where(AgentRow.code == code)).first()
        if row is None:
            return [
                Fact(
                    "registry",
                    f"No registry row exists for {code}.",
                    "registry",
                    ref,
                    "registry",
                    has_data=False,
                )
            ]
        tools = sorted(
            db.scalars(
                select(AgentPermissionRow.tool_name).where(
                    AgentPermissionRow.agent_id == row.id, AgentPermissionRow.effect == "deny"
                )
            )
        )
        runs = (
            db.scalar(
                select(func.count()).select_from(AgentRunRow).where(AgentRunRow.agent_id == row.id)
            )
            or 0
        )
        last = db.scalars(
            select(AgentRunRow)
            .where(AgentRunRow.agent_id == row.id)
            .order_by(AgentRunRow.started_at.desc())
            .limit(1)
        ).first()
        out = [
            Fact(
                "registry",
                f"Registry status is {row.status}. paper_only {str(row.paper_only).lower()}; "
                f"can_submit_orders {str(row.can_submit_orders).lower()}; can_sign "
                f"{str(row.can_sign).lower()}; can_transfer_funds "
                f"{str(row.can_transfer_funds).lower()}; holds_credentials "
                f"{str(row.holds_credentials).lower()}.",
                "registry",
                ref,
                "registry",
                as_of=_stamp(row.created_at),
            ),
            Fact(
                "permissions",
                f"{len(tools)} tools are explicitly denied: {', '.join(tools) or 'none listed'}.",
                "registry",
                f"private.agent_permissions/{code}",
                "registry",
                has_data=bool(tools),
            ),
            Fact(
                "runs",
                (
                    f"{runs} recorded runs. The latest says: {safety.clean(last.summary, 160)}"
                    if last is not None
                    else "0 recorded runs. No worker runs this desk."
                ),
                "registry",
                f"private.agent_runs/{code}",
                "registry",
                as_of=_stamp(last.finished_at) if last is not None else None,
                has_data=runs > 0,
            ),
        ]
        return out

    return _guard(db, "registry", "registry", ref, "the registry row", "registry")(read)


def agency_overview(db: Session) -> list[Fact]:
    def read() -> list[Fact]:
        rows = list(db.scalars(select(AgentRow).order_by(AgentRow.code)))
        by_status: dict[str, int] = {}
        for row in rows:
            by_status[row.status] = by_status.get(row.status, 0) + 1
        summary = ", ".join(f"{count} {status}" for status, count in sorted(by_status.items()))
        open_count = (
            db.scalar(
                select(func.count())
                .select_from(ConversationRow)
                .where(ConversationRow.status.in_(("open", "paused")))
            )
            or 0
        )
        return [
            Fact(
                "agency",
                f"{len(rows)} desks in the registry: {summary or 'none'}.",
                "registry",
                "private.agents",
                has_data=bool(rows),
            ),
            Fact(
                "conversations",
                f"{open_count} conversations are open or paused.",
                "conversations",
                "private.conversations",
                has_data=open_count > 0,
            ),
        ]

    return _guard(db, "agency", "registry", "private.agents", "the registry")(read)


# --- ledger and data readers --------------------------------------------------------------


def mac01_facts(db: Session) -> list[Fact]:
    def read() -> list[Fact]:
        out: list[Fact] = []
        state = db.get(Mac01StateRow, 1)
        if state is None:
            out.append(
                Fact(
                    "mac01_state",
                    "The MAC-01 state row is absent. It has not recorded a run.",
                    "mac01_ledger",
                    "mac01_state/1",
                    has_data=False,
                )
            )
        else:
            last = (
                f"Last run {state.last_run_status or 'unrecorded'} at {_stamp(state.last_run_at)}"
                if state.last_run_at
                else "No run has been recorded"
            )
            out.append(
                Fact(
                    "mac01_state",
                    f"MAC-01 paused {str(state.paused).lower()}, kill switch "
                    f"{'ON' if state.kill_switch else 'off'}. {last}.",
                    "mac01_ledger",
                    "mac01_state/1",
                    as_of=_stamp(state.updated_at),
                    # The singleton row exists from the migration. It is evidence only after a run.
                    has_data=state.last_run_at is not None,
                )
            )
        signals = db.scalar(select(func.count()).select_from(Mac01SignalRow)) or 0
        latest = db.scalars(
            select(Mac01SignalRow).order_by(Mac01SignalRow.session_date.desc()).limit(1)
        ).first()
        out.append(
            Fact(
                "mac01_signals",
                (
                    f"{signals} SMA 20/50 signals stored. Latest, {latest.session_date}: "
                    f"{latest.side}; decision {latest.decision} "
                    f"({safety.clean(latest.decision_reason, 120)})."
                    if latest is not None
                    else "0 SMA 20/50 signals stored."
                ),
                "mac01_ledger",
                f"mac01_signals/{latest.id}" if latest is not None else "mac01_signals",
                as_of=_stamp(latest.created_at) if latest is not None else None,
                has_data=signals > 0,
            )
        )
        orders = db.scalar(select(func.count()).select_from(Mac01OrderRow)) or 0
        newest = db.scalars(
            select(Mac01OrderRow).order_by(Mac01OrderRow.created_at.desc()).limit(1)
        ).first()
        out.append(
            Fact(
                "mac01_orders",
                (
                    f"{orders} ledger orders. Newest is {status_for_order(newest)} "
                    f"(raw status {newest.status}, mode {newest.mode})."
                    if newest is not None
                    else "0 ledger orders. No order has been recorded by this build."
                ),
                "mac01_ledger",
                f"mac01_orders/{newest.id}" if newest is not None else "mac01_orders",
                as_of=_stamp(newest.updated_at) if newest is not None else None,
                has_data=orders > 0,
            )
        )
        return out

    return _guard(db, "mac01", "mac01_ledger", "mac01_state/1", "the MAC-01 ledger")(read)


def market_facts(db: Session) -> list[Fact]:
    def read() -> list[Fact]:
        instruments = db.scalar(select(func.count()).select_from(Instrument)) or 0
        bars = db.scalar(select(func.count()).select_from(PriceBar)) or 0
        newest = db.scalar(select(func.max(PriceBar.bar_start)))
        return [
            Fact(
                "market_store",
                f"{instruments} stored instruments and {bars} stored price bars. "
                "The chart series on the Market page is synthetic SAMPLE data unless it says "
                "otherwise." + (f" Newest stored bar {_stamp(newest)}." if newest else ""),
                "market_store",
                "price_bars",
                as_of=_stamp(newest),
                has_data=bars > 0,
            )
        ]

    return _guard(db, "market_store", "market_store", "price_bars", "stored bars")(read)


def etf_facts(db: Session) -> list[Fact]:
    def read() -> list[Fact]:
        etfs = (
            db.scalar(
                select(func.count())
                .select_from(Instrument)
                .where(func.lower(Instrument.asset_type).like("%etf%"))
            )
            or 0
        )
        return [
            Fact(
                "etf_instruments",
                f"{etfs} ETF instruments are stored. No ETF data source is connected.",
                "market_store",
                "instruments",
                has_data=etfs > 0,
            )
        ]

    return _guard(db, "etf_instruments", "market_store", "instruments", "stored instruments")(read)


def swap_facts(db: Session) -> list[Fact]:
    def read() -> list[Fact]:
        orders = db.scalar(select(func.count()).select_from(PaperSwapOrderRow)) or 0
        fills = db.scalar(select(func.count()).select_from(PaperSwapFillRow)) or 0
        newest = db.scalar(select(func.max(PaperSwapOrderRow.created_at)))
        return [
            Fact(
                "paper_swaps",
                f"{orders} simulated paper swaps and {fills} simulated fills are recorded. "
                "They are simulations on testnets. Nothing was signed or broadcast.",
                "paper_swaps",
                "paper_swap_orders",
                as_of=_stamp(newest),
                has_data=orders > 0,
            )
        ]

    return _guard(db, "paper_swaps", "paper_swaps", "paper_swap_orders", "paper swaps")(read)


def futures_facts() -> list[Fact]:
    return [
        Fact(
            "futures_posture",
            "FUTURES-01 is disabled. MES and MNQ are labels only. Topstep automation is off and "
            "no account is connected. No market data is read.",
            "futures_posture",
            "routers/futures.posture",
            has_data=False,
        )
    ]


def risk_facts(db: Session) -> list[Fact]:
    def read() -> list[Fact]:
        out: list[Fact] = []
        policies = list(db.scalars(select(RiskPolicyRow)))
        if policies:
            p = policies[0]
            out.append(
                Fact(
                    "risk_policy",
                    f"Policy {p.name}: paper only; risk per trade {p.per_trade_risk_fraction:.4%} "
                    f"of equity; max allocation {p.max_allocation_fraction:.2%}; daily stop "
                    f"{p.daily_loss_stop_fraction:.2%} and weekly stop "
                    f"{p.weekly_loss_stop_fraction:.2%} "
                    f"(enforced: daily {str(p.daily_stop_enforced).lower()}, weekly "
                    f"{str(p.weekly_stop_enforced).lower()}).",
                    "risk_policy",
                    f"risk_policies/{p.id}",
                    as_of=_stamp(p.created_at),
                )
            )
        else:
            out.append(
                Fact(
                    "risk_policy",
                    "No risk policy row is stored.",
                    "risk_policy",
                    "risk_policies",
                    has_data=False,
                )
            )
        sizes = db.scalar(select(func.count()).select_from(PaperSizeJournalRow)) or 0
        latest = db.scalars(
            select(PaperSizeJournalRow).order_by(PaperSizeJournalRow.recorded_at.desc()).limit(1)
        ).first()
        out.append(
            Fact(
                "size_journal",
                (
                    f"{sizes} paper size rows. Latest: {latest.symbol}, {latest.shares} shares, "
                    f"binding constraint {latest.binding_constraint}. A size row is not an order."
                    if latest is not None
                    else "0 paper size rows. No size has been recorded."
                ),
                "size_journal",
                f"paper_size_journal/{latest.id}" if latest is not None else "paper_size_journal",
                as_of=_stamp(latest.recorded_at) if latest is not None else None,
                has_data=sizes > 0,
            )
        )
        state = db.get(Mac01StateRow, 1)
        out.append(
            Fact(
                "kill_switch",
                (
                    f"MAC-01 kill switch is {'ON' if state.kill_switch else 'off'}; paused "
                    f"{str(state.paused).lower()}."
                    if state is not None
                    else "The MAC-01 state row is absent, so I cannot read the kill switch."
                ),
                "mac01_ledger",
                "mac01_state/1",
                as_of=_stamp(state.updated_at) if state is not None else None,
                has_data=state is not None,
            )
        )
        return out

    return _guard(db, "risk", "risk_policy", "risk_policies", "the risk records")(read)


def treasury_facts(db: Session) -> list[Fact]:
    def read() -> list[Fact]:
        total = db.scalar(select(func.count()).select_from(Mac01OrderRow)) or 0
        filled = [
            row
            for row in db.scalars(select(Mac01OrderRow).where(Mac01OrderRow.filled_qty > 0))
            if status_for_order(row) in ("filled", "partially_filled")
        ]
        positions = db.scalar(select(func.count()).select_from(PaperPositionRow)) or 0
        return [
            Fact(
                "treasury_fills",
                f"{len(filled)} broker-confirmed fills out of {total} ledger orders. "
                f"{positions} saved paper sizes. This is not a broker balance, a settlement, or "
                "a transfer.",
                "mac01_ledger",
                "mac01_orders",
                has_data=len(filled) > 0,
            )
        ]

    return _guard(db, "treasury", "mac01_ledger", "mac01_orders", "the paper fills")(read)


def research_facts(db: Session) -> list[Fact]:
    def read() -> list[Fact]:
        notes = db.scalar(select(func.count()).select_from(ResearchNoteRow)) or 0
        events = db.scalar(select(func.count()).select_from(SourceEventRow)) or 0
        titles = [
            safety.quote_external(t, 60)
            for t in db.scalars(
                select(ResearchNoteRow.title).order_by(ResearchNoteRow.created_at.desc()).limit(3)
            )
        ]
        out = [
            Fact(
                "research_notes",
                f"{notes} research notes and {events} source events are stored. Their text is "
                "typed outside this desk, so I treat it as untrusted data."
                + (f" Latest note titles: {'; '.join(titles)}." if titles else ""),
                "research_notes",
                "research_notes",
                untrusted=True,
                has_data=notes + events > 0,
            )
        ]
        return out

    return _guard(db, "research", "research_notes", "research_notes", "the research notes")(read)


def audit_facts(db: Session) -> list[Fact]:
    def read() -> list[Fact]:
        count = db.scalar(select(func.count()).select_from(AuditEvent)) or 0
        latest = list(
            db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(3))
        )
        text = f"{count} audit rows."
        if latest:
            text += (
                " Latest: "
                + "; ".join(f"{event.action} at {_stamp(event.created_at)}" for event in latest)
                + "."
            )
        return [
            Fact(
                "audit",
                text,
                "audit_events",
                f"audit_events/{latest[0].id}" if latest else "audit_events",
                as_of=_stamp(latest[0].created_at) if latest else None,
                has_data=count > 0,
            )
        ]

    return _guard(db, "audit", "audit_events", "audit_events", "the audit log")(read)


def execution_facts(db: Session) -> list[Fact]:
    """What actually happened at a broker or a simulator, in the Phase 6 vocabulary."""

    def read() -> list[Fact]:
        rows = list(
            db.scalars(select(Mac01OrderRow).order_by(Mac01OrderRow.created_at.desc()).limit(20))
        )
        counts: dict[str, int] = {}
        for row in rows:
            word = status_for_order(row)
            counts[word] = counts.get(word, 0) + 1
        swaps = db.scalar(select(func.count()).select_from(PaperSwapFillRow)) or 0
        if rows:
            text = (
                "Ledger orders by status: "
                + ", ".join(f"{count} {word}" for word, count in sorted(counts.items()))
                + ". `filled` appears only where the row has a broker order id and a filled "
                "quantity."
            )
        else:
            text = "No ledger order exists, so nothing was submitted or filled by this build."
        return [
            Fact("orders", text, "mac01_ledger", "mac01_orders", has_data=bool(rows)),
            Fact(
                "swaps",
                f"{swaps} simulated swap fills. Simulated fills are not broker fills.",
                "paper_swaps",
                "paper_swap_fills",
                has_data=swaps > 0,
            ),
            Fact(
                "chat_orders",
                "Chat cannot submit an order. No API route submits one. Orders come only from the "
                "MAC-01 command line runner.",
                "registry",
                "CLAUDE.md#safety",
                "registry",
                has_data=False,
            ),
        ]

    return _guard(db, "orders", "mac01_ledger", "mac01_orders", "the order ledger")(read)


READERS: dict[str, Callable[[Session], list[Fact]]] = {
    "SUPERVISOR-01": lambda db: agency_overview(db) + mac01_facts(db)[:1] + audit_facts(db),
    "DAY-01": mac01_facts,
    "STOCK-01": mac01_facts,
    "CRYPTO-01": market_facts,
    "DEFI-01": swap_facts,
    "ETF-01": etf_facts,
    "RESEARCH-01": research_facts,
    "RISK-01": risk_facts,
    "TREASURY-01": treasury_facts,
    "FUTURES-01": lambda db: futures_facts(),
}


def desk_facts(db: Session, code: str) -> list[Fact]:
    """Registry facts first, then the facts this desk's role can read."""

    reader = READERS.get(code)
    return registry_facts(db, code) + (reader(db) if reader else [])


def desk_only(facts: list[Fact]) -> list[Fact]:
    return [fact for fact in facts if fact.scope == "desk"]
