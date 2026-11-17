"""The close's flux (C-01-T25; C-01 §3 F7; SPEC-655 AC-48, AC-49; CLS-10; DEC-5411; amber).

- **Sets**: month over month (the close month against the month before) and year over year (the
  same month a year earlier), over the income statement's accounts: the month's activity plus the
  close's pending and approved AJEs not yet recorded in the ledger (adjusted figures), with
  the shared dual-threshold rule (`workpapers.compute.flux`): a line is over only when both legs
  are (the firm's `variance_thresholds` row `close_flux`; unset reads 10% and $2,500). A month
  the ledger does not hold makes every line **not comparable** (dashes; nothing to explain). A
  changed input is a new set version; lines are insert-only and their status moves forward.
- **Line ids**: `analytic_lines` is keyed by (set, position) with a unique line key; the API's
  `line_id` is `md5(set_id:line_key)` read as a UUID, computed the same way in SQL (DEC-5411).
- **Explanation**: a person's text, a new sealed explanation version under `If-Match` (the line's
  row version: explanations so far + 1); an agent's draft arrives only as a suggestion (C-01-T30).
- **Accept**: a Manager or Partner (the matrix's `flux.accept`), never a Senior, never the agent,
  accepts the newest explanation; emits `analytic_line.accepted` for C-02's commentary.
- **Export**: a deterministic workbook of the set as CLS-10 shows it.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.safe_xlsx import Cell, Sheet, workbook
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.closes import repository as repo
from abacus.modules.closes.contract_work import FluxLineOut, FluxSetOut
from abacus.modules.closes.events import AnalyticLineExplained, AnalyticSetComputed
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.workpapers import api as engine

Basis = Literal["mom", "yoy"]
TARGET: Final = "analytic_set"
FINGERPRINT: Final = "closes.flux_explanation"
DEFAULT_PCT: Final = Decimal("10")
DEFAULT_AMOUNT: Final = Decimal("2500")
_TENTH: Final = Decimal("0.1")
_KEY_BAD: Final = re.compile(r"[^A-Za-z0-9_.:-]")
# An AJE counts until it is rejected or withdrawn; once recorded in QuickBooks the ledger has it.
_LIVE: Final = frozenset(
    {"proposed", "within_threshold", "review_required", "approved", "client_approved"}
)
_I = classified("internal")


class AnalyticLineAccepted(DomainEvent):
    """C-02's commentary reads accepted flux lines."""

    event_type: ClassVar[str] = "analytic_line.accepted"

    close_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    set_id: Annotated[UUID, _I]
    line_key: Annotated[str, _I]


class FluxStale(DomainConflict):
    code = "stale_version"


class NothingToAccept(DomainConflict):
    code = "flux_line_not_explained"


class NothingToExplain(DomainConflict):
    code = "flux_line_within_threshold"


class LineAccepted(DomainConflict):
    """An accepted line's explanation is final for its set (a new set version reopens nothing)."""

    code = "flux_line_accepted"


def prior_period(period: str, basis: Basis) -> str:
    year, month = (int(x) for x in period.split("-"))
    if basis == "yoy":
        return f"{year - 1:04d}-{month:02d}"
    return f"{year - 1:04d}-12" if month == 1 else f"{year:04d}-{month - 1:02d}"


def line_id(set_id: UUID, key: str) -> UUID:
    """The API's id for a line; `_LINE_BY_ID` computes the same in SQL."""
    return UUID(hashlib.md5(f"{set_id}:{key}".encode(), usedforsecurity=False).hexdigest())


def line_key(external_id: str) -> str:
    """The ledger's account id as a line key (the table's pattern; QuickBooks ids are digits)."""
    key = _KEY_BAD.sub("_", external_id)[:128]
    return key if key[:1].isalnum() else f"a{key}"[:128]


async def thresholds(tenant: TenantContext) -> tuple[engine.Thresholds, UUID | None]:
    """The firm's `close_flux` variance row in effect, else 10% and $2,500."""
    from abacus.kernel.clock import today
    from abacus.modules.methodology.api import current_version_of_kind, policy_payload

    policy = await current_version_of_kind(
        tenant.tenant_id, "variance_thresholds", await today(tenant)
    )
    if policy is None:
        return engine.Thresholds(DEFAULT_PCT, DEFAULT_AMOUNT), None
    payload = await policy_payload(tenant.tenant_id, policy, "variance_thresholds")
    rows = cast("list[dict[str, object]]", (payload or {}).get("rows") or [])
    row = next((r for r in rows if r.get("context") == "close_flux"), None)
    if row is None:
        return engine.Thresholds(DEFAULT_PCT, DEFAULT_AMOUNT), policy.version_id
    return (
        engine.Thresholds(Decimal(str(row["pct"])), Decimal(str(row["amount_usd"]))),
        policy.version_id,
    )


