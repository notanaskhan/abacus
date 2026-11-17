"""Group consolidations, the ledger's half (A-09-T13; SPEC-658 F1, AC-1.1 to AC-1.3; ADR-341;
DEC-5070). Pure ledger: no other module, the caller (assurance) authorises first.

- A consolidation is a draft until a person finalizes it; `discard` is an audited status, never a
  delete. Edits and the structure carry the row version (ETag); a stale one is `VersionStale`.
- The structure: one root at level 1, every other entity one level under its parent, at most
  three tiers, 100% owned (X-06); the database's guard refuses an entity outside the engagement
  and any change once finalized.
- Trial balances: each entity needs a current slot (`interim` through the interim date, or
  `standard` through year end) and, with a prior period, a `prior` slot. A slot is stored only
  when a TB is attached or a person marks it not needed; "missing" is what is required and not
  stored. A replacement points the old row at its successor (the deferred FK, 0899).
- Finalize refuses any missing slot (`trial_balance_missing`, naming each) and returns the
  attached current snapshots, one per entity, for the caller's mapping runs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork

Label = Literal["standard", "interim", "prior", "budget", "preliminary"]
PeriodKind = Literal["current", "prior"]
Source = Literal["upload", "evidence", "connection"]
MAX_TIERS: Final = 3
TARGET: Final = "consolidation"


class VersionStale(DomainConflict):
    """The consolidation changed since it was read (If-Match)."""

    code = "consolidation_changed"


class ConsolidationNotDraft(DomainConflict):
    """Only a draft consolidation changes."""

    code = "consolidation_not_draft"


class StructureInvalid(DomainInvalid):
    """A fourth tier, a second root, a parent missing or not one level up (X-06)."""

    code = "structure_invalid"


class TrialBalanceMissing(DomainConflict):
    code = "trial_balance_missing"


class SnapshotMismatch(DomainInvalid):
    """The snapshot is not the entity's, or not for the slot's period."""

    code = "snapshot_mismatch"


@dataclass(frozen=True)
class EntityRow:
    id: UUID
    client_entity_id: UUID
    parent_id: UUID | None
    level: int
    city: str | None
    component_auditor_id: UUID | None
    position: int


@dataclass(frozen=True)
class SlotKey:
    consolidation_entity_id: UUID
    label: Label
    period_kind: PeriodKind
    period_start: date
    period_end: date


@dataclass(frozen=True)
class SlotRow:
    id: UUID
    key: SlotKey
    state: Literal["attached", "not_needed", "needs_reauth", "missing"]
    ledger_snapshot_id: UUID | None
    source: Source | None
    not_needed_reason: str | None
    total_debits: Decimal | None
    total_credits: Decimal | None


@dataclass(frozen=True)
class ConsolidationFacts:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID
    name: str
    year_end: date
    interim_period_end: date | None
    prior_period_end: date | None
    source_connection_id: UUID | None
    status: Literal["draft", "finalized", "discarded"]
    lock_state: Literal["open", "locked"]
    finalized_by: UUID | None
    finalized_at: datetime | None
    row_version: int
    entities: tuple[EntityRow, ...] = ()
    slots: tuple[SlotRow, ...] = ()  # current stored slots
    required: tuple[SlotKey, ...] = field(default=())

    def slot_of(self, key: SlotKey) -> SlotRow | None:
        return next(
            (
                s
                for s in self.slots
                if (s.key.consolidation_entity_id, s.key.label, s.key.period_kind)
                == (key.consolidation_entity_id, key.label, key.period_kind)
            ),
            None,
        )

    def missing(self) -> tuple[SlotKey, ...]:
        """Every required slot without a TB: absent, or one that cannot be read (Needs reauth,
        A-09-T18) blocks finalize as an absent one does."""
        return tuple(
            k
            for k in self.required
            if (found := self.slot_of(k)) is None or found.state not in ("attached", "not_needed")
        )


@dataclass(frozen=True)
class StructureEntity:
    client_entity_id: UUID
    parent_client_entity_id: UUID | None
    level: int
    city: str | None
    component_auditor_id: UUID | None


def year_start(year_end: date) -> date:
    try:
        return year_end.replace(year=year_end.year - 1) + timedelta(days=1)
    except ValueError:  # Feb 29
        return year_end.replace(year=year_end.year - 1, day=28) + timedelta(days=1)


def required_slots(
    entities: Sequence[EntityRow], year_end: date, interim: date | None, prior: date | None
) -> tuple[SlotKey, ...]:
    """Every entity's current slot and, with a prior period, its prior slot (code's, ADR-050)."""
    start = year_start(year_end)
    out: list[SlotKey] = []
    for e in sorted(entities, key=lambda x: (x.position, x.level)):
        current: Label = "interim" if interim is not None else "standard"
        out.append(SlotKey(e.id, current, "current", start, interim or year_end))
        if prior is not None:
            out.append(SlotKey(e.id, "prior", "prior", year_start(prior), prior))
    return tuple(out)


def check_structure(entities: Sequence[StructureEntity]) -> None:
    """X-06 and the tiers, before the database's own guard."""
    ids = [e.client_entity_id for e in entities]
    if len(set(ids)) != len(ids):
        raise StructureInvalid(facts={"reason": "duplicate_entity"})
    roots = [e for e in entities if e.parent_client_entity_id is None]
    if len(roots) != 1 or roots[0].level != 1:
        raise StructureInvalid(facts={"reason": "one_root"})
    levels = {e.client_entity_id: e.level for e in entities}
    for e in entities:
        if e.level > MAX_TIERS:
            raise StructureInvalid(facts={"reason": "fourth_tier"})
        if e.parent_client_entity_id is None:
            continue
        parent = levels.get(e.parent_client_entity_id)
        if parent is None or parent != e.level - 1:
            raise StructureInvalid(facts={"reason": "parent_level"})


