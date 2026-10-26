"""The trial balance of record (SPEC-309; TASK-320; A-02 §3.1-3.5, 3.7).

An engagement adopts an immutable ledger snapshot as its trial balance for a label and period,
paired with a prior-year snapshot for the beginning-of-year column. Re-adopting a newer snapshot
makes a new version; nothing earlier is touched (ADR-004). Code computes every total, the
balance check, leadsheets and Δ% (ADR-050); the browser never sums a column.

Ledger stays dependency-free: callers authorise, pass the actor and the work item, and supply
nothing but identifiers. Only the unadjusted layer exists until an adjustment source registers
(A-06); asking for another layer is refused, never answered with unadjusted figures.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.ledger.events import TrialBalanceVersionCreated
from abacus.modules.ledger.models import (
    LedgerSnapshot,
    TrialBalance,
    TrialBalanceLineRow,
    TrialBalanceVersion,
)
from abacus.modules.ledger.repository import get_snapshot, lines_of_snapshots
from abacus.modules.ledger.tb_repository import (
    annotation_setters,
    find_trial_balance,
    get_trial_balance,
    insert_annotations,
    insert_trial_balance,
    insert_version,
    lock_trial_balance,
    newest_annotations,
    set_current_version,
    snapshots_of_entity,
    trial_balances_of,
    versions_of,
)

Label = Literal["standard", "interim", "prior", "budget", "preliminary"]
Unit = Literal["cents", "whole_dollars"]
Layer = Literal["unadjusted", "aje", "rje", "final"]
LABELS: Final = ("standard", "interim", "prior", "budget", "preliminary")
UNASSIGNED: Final = "Unassigned"
_ZERO: Final = Decimal("0.00")
_PCT: Final = Decimal("0.1")


class SnapshotEntityMismatch(DomainInvalid):
    code = "snapshot_entity_mismatch"


class TrialBalanceInvalid(DomainInvalid):
    code = "trial_balance_invalid"


class TrialBalanceExists(DomainConflict):
    code = "trial_balance_exists"


class VersionStale(DomainConflict):
    """Someone adopted another version since the caller looked."""

    code = "tb_version_stale"


class SameSnapshot(DomainConflict):
    code = "tb_same_snapshot"


class LayerUnavailable(DomainConflict):
    """AJE, RJE or Final before an adjustment source registers (A-06, C8)."""

    code = "layer_unavailable"


class LayerUnbalanced(DomainConflict):
    """A layer whose debits and credits differ (`facts.layer`, `facts.difference`)."""

    code = "layer_unbalanced"


@dataclass(frozen=True)
class EntryLine:
    account_code: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class AdjustmentEntry:
    """A recorded entry an adjustment source offers the layers (SPEC-311): `kind` aje or rje;
    only entries the source counts as recorded (approved, or accepted by the client) belong."""

    ref: str
    kind: Literal["aje", "rje"]
    lines: tuple[EntryLine, ...]


@dataclass(frozen=True)
class EntrySet:
    recorded: tuple[AdjustmentEntry, ...]
    pending: int  # proposed and not yet approved; shown as a count, never in a layer


AdjustmentSource = Callable[[TenantContext, UUID], Awaitable[EntrySet]]

# The adjustment slot (fieldwork fills it, SPEC-311): fails closed, so AJE, RJE and Final are
# refused while nothing is registered.
_ADJUSTMENT_SOURCES: list[AdjustmentSource] = []


def register_adjustment_source(source: AdjustmentSource) -> None:
    if source not in _ADJUSTMENT_SOURCES:
        _ADJUSTMENT_SOURCES.append(source)


def layer_available(layer: str) -> bool:
    return layer == "unadjusted" or bool(_ADJUSTMENT_SOURCES)


async def _entries(tenant: TenantContext, engagement_id: UUID) -> EntrySet | None:
    if not _ADJUSTMENT_SOURCES:
        return None
    recorded: list[AdjustmentEntry] = []
    pending = 0
    for source in _ADJUSTMENT_SOURCES:
        found = await source(tenant, engagement_id)
        recorded.extend(found.recorded)
        pending += found.pending
    return EntrySet(tuple(recorded), pending)


@dataclass(frozen=True)
class AreaRule:
    """A methodology account rule (A-02 §4.1; `engagements.api.area_for`): accounts whose code
    falls in `account_from`..`account_to` (compared as text) belong to `area`. The caller turns
    its methodology's rules into these; ledger stays dependency-free."""

    area: str
    account_from: str
    account_to: str