def threshold_label(t: engine.Thresholds) -> str:
    return f"{t.pct.normalize():f}% and ${t.amount:,.0f}"


@dataclass(frozen=True)
class Source:
    key: str
    caption: str
    current: Decimal
    prior: Decimal | None


@dataclass(frozen=True)
class Line:
    position: int
    key: str
    caption: str
    prior: Decimal | None
    current: Decimal
    change: Decimal | None
    pct: Decimal | None
    test: Literal["within", "over_both", "not_comparable"]
    status: Literal["within_threshold", "unexplained"]


def lines_of(source: list[Source], t: engine.Thresholds) -> list[Line]:
    """Each account as a line: not comparable without a prior; else both legs or within."""
    out: list[Line] = []
    for n, s in enumerate(source):
        if s.prior is None:
            out.append(
                Line(n, s.key, s.caption, None, s.current, None, None, "not_comparable",
                     "within_threshold")
            )  # fmt: skip
            continue
        change = s.current - s.prior
        pct = engine.flux_change_pct(s.current, s.prior)
        over = engine.classify_flux(change, pct, t) == "over"
        out.append(
            Line(n, s.key, s.caption, s.prior, s.current, change, pct,
                 "over_both" if over else "within",
                 "unexplained" if over else "within_threshold")
        )  # fmt: skip
    return out


def inputs_hash(basis: Basis, source: list[Source], t: engine.Thresholds) -> str:
    payload = {
        "basis": basis,
        "engine": engine.FLUX_ENGINE_VERSION,
        "t": [str(t.pct), str(t.amount)],
        "lines": [[s.key, s.caption, str(s.current), None if s.prior is None else str(s.prior)]
                  for s in source],
    }  # fmt: skip
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def adjusted(
    activity: Decimal, entries: list[tuple[str, Decimal, Decimal]], account: str, income: bool
) -> Decimal:
    """The month's activity (natural sign) plus the close's AJE lines on the account."""
    net = sum(((d - c) for code, d, c in entries if code == account), Decimal(0))
    return activity + (-net if income else net)


async def _entry_lines(ctx: AuthContext, close_id: UUID) -> list[tuple[str, Decimal, Decimal]]:
    from abacus.modules.adjustments.api import entries_of

    async with tenant_session(ctx.tenant) as session:
        recorded = {
            cast(UUID, r[0])
            for r in await session.execute(
                text("SELECT proposed_entry_id FROM close_entry_recordings WHERE close_id = :c"),
                {"c": close_id},
            )
        }
    return [
        (ln.account_code, ln.debit, ln.credit)
        for e in await entries_of(ctx, close_id, "aje")
        if e.status in _LIVE and e.id not in recorded
        for ln in e.lines
    ]


async def _source(ctx: AuthContext, close: repo.CloseRow, basis: Basis) -> list[Source]:
    from abacus.modules.ledger.api import PeriodNotAvailable, account_tree, monthly_balances

    tenant = ctx.tenant
    if close.client_entity_id is None:
        raise NotFound("client_entity")
    tree = await account_tree(tenant, close.client_entity_id, close.period)
    pnl = [a for a in tree.accounts if a.classification in ("income", "expense")]
    before = prior_period(close.period, basis)
    try:
        months = await monthly_balances(tenant, close.client_entity_id, [close.period, before])
    except PeriodNotAvailable:
        months = []
    current = {m.external_id: m.activity for m in months if m.period == close.period}
    prior = {m.external_id: m.activity for m in months if m.period == before}
    held = bool(prior)
    entries = await _entry_lines(ctx, close.work_item_id)
    return [
        Source(
            line_key(a.external_id),
            a.name[:200] or a.external_id,
            adjusted(
                current.get(a.external_id, Decimal(0)),
                entries,
                a.external_id,
                a.classification == "income",
            ),
            prior.get(a.external_id, Decimal(0)) if held else None,
        )
        for a in pnl
    ]