# --- reads ---------------------------------------------------------------------------------------

_GET = text("SELECT * FROM consolidations WHERE id = :i")
_ENTITIES = text(
    "SELECT id, client_entity_id, parent_id, level, city, component_auditor_id, position "
    "FROM consolidation_entities WHERE consolidation_id = :i ORDER BY position, level"
)
_SLOTS = text(
    "SELECT t.id, t.consolidation_entity_id, t.label, t.period_kind, t.period_start, "
    "t.period_end, t.state, t.ledger_snapshot_id, t.source, t.not_needed_reason, "
    "s.total_debit, s.total_credit FROM consolidation_trial_balances t "
    "JOIN consolidation_entities e "
    "ON e.tenant_id = t.tenant_id AND e.id = t.consolidation_entity_id "
    "LEFT JOIN ledger_snapshots s ON s.tenant_id = t.tenant_id AND s.id = t.ledger_snapshot_id "
    "WHERE e.consolidation_id = :i AND t.superseded_by IS NULL"
)


async def consolidation_facts(tenant: TenantContext, consolidation_id: UUID) -> ConsolidationFacts:
    async with tenant_session(tenant) as session:
        head = (await session.execute(_GET, {"i": consolidation_id})).mappings().first()
        if head is None:
            raise NotFound("consolidation")
        entities = [
            dict(r) for r in (await session.execute(_ENTITIES, {"i": consolidation_id})).mappings()
        ]
        slots = [
            dict(r) for r in (await session.execute(_SLOTS, {"i": consolidation_id})).mappings()
        ]
    h = dict(head)
    rows = tuple(EntityRow(**e) for e in entities)
    return ConsolidationFacts(
        id=h["id"],
        engagement_id=h["engagement_id"],
        work_item_id=h["work_item_id"],
        name=h["name"],
        year_end=h["year_end"],
        interim_period_end=h["interim_period_end"],
        prior_period_end=h["prior_period_end"],
        source_connection_id=h["source_connection_id"],
        status=h["status"],
        lock_state=h["lock_state"],
        finalized_by=h["finalized_by"],
        finalized_at=h["finalized_at"],
        row_version=h["row_version"],
        entities=rows,
        slots=tuple(
            SlotRow(
                id=s["id"],
                key=SlotKey(
                    s["consolidation_entity_id"],
                    s["label"],
                    s["period_kind"],
                    s["period_start"],
                    s["period_end"],
                ),
                state=s["state"],
                ledger_snapshot_id=s["ledger_snapshot_id"],
                source=s["source"],
                not_needed_reason=s["not_needed_reason"],
                total_debits=s["total_debit"],
                total_credits=s["total_credit"],
            )
            for s in slots
        ),
        required=required_slots(
            rows, h["year_end"], h["interim_period_end"], h["prior_period_end"]
        ),
    )