def area_of_rules(code: str, rules: Sequence[AreaRule]) -> str | None:
    """The first rule in rule order whose range holds the code, as `area_for` reads it."""
    for rule in rules:
        if rule.account_from <= code <= rule.account_to:
            return rule.area
    return None


@dataclass(frozen=True)
class SnapshotSummary:
    id: UUID
    period_start: date
    period_end: date
    source: str
    pulled_at: datetime
    line_count: int
    total_debit: Decimal
    total_credit: Decimal


@dataclass(frozen=True)
class TbLine:
    account_code: str
    account_name: str
    boy: Decimal | None  # the prior snapshot's net (debit - credit); None without a prior
    debit: Decimal
    credit: Decimal
    eoy: Decimal  # net, debit - credit
    change: Decimal | None
    area: str | None
    wp_ref: str | None
    aje: Decimal | None = None  # None without an adjustment source (SPEC-311)
    rje: Decimal | None = None
    final: Decimal | None = None
    refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Totals:
    debit: Decimal
    credit: Decimal
    difference: Decimal
    balanced: bool


@dataclass(frozen=True)
class VersionInfo:
    version_no: int
    snapshot_id: UUID
    prior_snapshot_id: UUID | None
    adopted_by: UUID
    reason: str | None
    adopted_at: datetime
    source: str
    pulled_at: datetime


@dataclass(frozen=True)
class TrialBalanceSummary:
    id: UUID
    label: str
    period_start: date
    period_end: date
    display_unit: str
    current_version_no: int


@dataclass(frozen=True)
class TrialBalanceView:
    summary: TrialBalanceSummary
    version: VersionInfo
    versions: list[VersionInfo]
    lines: list[TbLine]
    eoy: Totals
    boy: Totals | None
    final: Totals | None = None  # None without an adjustment source
    pending_entries: int = 0
    # Each available layer's debits, credits and balance (AC-17): Unadjusted always; AJE, RJE
    # and Final once an adjustment source registers.
    layer_balances: dict[str, Totals] = field(default_factory=dict[str, Totals])


@dataclass(frozen=True)
class LeadRow:
    account_code: str
    account_name: str
    py: Decimal | None
    cy: Decimal
    change: Decimal | None
    change_pct: Decimal | None


@dataclass(frozen=True)
class Leadsheet:
    area: str
    rows: list[LeadRow]
    py: Decimal | None
    cy: Decimal
    change: Decimal | None
    change_pct: Decimal | None


@dataclass(frozen=True)
class Candidate:
    snapshot: SnapshotSummary
    lines_changed: int | None  # against the current version; None when nothing is adopted
    net_change: Decimal | None


@dataclass(frozen=True)
class AnnotationEdit:
    account_code: str
    area: str | None
    wp_ref: str | None


# --- compute (pure) ---------------------------------------------------------------------------


def _net(rows: Sequence[TrialBalanceLineRow]) -> dict[str, tuple[str, Decimal, Decimal]]:
    out: dict[str, tuple[str, Decimal, Decimal]] = {}
    for r in rows:
        name, debit, credit = out.get(r.account_code, (r.account_name, _ZERO, _ZERO))
        out[r.account_code] = (name, debit + r.debit, credit + r.credit)
    return out


def totals(debit: Decimal, credit: Decimal) -> Totals:
    return Totals(debit, credit, debit - credit, debit == credit)


def pct(change: Decimal, base: Decimal | None) -> Decimal | None:
    """Δ% to 0.1, half-even, against the magnitude of the base; None when the base is 0."""
    if base is None or base == 0:
        return None
    return (change * 100 / abs(base)).quantize(_PCT, rounding=ROUND_HALF_EVEN)