_LATEST: Final = text(
    "SELECT id, version, inputs_hash FROM analytic_sets WHERE close_id = :c AND basis = :b "
    "ORDER BY version DESC LIMIT 1"
)
_INSERT_SET: Final = text(
    "INSERT INTO analytic_sets (tenant_id, close_id, basis, threshold_policy_version_id, version, "
    "engine_version, inputs_hash) VALUES (:t, :c, :b, :p, :v, :e, :h) RETURNING id"
)
_INSERT_LINE: Final = text(
    "INSERT INTO analytic_lines (tenant_id, set_id, position, line_key, caption, prior, current, "
    "change, change_pct, test, status) VALUES (:t, :s, :pos, :k, :cap, :prior, :cur, :chg, :pct, "
    ":test, :status)"
)
_LINES: Final = text(
    "SELECT position, line_key, caption, prior, current, change, change_pct, test, status "
    "FROM analytic_lines WHERE set_id = :s ORDER BY position"
)
_NEWEST: Final = text(
    "SELECT DISTINCT ON (line_key) id, line_key, version, text_sealed, accepted_by "
    "FROM analytic_explanations WHERE close_id = :c ORDER BY line_key, version DESC"
)
_LINE_BY_ID: Final = text(
    "SELECT l.set_id, l.line_key, l.test, l.status, s.close_id, s.basis FROM analytic_lines l "
    "JOIN analytic_sets s ON s.id = l.set_id "
    "WHERE md5(l.set_id::text || ':' || l.line_key)::uuid = :id"
)
_INSERT_EXPLANATION: Final = text(
    "INSERT INTO analytic_explanations (tenant_id, close_id, line_key, version, text_sealed, "
    "author_kind) VALUES (:t, :c, :k, :v, :sealed, 'human') RETURNING id"
)
_ACCEPT: Final = text(
    "UPDATE analytic_explanations SET accepted_by = :by, accepted_actor_kind = 'human', "
    "accepted_at = clock_timestamp() WHERE id = :id AND accepted_by IS NULL RETURNING id"
)
_ADVANCE: Final = text(
    "UPDATE analytic_lines SET status = :status WHERE set_id = :s AND line_key = :k "
    "AND test = 'over_both' AND status <> :status AND status <> 'accepted'"
)


async def compute(ctx: AuthContext, close_id: UUID, basis: Basis) -> UUID:
    """The close's newest set for the basis: a new version when its inputs changed."""
    tenant = ctx.tenant
    async with tenant_session(tenant) as session:
        close = await repo.close_row(session, close_id)
        latest = (await session.execute(_LATEST, {"c": close_id, "b": basis})).mappings().first()
    if close is None:
        raise NotFound("close")
    t, policy = await thresholds(tenant)
    source = await _source(ctx, close, basis)
    digest = inputs_hash(basis, source, t)
    if latest is not None and latest["inputs_hash"] == digest:
        return cast(UUID, latest["id"])
    lines = lines_of(source, t)
    version = 1 if latest is None else int(cast(int, latest["version"])) + 1
    async with uow(tenant) as tx:
        done = {
            str(r["line_key"]): "accepted" if r["accepted_by"] else "explained"
            for r in (await tx.session.execute(_NEWEST, {"c": close_id})).mappings()
        }
        set_id = cast(
            UUID,
            await tx.session.scalar(
                _INSERT_SET,
                {"t": tenant.tenant_id, "c": close_id, "b": basis, "p": policy, "v": version,
                 "e": engine.FLUX_ENGINE_VERSION, "h": digest},
            ),
        )  # fmt: skip
        for ln in lines:
            status = done.get(ln.key, ln.status) if ln.test == "over_both" else ln.status
            await tx.session.execute(
                _INSERT_LINE,
                {"t": tenant.tenant_id, "s": set_id, "pos": ln.position, "k": ln.key,
                 "cap": ln.caption, "prior": ln.prior, "cur": ln.current, "chg": ln.change,
                 "pct": ln.pct, "test": ln.test, "status": status},
            )  # fmt: skip
        tx.record(
            "analytic_set.computed", target=Target(TARGET, set_id), after=Ref(version=version)
        )
        tx.emit(
            AnalyticSetComputed(
                set_id=set_id, close_id=close_id, engagement_id=close.engagement_id
            )
        )
    return set_id