async def consolidations_of(tenant: TenantContext, work_item_id: UUID) -> list[UUID]:
    async with tenant_session(tenant) as session:
        found = await session.execute(
            text(
                "SELECT id FROM consolidations WHERE work_item_id = :w AND status <> 'discarded' "
                "ORDER BY created_at"
            ),
            {"w": work_item_id},
        )
        return [cast(UUID, r[0]) for r in found]


_SNAPSHOT = text(
    "SELECT id, client_entity_id, period_end, source_evidence_version_id FROM ledger_snapshots "
    "WHERE id = :i"
)
_NEWEST = text(
    "SELECT id FROM ledger_snapshots WHERE client_entity_id = :e AND period_end = :p "
    "AND (CAST(:ev AS uuid) IS NULL OR source_evidence_version_id = CAST(:ev AS uuid)) "
    "ORDER BY pulled_at DESC, created_at DESC LIMIT 1"
)


async def snapshot_for_slot(
    tenant: TenantContext,
    client_entity_id: UUID,
    period_end: date,
    *,
    snapshot_id: UUID | None = None,
    evidence_version_id: UUID | None = None,
) -> UUID:
    """The immutable TB snapshot a slot attaches: the one named (an upload's), the evidence's, or
    the entity's newest for the period (a covering connection's pull)."""
    async with tenant_session(tenant) as session:
        if snapshot_id is not None:
            found = (await session.execute(_SNAPSHOT, {"i": snapshot_id})).first()
            if found is None:
                raise NotFound("ledger_snapshot")
            if found.client_entity_id != client_entity_id or found.period_end != period_end:
                raise SnapshotMismatch
            return snapshot_id
        newest = (
            await session.execute(
                _NEWEST, {"e": client_entity_id, "p": period_end, "ev": evidence_version_id}
            )
        ).first()
    if newest is None:
        raise NotFound("ledger_snapshot")
    return cast(UUID, newest[0])


# --- writes (inside the caller's unit of work) ---------------------------------------------


async def create_consolidation(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    work_item_id: UUID,
    user_id: UUID,
    name: str,
    year_end: date,
    interim_period_end: date | None,
    prior_period_end: date | None,
    source_connection_id: UUID | None,
) -> UUID:
    consolidation_id = uuid4()
    await tx.session.execute(
        text(
            "INSERT INTO consolidations (id, tenant_id, engagement_id, work_item_id, name, "
            "year_end, reporting_currency, interim_period_end, prior_period_end, "
            "source_connection_id, created_by) VALUES (:id, :t, :e, :w, :n, :y, 'USD', :ip, "
            ":pp, :sc, :u)"
        ),
        {
            "id": consolidation_id,
            "t": tenant_id,
            "e": engagement_id,
            "w": work_item_id,
            "n": name.strip(),
            "y": year_end,
            "ip": interim_period_end,
            "pp": prior_period_end,
            "sc": source_connection_id,
            "u": user_id,
        },
    )
    tx.record(
        "consolidation.created",
        target=Target(TARGET, consolidation_id),
        after=Ref(engagement=engagement_id, work_item=work_item_id),
    )
    return consolidation_id


_BUMPS: Final = {
    "edit": text(
        "UPDATE consolidations SET name = :n, year_end = :y, interim_period_end = :ip, "
        "prior_period_end = :pp, source_connection_id = :sc, row_version = row_version + 1 "
        "WHERE id = :i AND row_version = :v AND status = 'draft' RETURNING id"
    ),
    "discard": text(
        "UPDATE consolidations SET status = 'discarded', row_version = row_version + 1 "
        "WHERE id = :i AND row_version = :v AND status = 'draft' RETURNING id"
    ),
    "touch": text(
        "UPDATE consolidations SET row_version = row_version + 1 "
        "WHERE id = :i AND row_version = :v AND status = 'draft' RETURNING id"
    ),
}


async def _bump(
    tx: UnitOfWork, consolidation_id: UUID, seen: int, kind: str, values: dict[str, object]
) -> None:
    done = await tx.session.execute(_BUMPS[kind], {"i": consolidation_id, "v": seen, **values})
    if done.first() is None:
        current = (await tx.session.execute(_GET, {"i": consolidation_id})).first()
        if current is None:
            raise NotFound("consolidation")
        if current.status != "draft":
            raise ConsolidationNotDraft
        raise VersionStale