def build_lines(
    current: Sequence[TrialBalanceLineRow],
    prior: Sequence[TrialBalanceLineRow] | None,
    annotations: dict[str, tuple[str | None, str | None]],
    area_rules: Sequence[AreaRule] = (),
) -> list[TbLine]:
    """Every account of either year, by code: BOY is the prior snapshot's net, EOY the current
    one's. An annotated area wins over the methodology rules' area (A-02 §4.1)."""
    cy = _net(current)
    py = _net(prior) if prior is not None else {}
    lines: list[TbLine] = []
    for code in sorted(set(cy) | set(py)):
        name, debit, credit = cy.get(code, (py[code][0] if code in py else code, _ZERO, _ZERO))
        boy = (py[code][1] - py[code][2]) if code in py else (_ZERO if prior is not None else None)
        eoy = debit - credit
        area, wp_ref = annotations.get(code, (None, None))
        area = area if area is not None else area_of_rules(code, area_rules)
        lines.append(
            TbLine(
                code,
                name,
                boy,
                debit,
                credit,
                eoy,
                None if boy is None else eoy - boy,
                area,
                wp_ref,
            )
        )
    return lines


def apply_entries(
    lines: Sequence[TbLine],
    entries: Sequence[AdjustmentEntry],
    area_rules: Sequence[AreaRule] = (),
) -> list[TbLine]:
    """AJE, RJE and Final per account, by code; an entry's account the trial balance doesn't
    hold appears as a new line with no unadjusted balance: 0.00 at the beginning of the year when
    the trial balance has a prior year (as `build_lines` gives an account new this year), and
    its area from the methodology rules."""
    names = {line.account_code: line for line in lines}
    has_prior = any(line.boy is not None for line in lines)
    aje: dict[str, Decimal] = {}
    rje: dict[str, Decimal] = {}
    refs: dict[str, list[str]] = {}
    for e in entries:
        bucket = aje if e.kind == "aje" else rje
        for x in e.lines:
            bucket[x.account_code] = bucket.get(x.account_code, _ZERO) + x.debit - x.credit
            if e.ref not in refs.setdefault(x.account_code, []):
                refs[x.account_code].append(e.ref)
    out: list[TbLine] = []
    for code in sorted(set(names) | set(aje) | set(rje)):
        base = names.get(code)
        if base is None:
            boy = _ZERO if has_prior else None
            change = None if boy is None else _ZERO
            area = area_of_rules(code, area_rules)
            base = TbLine(code, code, boy, _ZERO, _ZERO, _ZERO, change, area, None)
        a, r = aje.get(code, _ZERO), rje.get(code, _ZERO)
        out.append(
            TbLine(
                base.account_code,
                base.account_name,
                base.boy,
                base.debit,
                base.credit,
                base.eoy,
                base.change,
                base.area,
                base.wp_ref,
                a,
                r,
                base.eoy + a + r,
                tuple(refs.get(code, ())),
            )
        )
    return out


def cy_of(line: TbLine, layer: str) -> Decimal:
    if layer == "final" and line.final is not None:
        return line.final
    return line.eoy


def final_totals(lines: Sequence[TbLine]) -> Totals:
    """Debits and credits of the Final column: each account's final net on its own side."""
    debit = sum((line.final for line in lines if line.final is not None and line.final > 0), _ZERO)
    credit = -sum(
        (line.final for line in lines if line.final is not None and line.final < 0), _ZERO
    )
    return totals(debit, credit)


def layer_totals(lines: Sequence[TbLine], layer: str) -> Totals:
    """A layer's debits and credits (AC-17). Unadjusted is the snapshot's debit and credit
    columns; AJE and RJE put each account's net adjustment on its own side; Final is the final
    column's (`final_totals`). Callers check `layer_available` first."""
    if layer == "unadjusted":
        return totals(
            sum((line.debit for line in lines), _ZERO), sum((line.credit for line in lines), _ZERO)
        )
    if layer == "final":
        return final_totals(lines)
    if layer not in ("aje", "rje"):
        raise LayerUnavailable(layer)
    values = [(line.aje if layer == "aje" else line.rje) or _ZERO for line in lines]
    return totals(
        sum((v for v in values if v > 0), _ZERO), -sum((v for v in values if v < 0), _ZERO)
    )