async def _authorise_close(ctx: AuthContext, close_id: UUID, action: str) -> UUID:
    from abacus.modules.engagements.api import get_ref

    async with tenant_session(ctx.tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None:
        raise NotFound("close")
    await authorise(ctx, action, (await get_ref(ctx, close.engagement_id)).resource())
    return close.engagement_id


def _pct(v: object) -> Decimal | None:
    return None if v is None else cast(Decimal, v).quantize(_TENTH, rounding=ROUND_HALF_UP)


async def _view(ctx: AuthContext, close_id: UUID, set_id: UUID, basis: Basis) -> FluxSetOut:
    from abacus.modules.closes.service import people

    t, _ = await thresholds(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        rows = [dict(r) for r in (await session.execute(_LINES, {"s": set_id})).mappings()]
        newest = {
            str(r["line_key"]): dict(r)
            for r in (await session.execute(_NEWEST, {"c": close_id})).mappings()
        }
    named = await people(
        {cast(UUID, e["accepted_by"]) for e in newest.values() if e["accepted_by"]}
    )
    out: list[FluxLineOut] = []
    for r in rows:
        key = str(r["line_key"])
        e = newest.get(key) if r["test"] == "over_both" else None
        status = str(r["status"])
        explanation: str | None = None
        accepted_by = None
        if e is not None:
            explanation = (
                await open_sealed(ctx.tenant_id, cast(bytes, e["text_sealed"]), FINGERPRINT)
            ).decode()
            accepted_by = named.get(cast(UUID, e["accepted_by"])) if e["accepted_by"] else None
            status = "accepted" if e["accepted_by"] else "explained"
        out.append(
            FluxLineOut(
                line_id=line_id(set_id, key), line_key=key, caption=str(r["caption"]),
                prior=cast("Decimal | None", r["prior"]), current=cast(Decimal, r["current"]),
                change=cast("Decimal | None", r["change"]), change_pct=_pct(r["change_pct"]),
                test=r["test"], status=status,  # type: ignore[arg-type] -- the table's CHECK
                explanation=explanation, accepted_by=accepted_by,
                row_version=1 if e is None else int(cast(int, e["version"])) + 1,
            )
        )  # fmt: skip
    over = [x for x in out if x.test == "over_both"]
    return FluxSetOut(
        set_id=set_id,
        basis=basis,
        threshold_label=threshold_label(t),
        tested=len(out),
        explained=sum(1 for x in over if x.status in ("explained", "accepted")),
        unexplained=sum(1 for x in over if x.status in ("unexplained", "explained_draft")),
        budget_available=False,
        lines=out,
        engine_version=engine.FLUX_ENGINE_VERSION,
    )


async def flux_set(ctx: AuthContext, close_id: UUID, basis: Basis) -> FluxSetOut:
    """CLS-10: the newest set (recomputed when its inputs changed), lines with explanations."""
    await _authorise_close(ctx, close_id, "flux.read")
    set_id = await compute(ctx, close_id, basis)
    return await _view(ctx, close_id, set_id, basis)


@dataclass(frozen=True)
class _Found:
    set_id: UUID
    key: str
    test: str
    close_id: UUID
    basis: Basis
    engagement_id: UUID
    status: str


async def _line(ctx: AuthContext, the_line: UUID, action: str) -> _Found:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")
    async with tenant_session(ctx.tenant) as session:
        r = (await session.execute(_LINE_BY_ID, {"id": the_line})).mappings().first()
    if r is None:
        raise NotFound("analytic_line")
    engagement = await _authorise_close(ctx, cast(UUID, r["close_id"]), action)
    found = _Found(
        cast(UUID, r["set_id"]), str(r["line_key"]), str(r["test"]), cast(UUID, r["close_id"]),
        cast(Basis, r["basis"]), engagement, str(r["status"]),
    )  # fmt: skip
    if found.test != "over_both":
        raise NothingToExplain(facts={"line": found.key})
    return found


def _version(if_match: str) -> int:
    raw = if_match.strip().removeprefix("W/").strip('"')
    if not raw.isdigit():
        raise FluxStale(facts={"if_match": raw[:20]})
    return int(raw)


async def _line_out(ctx: AuthContext, found: _Found) -> FluxLineOut:
    view = await _view(ctx, found.close_id, found.set_id, found.basis)
    return next(x for x in view.lines if x.line_key == found.key)


async def explain(ctx: AuthContext, the_line: UUID, *, body: str, if_match: str) -> FluxLineOut:
    """A person's explanation: a new sealed version; `If-Match` is the line's row version."""
    found = await _line(ctx, the_line, "flux.edit")
    if found.status == "accepted":
        raise LineAccepted(facts={"line": found.key})
    wanted = _version(if_match)
    sealed = await seal(ctx.tenant_id, body.strip().encode(), FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        latest = await tx.session.scalar(
            text(
                "SELECT max(version) FROM analytic_explanations "
                "WHERE close_id = :c AND line_key = :k"
            ),
            {"c": found.close_id, "k": found.key},
        )
        current = int(cast(int, latest or 0)) + 1
        if wanted != current:
            raise FluxStale(facts={"row_version": current})
        made = await tx.session.scalar(
            _INSERT_EXPLANATION,
            {"t": ctx.tenant_id, "c": found.close_id, "k": found.key, "v": current,
             "sealed": sealed},
        )  # fmt: skip
        await tx.session.execute(
            _ADVANCE, {"s": found.set_id, "k": found.key, "status": "explained"}
        )
        tx.record(
            "analytic_explanation.edited",
            target=Target(TARGET, found.set_id),
            after=Ref(explanation=made, line=found.key),
        )
        tx.emit(
            AnalyticLineExplained(
                set_id=found.set_id,
                close_id=found.close_id,
                engagement_id=found.engagement_id,
                line_key=found.key,
            )
        )
    return await _line_out(ctx, found)


async def accept(ctx: AuthContext, the_line: UUID, *, if_match: str) -> FluxLineOut:
    """A Manager or Partner accepts the line's newest explanation (`flux.accept`; a Senior 403)."""
    found = await _line(ctx, the_line, "flux.accept")
    wanted = _version(if_match)
    async with uow(ctx.tenant) as tx:
        newest = (
            await tx.session.execute(
                text(
                    "SELECT id, version FROM analytic_explanations WHERE close_id = :c "
                    "AND line_key = :k ORDER BY version DESC LIMIT 1 FOR UPDATE"
                ),
                {"c": found.close_id, "k": found.key},
            )
        ).first()
        if newest is None:
            raise NothingToAccept(facts={"line": found.key})
        if wanted != int(newest.version) + 1:
            raise FluxStale(facts={"row_version": int(newest.version) + 1})
        if await tx.session.scalar(_ACCEPT, {"id": newest.id, "by": ctx.user_id}) is None:
            raise NothingToAccept(facts={"line": found.key})
        await tx.session.execute(
            _ADVANCE, {"s": found.set_id, "k": found.key, "status": "accepted"}
        )
        tx.record(
            "analytic_line.accepted",
            target=Target(TARGET, found.set_id),
            after=Ref(explanation=newest.id, line=found.key),
        )
        tx.emit(
            AnalyticLineAccepted(
                close_id=found.close_id,
                engagement_id=found.engagement_id,
                set_id=found.set_id,
                line_key=found.key,
            )
        )
    return await _line_out(ctx, found)


def _dash(v: Decimal | None) -> Cell:
    return "—" if v is None else v


async def workbook_of(ctx: AuthContext, close_id: UUID, basis: Basis) -> bytes:
    view = await flux_set(ctx, close_id, basis)
    rows: list[list[Cell]] = [
        ["Account", "Prior", "Current", "Change", "Change %", "Test", "Status", "Explanation"]
    ]
    for x in view.lines:
        rows.append(
            [x.caption, _dash(x.prior), x.current, _dash(x.change), _dash(x.change_pct), x.test,
             x.status, x.explanation or ""]
        )  # fmt: skip
    about: list[list[Cell]] = [
        ["Basis", "Month over month" if basis == "mom" else "Year over year"],
        ["Threshold", view.threshold_label],
        ["Engine", view.engine_version],
        ["Set", str(view.set_id)],
    ]
    return workbook([Sheet("Flux", rows), Sheet("About", about)])


__all__ = [
    "AnalyticLineAccepted",
    "accept",
    "adjusted",
    "compute",
    "explain",
    "flux_set",
    "line_id",
    "line_key",
    "lines_of",
    "prior_period",
    "workbook_of",
]