async def edit_consolidation(
    tx: UnitOfWork,
    consolidation_id: UUID,
    seen: int,
    *,
    name: str,
    year_end: date,
    interim_period_end: date | None,
    prior_period_end: date | None,
    source_connection_id: UUID | None,
) -> None:
    await _bump(
        tx,
        consolidation_id,
        seen,
        "edit",
        {
            "n": name.strip(),
            "y": year_end,
            "ip": interim_period_end,
            "pp": prior_period_end,
            "sc": source_connection_id,
        },
    )
    tx.record("consolidation.edited", target=Target(TARGET, consolidation_id))


async def discard_consolidation(tx: UnitOfWork, consolidation_id: UUID) -> None:
    current = (await tx.session.execute(_GET, {"i": consolidation_id})).first()
    if current is None:
        raise NotFound("consolidation")
    await _bump(tx, consolidation_id, int(current.row_version), "discard", {})
    tx.record("consolidation.discarded", target=Target(TARGET, consolidation_id))


async def save_structure(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    consolidation_id: UUID,
    seen: int,
    entities: Sequence[StructureEntity],
) -> None:
    """Replace the draft structure: entities kept are updated in place (their TB slots stay),
    new ones inserted, dropped ones deleted (refused once a TB is attached to one)."""
    check_structure(entities)
    await _bump(tx, consolidation_id, seen, "touch", {})
    existing = {
        r.client_entity_id: r.id
        for r in await tx.session.execute(
            text(
                "SELECT id, client_entity_id FROM consolidation_entities "
                "WHERE consolidation_id = :i"
            ),
            {"i": consolidation_id},
        )
    }
    wanted = {e.client_entity_id for e in entities}
    dropped = [eid for cid, eid in existing.items() if cid not in wanted]
    if dropped:
        has_tb = await tx.session.execute(
            text(
                "SELECT 1 FROM consolidation_trial_balances "
                "WHERE consolidation_entity_id = ANY(:d) LIMIT 1"
            ),
            {"d": dropped},
        )
        if has_tb.first() is not None:
            raise StructureInvalid(facts={"reason": "entity_has_trial_balances"})
        # Children before parents: the deepest tier first.
        for level in (3, 2, 1):
            await tx.session.execute(
                text("DELETE FROM consolidation_entities WHERE id = ANY(:d) AND level = :l"),
                {"d": dropped, "l": level},
            )
    ids = dict(existing)
    order = {e.client_entity_id: n for n, e in enumerate(entities)}
    for e in sorted(entities, key=lambda x: x.level):
        position = order[e.client_entity_id]
        parent = None if e.parent_client_entity_id is None else ids[e.parent_client_entity_id]
        values = {
            "p": parent,
            "l": e.level,
            "c": e.city,
            "a": e.component_auditor_id,
            "pos": position,
        }
        if e.client_entity_id in existing:
            await tx.session.execute(
                text(
                    "UPDATE consolidation_entities SET parent_id = :p, level = :l, city = :c, "
                    "component_auditor_id = :a, position = :pos WHERE id = :id"
                ),
                {**values, "id": existing[e.client_entity_id]},
            )
        else:
            new_id = uuid4()
            await tx.session.execute(
                text(
                    "INSERT INTO consolidation_entities (id, tenant_id, consolidation_id, "
                    "client_entity_id, parent_id, level, city, component_auditor_id, position) "
                    "VALUES (:id, :t, :cid, :e, :p, :l, :c, :a, :pos)"
                ),
                {
                    **values,
                    "id": new_id,
                    "t": tenant_id,
                    "cid": consolidation_id,
                    "e": e.client_entity_id,
                },
            )
            ids[e.client_entity_id] = new_id
    tx.record(
        "consolidation.structure_saved",
        target=Target(TARGET, consolidation_id),
        after=Ref(entities=len(entities), tiers=max(e.level for e in entities)),
    )