def require_balanced(lines: Sequence[TbLine], layer: str) -> Totals:
    """The layer's totals, or `layer_unbalanced` with the difference (AC-17)."""
    found = layer_totals(lines, layer)
    if not found.balanced:
        raise LayerUnbalanced(
            layer, facts={"layer": layer, "difference": str(abs(found.difference))}
        )
    return found


def leadsheets(lines: Sequence[TbLine], layer: str = "unadjusted") -> list[Leadsheet]:
    """One leadsheet per audit area, alphabetical, with Unassigned last; never drops a line.
    CY is the unadjusted or the final balance."""
    has_prior = any(line.boy is not None for line in lines)
    groups: dict[str, list[TbLine]] = {}
    for line in lines:
        groups.setdefault(line.area or UNASSIGNED, []).append(line)
    order = sorted((a for a in groups if a != UNASSIGNED), key=str.lower)
    if UNASSIGNED in groups:
        order.append(UNASSIGNED)
    out: list[Leadsheet] = []
    for area in order:
        rows = [
            LeadRow(
                line.account_code,
                line.account_name,
                line.boy,
                cy_of(line, layer),
                None if line.boy is None else cy_of(line, layer) - line.boy,
                None if line.boy is None else pct(cy_of(line, layer) - line.boy, line.boy),
            )
            for line in groups[area]
        ]
        cy = sum((r.cy for r in rows), _ZERO)
        py = sum((r.py or _ZERO for r in rows), _ZERO) if has_prior else None
        change = None if py is None else cy - py
        out.append(
            Leadsheet(area, rows, py, cy, change, None if change is None else pct(change, py))
        )
    return out


def compare_lines(
    current: Sequence[TrialBalanceLineRow], candidate: Sequence[TrialBalanceLineRow]
) -> tuple[int, Decimal]:
    """How many accounts differ (added, removed or a changed net) and the net change."""
    a, b = _net(current), _net(candidate)
    changed = 0
    net = _ZERO
    for code in set(a) | set(b):
        old = a[code][1] - a[code][2] if code in a else None
        new = b[code][1] - b[code][2] if code in b else None
        if old != new:
            changed += 1
            net += abs((new or _ZERO) - (old or _ZERO))
    return changed, net


def fingerprint(snapshot: LedgerSnapshot, prior: LedgerSnapshot | None) -> str:
    text = f"{snapshot.raw_fingerprint}:{prior.raw_fingerprint if prior else ''}"
    return hashlib.sha256(text.encode()).hexdigest()


def _summary(s: LedgerSnapshot) -> SnapshotSummary:
    return SnapshotSummary(
        s.id,
        s.period_start,
        s.period_end,
        s.source,
        s.pulled_at,
        s.line_count,
        s.total_debit,
        s.total_credit,
    )


def _tb_summary(tb: TrialBalance) -> TrialBalanceSummary:
    return TrialBalanceSummary(
        tb.id, tb.label, tb.period_start, tb.period_end, tb.display_unit, tb.current_version_no
    )


# --- service (callers authorise first) --------------------------------------------------------


async def entity_snapshots(tenant: TenantContext, client_entity_id: UUID) -> list[SnapshotSummary]:
    async with tenant_session(tenant) as session:
        return [_summary(s) for s in await snapshots_of_entity(session, client_entity_id)]


async def engagement_trial_balances(
    tenant: TenantContext, engagement_id: UUID
) -> list[TrialBalanceSummary]:
    async with tenant_session(tenant) as session:
        return [_tb_summary(tb) for tb in await trial_balances_of(session, engagement_id)]


async def _snapshots(
    tx: UnitOfWork, client_entity_id: UUID, snapshot_id: UUID, prior_snapshot_id: UUID | None
) -> tuple[LedgerSnapshot, LedgerSnapshot | None]:
    snapshot = await get_snapshot(tx.session, snapshot_id)
    if snapshot is None:
        raise NotFound("ledger_snapshot")
    if snapshot.client_entity_id != client_entity_id:
        raise SnapshotEntityMismatch(str(snapshot_id))
    prior = None
    if prior_snapshot_id is not None:
        if prior_snapshot_id == snapshot_id:
            raise TrialBalanceInvalid("prior")
        prior = await get_snapshot(tx.session, prior_snapshot_id)
        if prior is None:
            raise NotFound("ledger_snapshot")
        if prior.client_entity_id != client_entity_id:
            raise SnapshotEntityMismatch(str(prior_snapshot_id))
        if prior.period_end >= snapshot.period_end:
            raise TrialBalanceInvalid("prior_period")
    return snapshot, prior


async def adopt_trial_balance(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    work_item_id: UUID,
    client_entity_id: UUID,
    snapshot_id: UUID,
    prior_snapshot_id: UUID | None,
    label: str,
    display_unit: str,
    user_id: UUID,
    actor_kind: str,
) -> UUID:
    """AC-1: version 1 of a new trial balance of record, inside the caller's unit of work."""
    if label not in LABELS or display_unit not in ("cents", "whole_dollars"):
        raise TrialBalanceInvalid("label")
    snapshot, prior = await _snapshots(tx, client_entity_id, snapshot_id, prior_snapshot_id)
    if await find_trial_balance(
        tx.session, work_item_id, client_entity_id, label, snapshot.period_end
    ):
        raise TrialBalanceExists(label)
    tb_id = await insert_trial_balance(
        tx.session,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        work_item_id=work_item_id,
        client_entity_id=client_entity_id,
        label=label,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        display_unit=display_unit,
        created_by=user_id,
    )
    await insert_version(
        tx.session,
        tenant_id=tenant_id,
        trial_balance_id=tb_id,
        client_entity_id=client_entity_id,
        version_no=1,
        snapshot_id=snapshot.id,
        prior_snapshot_id=prior.id if prior else None,
        adopted_by=user_id,
        actor_kind=actor_kind,
        reason=None,
        content_fingerprint=fingerprint(snapshot, prior),
    )
    tx.record(
        "trial_balance.created", target=Target("trial_balance", tb_id), after=Ref(version_no=1)
    )
    tx.record(
        "trial_balance.version_adopted",
        target=Target("trial_balance", tb_id),
        after=Ref(version_no=1, snapshot=snapshot.id),
    )
    tx.emit(
        TrialBalanceVersionCreated(
            trial_balance_id=tb_id,
            engagement_id=engagement_id,
            version_no=1,
            snapshot_id=snapshot.id,
            prior_snapshot_id=prior.id if prior else None,
        )
    )
    return tb_id


async def adopt_version(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    tb_id: UUID,
    snapshot_id: UUID,
    prior_snapshot_id: UUID | None,
    reason: str,
    seen_version: int,
    user_id: UUID,
    actor_kind: str,
) -> int:
    """AC-7: a newer snapshot becomes the next version; earlier versions stay as they were."""
    reason = reason.strip()
    if not 1 <= len(reason) <= 500:
        raise TrialBalanceInvalid("reason")
    tb = await lock_trial_balance(tx.session, tb_id)
    if tb is None or tb.engagement_id != engagement_id:
        raise NotFound("trial_balance")
    if tb.current_version_no != seen_version:
        raise VersionStale(str(tb_id))
    snapshot, prior = await _snapshots(tx, tb.client_entity_id, snapshot_id, prior_snapshot_id)
    current = (await versions_of(tx.session, tb.id))[0]
    if current.snapshot_id == snapshot.id and current.prior_snapshot_id == (
        prior.id if prior else None
    ):
        raise SameSnapshot(str(snapshot_id))
    if (snapshot.period_start, snapshot.period_end) != (tb.period_start, tb.period_end):
        raise TrialBalanceInvalid("period")
    version_no = tb.current_version_no + 1
    await insert_version(
        tx.session,
        tenant_id=tenant_id,
        trial_balance_id=tb.id,
        client_entity_id=tb.client_entity_id,
        version_no=version_no,
        snapshot_id=snapshot.id,
        prior_snapshot_id=prior.id if prior else None,
        adopted_by=user_id,
        actor_kind=actor_kind,
        reason=reason,
        content_fingerprint=fingerprint(snapshot, prior),
    )
    await set_current_version(tx.session, tb.id, version_no)
    tx.record(
        "trial_balance.version_adopted",
        target=Target("trial_balance", tb.id),
        before=Ref(version_no=tb.current_version_no),
        after=Ref(version_no=version_no, snapshot=snapshot.id),
    )
    tx.emit(
        TrialBalanceVersionCreated(
            trial_balance_id=tb.id,
            engagement_id=engagement_id,
            version_no=version_no,
            snapshot_id=snapshot.id,
            prior_snapshot_id=prior.id if prior else None,
        )
    )
    return version_no