async def _replace_slot(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    key: SlotKey,
    state: str,
    snapshot_id: UUID | None,
    source: Source | None,
    evidence_version_id: UUID | None,
    reason: str | None,
    user_id: UUID,
) -> UUID:
    new_id = uuid4()
    # The deferred FK (0899): the old row points at its successor before the successor exists.
    await tx.session.execute(
        text(
            "UPDATE consolidation_trial_balances SET superseded_by = :n "
            "WHERE consolidation_entity_id = :e AND label = :l AND period_kind = :k "
            "AND superseded_by IS NULL"
        ),
        {"n": new_id, "e": key.consolidation_entity_id, "l": key.label, "k": key.period_kind},
    )
    await tx.session.execute(
        text(
            "INSERT INTO consolidation_trial_balances (id, tenant_id, consolidation_entity_id, "
            "label, period_kind, period_start, period_end, ledger_snapshot_id, state, source, "
            "evidence_version_id, not_needed_reason, attached_by) VALUES (:id, :t, :e, :l, :k, "
            ":ps, :pe, :s, :st, :src, :ev, :r, :u)"
        ),
        {
            "id": new_id,
            "t": tenant_id,
            "e": key.consolidation_entity_id,
            "l": key.label,
            "k": key.period_kind,
            "ps": key.period_start,
            "pe": key.period_end,
            "s": snapshot_id,
            "st": state,
            "src": source,
            "ev": evidence_version_id,
            "r": reason,
            "u": user_id,
        },
    )
    return new_id


async def mark_slot_needs_reauth(
    tx: UnitOfWork, *, tenant_id: UUID, key: SlotKey, user_id: UUID
) -> UUID:
    """A-09-T18 (DEC-5329): a pull whose token was refused leaves its slot Needs reauth (a new
    slot row; the old one points at it). Never retried here."""
    slot = await _replace_slot(
        tx,
        tenant_id=tenant_id,
        key=key,
        state="needs_reauth",
        snapshot_id=None,
        source="connection",
        evidence_version_id=None,
        reason=None,
        user_id=user_id,
    )
    tx.record(
        "consolidation.slot_needs_reauth",
        target=Target("consolidation_trial_balance", slot),
    )
    return slot


async def _require_draft(tx: UnitOfWork, consolidation_id: UUID) -> None:
    current = (await tx.session.execute(_GET, {"i": consolidation_id})).first()
    if current is None:
        raise NotFound("consolidation")
    if current.status != "draft":
        raise ConsolidationNotDraft


async def attach_trial_balance(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    consolidation_id: UUID,
    key: SlotKey,
    snapshot_id: UUID,
    source: Source,
    evidence_version_id: UUID | None,
    user_id: UUID,
) -> UUID:
    await _require_draft(tx, consolidation_id)
    slot_id = await _replace_slot(
        tx,
        tenant_id=tenant_id,
        key=key,
        state="attached",
        snapshot_id=snapshot_id,
        source=source,
        evidence_version_id=evidence_version_id,
        reason=None,
        user_id=user_id,
    )
    tx.record(
        "consolidation.trial_balance_attached",
        target=Target(TARGET, consolidation_id),
        after=Ref(slot=slot_id, snapshot=snapshot_id),  # the source is on the slot row
    )
    return slot_id


async def mark_not_needed(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    consolidation_id: UUID,
    key: SlotKey,
    reason: str,
    user_id: UUID,
) -> UUID:
    await _require_draft(tx, consolidation_id)
    slot_id = await _replace_slot(
        tx,
        tenant_id=tenant_id,
        key=key,
        state="not_needed",
        snapshot_id=None,
        source=None,
        evidence_version_id=None,
        reason=reason.strip(),
        user_id=user_id,
    )
    tx.record(
        "consolidation.trial_balance_not_needed",
        target=Target(TARGET, consolidation_id),
        after=Ref(slot=slot_id),
    )
    return slot_id


@dataclass(frozen=True)
class Finalized:
    """The attached current snapshot of each entity, for the caller's mapping runs."""

    entity_snapshots: tuple[tuple[UUID, UUID, Label, date, date], ...]  # (client entity, snapshot,
    # label, period start, period end)