async def annotate(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    tb_id: UUID,
    edits: Sequence[AnnotationEdit],
    reason: str | None,
    user_id: UUID,
) -> int:
    """An account's audit area and working-paper reference (amounts are never editable)."""
    if not edits or len(edits) > 500:
        raise TrialBalanceInvalid("edits")
    tb = await get_trial_balance(tx.session, tb_id)
    if tb is None or tb.engagement_id != engagement_id:
        raise NotFound("trial_balance")
    current = {a.account_code: a for a in await newest_annotations(tx.session, tb.id)}
    rows: list[dict[str, object]] = []
    for e in edits:
        old = current.get(e.account_code)
        if old is not None and (old.area, old.wp_ref) == (e.area, e.wp_ref):
            continue
        if old is None and e.area is None and e.wp_ref is None:
            continue
        rows.append(
            {
                "tenant_id": tenant_id,
                "trial_balance_id": tb.id,
                "account_code": e.account_code,
                "area": e.area,
                "wp_ref": e.wp_ref,
                "reason": reason,
                "set_by": user_id,
            }
        )
    await insert_annotations(tx.session, rows)
    if rows:
        tx.record(
            "trial_balance.annotated",
            target=Target("trial_balance", tb.id),
            after=Ref(accounts=len(rows)),
        )
    return len(rows)


async def trial_balance_view(
    tenant: TenantContext,
    engagement_id: UUID,
    tb_id: UUID,
    version_no: int | None = None,
    layer: str = "unadjusted",
    area_rules: Sequence[AreaRule] = (),
) -> TrialBalanceView:
    """AC-2, AC-4: a version's lines (BOY, debit, credit, EOY, change), totals and balance,
    and each available layer's balance (AC-17). Areas come from the annotations, then from the
    caller's methodology rules."""
    if not layer_available(layer):
        raise LayerUnavailable(layer)
    async with tenant_session(tenant) as session:
        tb = await get_trial_balance(session, tb_id)
        if tb is None or tb.engagement_id != engagement_id:
            raise NotFound("trial_balance")
        versions = await versions_of(session, tb.id)
        chosen = next(
            (v for v in versions if v.version_no == (version_no or tb.current_version_no)), None
        )
        if chosen is None:
            raise NotFound("trial_balance_version")
        snap_ids = {v.snapshot_id for v in versions} | {
            v.prior_snapshot_id for v in versions if v.prior_snapshot_id
        }
        snaps = {sid: await get_snapshot(session, sid) for sid in snap_ids}
        wanted = [chosen.snapshot_id] + (
            [chosen.prior_snapshot_id] if chosen.prior_snapshot_id else []
        )
        rows = await lines_of_snapshots(session, wanted)
        notes = await newest_annotations(session, tb.id)
    current = [r for r in rows if r.snapshot_id == chosen.snapshot_id]
    prior = (
        [r for r in rows if r.snapshot_id == chosen.prior_snapshot_id]
        if chosen.prior_snapshot_id
        else None
    )
    lines = build_lines(
        current, prior, {a.account_code: (a.area, a.wp_ref) for a in notes}, area_rules
    )
    entries = await _entries(tenant, engagement_id)
    if entries is not None:
        lines = apply_entries(lines, entries.recorded, area_rules)

    def info(v: TrialBalanceVersion) -> VersionInfo:
        s = snaps[v.snapshot_id]
        if s is None:
            raise NotFound("ledger_snapshot")
        return VersionInfo(
            v.version_no,
            v.snapshot_id,
            v.prior_snapshot_id,
            v.adopted_by,
            v.reason,
            v.created_at,
            s.source,
            s.pulled_at,
        )

    available = ("unadjusted", "aje", "rje", "final") if entries is not None else ("unadjusted",)
    balances = {name: layer_totals(lines, name) for name in available}
    boy = None
    if prior is not None:
        boy = totals(sum((r.debit for r in prior), _ZERO), sum((r.credit for r in prior), _ZERO))
    return TrialBalanceView(
        _tb_summary(tb),
        info(chosen),
        [info(v) for v in versions],
        lines,
        balances["unadjusted"],
        boy,
        balances["final"] if entries is not None else None,
        entries.pending if entries is not None else 0,
        balances,
    )