async def finalize(
    tx: UnitOfWork,
    facts: ConsolidationFacts,
    *,
    tenant_id: UUID,
    seen: int,
    user_id: UUID,
) -> Finalized:
    """A person's act (the caller checked); refuses a missing slot before anything changes."""
    if facts.status != "draft":
        raise ConsolidationNotDraft
    if facts.row_version != seen:
        raise VersionStale
    missing = facts.missing()
    if missing:
        raise TrialBalanceMissing(facts={"missing": len(missing)})
    done = await tx.session.execute(
        text(
            "UPDATE consolidations SET status = 'finalized', finalized_by = :u, "
            "finalized_at = clock_timestamp(), finalized_actor_kind = 'human', "
            "row_version = row_version + 1 "
            "WHERE id = :i AND row_version = :v AND status = 'draft' RETURNING id"
        ),
        {"u": user_id, "i": facts.id, "v": seen},
    )
    if done.first() is None:
        raise VersionStale
    await tx.session.execute(
        text(
            "INSERT INTO consolidation_events (tenant_id, consolidation_id, kind, actor_kind, "
            "actor_id) VALUES (:t, :i, 'finalized', 'human', :u)"
        ),
        {"t": tenant_id, "i": facts.id, "u": user_id},
    )
    tx.record(
        "consolidation.finalized",
        target=Target(TARGET, facts.id),
        after=Ref(entities=len(facts.entities)),
    )
    by_entity = {e.id: e.client_entity_id for e in facts.entities}
    current = [
        s
        for s in facts.slots
        if s.key.period_kind == "current" and s.state == "attached" and s.ledger_snapshot_id
    ]
    return Finalized(
        tuple(
            (
                by_entity[s.key.consolidation_entity_id],
                cast(UUID, s.ledger_snapshot_id),
                s.key.label,
                s.key.period_start,
                s.key.period_end,
            )
            for s in current
        )
    )


# --- lock and reopen (A-09-T19 rest; DEC-5328) -------------------------------------------------


class ConsolidationLockState(DomainConflict):
    code = "consolidation_lock_state"


class ReopenReasonRequired(DomainInvalid):
    """S48 rest (A-09-T26 found it): a reopen's reason is blank once trimmed (AC-4.5)."""

    code = "reopen_reason_required"


async def lock(
    tx: UnitOfWork, facts: ConsolidationFacts, *, tenant_id: UUID, user_id: UUID
) -> None:
    """A person locks a finalized consolidation (AC-4.5): edits are refused until a reopen."""
    if facts.status != "finalized" or facts.lock_state != "open":
        raise ConsolidationLockState(facts={"lock_state": facts.lock_state})
    done = await tx.session.execute(
        text(
            "UPDATE consolidations SET lock_state = 'locked', locked_by = :u, "
            "locked_at = clock_timestamp(), locked_actor_kind = 'human', "
            "row_version = row_version + 1 WHERE id = :i AND lock_state = 'open' RETURNING id"
        ),
        {"u": user_id, "i": facts.id},
    )
    if done.first() is None:
        raise VersionStale
    await tx.session.execute(
        text(
            "INSERT INTO consolidation_events (tenant_id, consolidation_id, kind, actor_kind, "
            "actor_id) VALUES (:t, :i, 'locked', 'human', :u)"
        ),
        {"t": tenant_id, "i": facts.id, "u": user_id},
    )
    tx.record("consolidation.locked", target=Target(TARGET, facts.id))


async def reopen(
    tx: UnitOfWork, facts: ConsolidationFacts, *, tenant_id: UUID, user_id: UUID, reason: str
) -> None:
    """A Manager or the EP reopens with a reason (AC-4.5); the event keeps the reason."""
    if not reason.strip():
        raise ReopenReasonRequired
    if facts.lock_state != "locked":
        raise ConsolidationLockState(facts={"lock_state": facts.lock_state})
    done = await tx.session.execute(
        text(
            "UPDATE consolidations SET lock_state = 'open', locked_by = NULL, locked_at = NULL, "
            "locked_actor_kind = NULL, row_version = row_version + 1 "
            "WHERE id = :i AND lock_state = 'locked' RETURNING id"
        ),
        {"i": facts.id},
    )
    if done.first() is None:
        raise VersionStale
    await tx.session.execute(
        text(
            "INSERT INTO consolidation_events (tenant_id, consolidation_id, kind, reason, "
            "actor_kind, actor_id) VALUES (:t, :i, 'reopened', :r, 'human', :u)"
        ),
        {"t": tenant_id, "i": facts.id, "r": reason.strip()[:500], "u": user_id},
    )
    tx.record("consolidation.reopened", target=Target(TARGET, facts.id))