async def candidates(
    tenant: TenantContext, engagement_id: UUID, client_entity_id: UUID, tb_id: UUID | None
) -> list[Candidate]:
    """AC-7: the entity's snapshots, each with a code-computed difference from the current
    version (lines changed, net change); newest first."""
    async with tenant_session(tenant) as session:
        snaps = await snapshots_of_entity(session, client_entity_id)
        current_rows: Sequence[TrialBalanceLineRow] | None = None
        if tb_id is not None:
            tb = await get_trial_balance(session, tb_id)
            if tb is None or tb.engagement_id != engagement_id:
                raise NotFound("trial_balance")
            current = next(
                v
                for v in await versions_of(session, tb.id)
                if v.version_no == tb.current_version_no
            )
            current_rows = await lines_of_snapshots(session, [current.snapshot_id])
            same_period = [
                s
                for s in snaps
                if (s.period_start, s.period_end) == (tb.period_start, tb.period_end)
            ]
            others = await lines_of_snapshots(session, [s.id for s in same_period])
        else:
            others: Sequence[TrialBalanceLineRow] = []
    out: list[Candidate] = []
    for s in snaps:
        if current_rows is None:
            out.append(Candidate(_summary(s), None, None))
            continue
        mine = [r for r in others if r.snapshot_id == s.id]
        if not mine:
            out.append(Candidate(_summary(s), None, None))
            continue
        changed, net = compare_lines(current_rows, mine)
        out.append(Candidate(_summary(s), changed, net))
    return out


@dataclass(frozen=True)
class TbDigest:
    """What a trial balance sign-off approves (SPEC-313): the current version's fingerprint and
    every account's area and WP ref. Tie-out definitions are not in it yet."""

    summary: TrialBalanceSummary
    digest: str


@dataclass(frozen=True)
class TbAuthors:
    """Who prepared a trial balance, from its own records (P-04-T15): everyone who adopted a
    version of it and everyone who annotated it."""

    trial_balance_id: UUID
    engagement_id: UUID
    version_no: int
    authors: frozenset[UUID]


async def trial_balance_authors(tenant: TenantContext, tb_id: UUID) -> TbAuthors | None:
    """For callers authorised on the trial balance's engagement; None when unknown."""
    async with tenant_session(tenant) as session:
        tb = await get_trial_balance(session, tb_id)
        if tb is None:
            return None
        adopters = {v.adopted_by for v in await versions_of(session, tb.id)}
        annotators = await annotation_setters(session, tb.id)
    return TbAuthors(
        tb.id, tb.engagement_id, tb.current_version_no, frozenset(adopters | annotators)
    )


async def review_digests(tenant: TenantContext, engagement_id: UUID) -> list[TbDigest]:
    async with tenant_session(tenant) as session:
        out: list[TbDigest] = []
        for tb in await trial_balances_of(session, engagement_id):
            current = next(
                v
                for v in await versions_of(session, tb.id)
                if v.version_no == tb.current_version_no
            )
            notes = sorted(
                (a.account_code, a.area or "", a.wp_ref or "")
                for a in await newest_annotations(session, tb.id)
                if a.area or a.wp_ref
            )
            text = current.content_fingerprint + "|" + "|".join(":".join(n) for n in notes)
            out.append(TbDigest(_tb_summary(tb), hashlib.sha256(text.encode()).hexdigest()))
    return out
