"""T-06-T21: the relationship service (SPEC-702 F8; T-06 §4.3; DEC-5632). PROTECTED (red).

Writes to `entity_relationships` (P-07's table, widened by 0954) and its insert-only event log
`entity_relationship_events`, each in one unit of work with an audit event:

- **Create** (`create`): an entity or an external party on either side; never a self-edge (422
  `relationship_self_edge`); an ownership edge (`owner_of`, `gp_of`, `lp_of`) may not take the
  owned entity past 100 percent on any day it is in force (422 `relationship_percent_exceeds`,
  checked here in code and again by 0954's deferred constraint trigger).
- **Update** (`update`): percent, note or the end date, with optimistic concurrency on `version`.
- **End** (`end`): an end date and a reason; ended, never deleted.
- **External parties** (`add_external_party`): a person or organisation outside the firm's
  clients, kept on the client.

Every write carries the actor and, for a delegated act, `on_behalf_of` (the event row's GUC
defaults). Walls answer 404 with no count (DEC-43): the caller authorises the client first and
this service reads nothing outside it. Graph annotators register through
`register_relationship_annotator` (fail closed: an unregistered annotator adds nothing).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Scope, Target, UnitOfWork, uow
from abacus.modules.organisations.relationship_errors import (
    RelationshipPercentExceeds,
    RelationshipSelfEdge,
)

TARGET: Final = "entity_relationship"
OWNERSHIP: Final = frozenset({"owner_of", "gp_of", "lp_of"})
NodeKind = Literal["entity", "external_party"]
# (tenant, client) -> extra node facts by node id; registered by their owners (tax: K-1 flows).
Annotator = Callable[[TenantContext, UUID], Awaitable[Mapping[UUID, Mapping[str, str]]]]
_ANNOTATORS: dict[str, Annotator] = {}


class RelationshipVersionMoved(DomainConflict):
    """The relationship changed since it was read (`facts.version`)."""

    code = "relationship_version_moved"


def register_relationship_annotator(key: str, annotator: Annotator) -> None:
    if key in _ANNOTATORS and _ANNOTATORS[key] is not annotator:
        raise ValueError(f"relationship annotator {key!r} is already registered")
    _ANNOTATORS[key] = annotator


def relationship_annotators() -> tuple[str, ...]:
    return tuple(sorted(_ANNOTATORS))


@dataclass(frozen=True)
class Edge:
    to_entity_id: UUID | None
    kind: str
    percent: Decimal | None
    effective_from: date
    effective_to: date | None


def cap_exceeded(existing: Sequence[Edge], new: Edge) -> bool:
    """Whether adding `new` takes its owned entity past 100 percent on any day it is in force
    (the days checked are the edges' start dates, where a total can change upward)."""
    if new.kind not in OWNERSHIP or new.percent is None or new.to_entity_id is None:
        return False
    edges = [e for e in existing if e.to_entity_id == new.to_entity_id and e.kind in OWNERSHIP]
    edges.append(new)
    for day in {e.effective_from for e in edges}:
        total = sum(
            (
                e.percent or Decimal("0")
                for e in edges
                if e.effective_from <= day and (e.effective_to is None or e.effective_to >= day)
            ),
            Decimal("0"),
        )
        if total > 100:
            return True
    return False


async def _node(tx: UnitOfWork, node_id: UUID) -> NodeKind:
    entity = (
        await tx.session.execute(
            text("SELECT 1 FROM client_entities WHERE id = :i"), {"i": node_id}
        )
    ).first()
    if entity is not None:
        return "entity"
    party = (
        await tx.session.execute(
            text("SELECT 1 FROM external_parties WHERE id = :i"), {"i": node_id}
        )
    ).first()
    if party is not None:
        return "external_party"
    raise NotFound("relationship_node")


async def _edges_into(tx: UnitOfWork, entity_id: UUID) -> list[Edge]:
    rows = (
        await tx.session.execute(
            text(
                "SELECT to_entity_id, kind, percent, effective_from, effective_to "
                "FROM entity_relationships WHERE to_entity_id = :e AND ended_at IS NULL"
            ),
            {"e": entity_id},
        )
    ).all()
    return [Edge(r[0], str(r[1]), r[2], r[3], r[4]) for r in rows]


async def _event(
    tx: UnitOfWork,
    tenant: TenantContext,
    rel_id: UUID,
    event: str,
    before: Mapping[str, object] | None,
    after: Mapping[str, object] | None,
) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO entity_relationship_events (tenant_id, relationship_id, event, before, "
            "after, on_behalf_of) VALUES (:t, :r, :e, CAST(:b AS jsonb), CAST(:a AS jsonb), "
            "NULLIF(current_setting('app.on_behalf_of', true), '')::uuid)"
        ),
        {
            "t": tenant.tenant_id,
            "r": rel_id,
            "e": event,
            "b": None if before is None else json.dumps(before, default=str),
            "a": None if after is None else json.dumps(after, default=str),
        },
    )


async def create(
    tenant: TenantContext,
    actor_user_id: UUID,
    client_id: UUID,
    *,
    from_node_id: UUID,
    to_node_id: UUID,
    kind: str,
    percent: Decimal | None,
    effective_from: date,
    note: str | None,
) -> UUID:
    if from_node_id == to_node_id:
        raise RelationshipSelfEdge
    async with uow(tenant) as tx:
        from_kind = await _node(tx, from_node_id)
        to_kind = await _node(tx, to_node_id)
        if to_kind == "entity" and cap_exceeded(
            await _edges_into(tx, to_node_id),
            Edge(to_node_id, kind, percent, effective_from, None),
        ):
            raise RelationshipPercentExceeds(facts={"to": str(to_node_id)})
        cols = {
            "from_entity_id": from_node_id if from_kind == "entity" else None,
            "from_external_party_id": from_node_id if from_kind == "external_party" else None,
            "to_entity_id": to_node_id if to_kind == "entity" else None,
            "to_external_party_id": to_node_id if to_kind == "external_party" else None,
        }
        rel_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO entity_relationships (tenant_id, from_entity_id, "
                    "from_external_party_id, to_entity_id, to_external_party_id, kind, percent, "
                    "effective_from, created_by, source, note) VALUES (:t, :fe, :fp, :te, :tp, "
                    ":k, :p, :f, :by, 'manual', :n) RETURNING id"
                ),
                {
                    "t": tenant.tenant_id,
                    "fe": cols["from_entity_id"],
                    "fp": cols["from_external_party_id"],
                    "te": cols["to_entity_id"],
                    "tp": cols["to_external_party_id"],
                    "k": kind,
                    "p": percent,
                    "f": effective_from,
                    "by": actor_user_id,
                    "n": note,
                },
            )
        ).scalar_one()
        rel = UUID(str(rel_id))
        await _event(tx, tenant, rel, "created", None, {"kind": kind, "percent": percent})
        tx.record(
            "relationship.created", target=Target(TARGET, rel), scope=Scope(client_id=client_id)
        )
    return rel


async def update(
    tenant: TenantContext,
    client_id: UUID,
    rel_id: UUID,
    *,
    expected_version: int,
    percent: Decimal | None = None,
    note: str | None = None,
    effective_to: date | None = None,
) -> None:
    async with uow(tenant) as tx:
        row = (
            await tx.session.execute(
                text(
                    "SELECT version, percent, note, effective_to, kind, to_entity_id, "
                    "effective_from FROM entity_relationships WHERE id = :r AND ended_at IS NULL "
                    "FOR UPDATE"
                ),
                {"r": rel_id},
            )
        ).first()
        if row is None:
            raise NotFound(TARGET)
        if int(row[0]) != expected_version:
            raise RelationshipVersionMoved(facts={"version": int(row[0])})
        new_percent = row[1] if percent is None else percent
        if row[5] is not None and percent is not None:
            others = [e for e in await _edges_into(tx, row[5])]
            # the edge itself is replaced by its new percent
            mine = Edge(row[5], str(row[4]), row[1], row[6], row[3])
            others = [e for e in others if e != mine]
            if cap_exceeded(others, Edge(row[5], str(row[4]), new_percent, row[6], effective_to)):
                raise RelationshipPercentExceeds(facts={"to": str(row[5])})
        await tx.session.execute(
            text(
                "UPDATE entity_relationships SET percent = :p, note = COALESCE(:n, note), "
                "effective_to = COALESCE(:to, effective_to), version = version + 1 WHERE id = :r"
            ),
            {"p": new_percent, "n": note, "to": effective_to, "r": rel_id},
        )
        await _event(tx, tenant, rel_id, "updated", {"percent": row[1]}, {"percent": new_percent})
        tx.record(
            "relationship.updated", target=Target(TARGET, rel_id), scope=Scope(client_id=client_id)
        )


async def end(
    tenant: TenantContext,
    actor_user_id: UUID,
    client_id: UUID,
    rel_id: UUID,
    *,
    effective_to: date,
    reason: str,
) -> None:
    async with uow(tenant) as tx:
        changed = (
            await tx.session.execute(
                text(
                    "UPDATE entity_relationships SET effective_to = :to, ended_at = now(), "
                    "ended_by = :by, end_reason = :why, version = version + 1 "
                    "WHERE id = :r AND ended_at IS NULL RETURNING id"
                ),
                {"to": effective_to, "by": actor_user_id, "why": reason, "r": rel_id},
            )
        ).first()
        if changed is None:
            raise NotFound(TARGET)
        await _event(tx, tenant, rel_id, "ended", None, {"effective_to": effective_to})
        tx.record(
            "relationship.ended", target=Target(TARGET, rel_id), scope=Scope(client_id=client_id)
        )


async def add_external_party(
    tenant: TenantContext,
    actor_user_id: UUID,
    client_id: UUID,
    *,
    display_name: str,
    kind: Literal["individual", "entity", "trust", "fund"],
    note: str | None = None,
) -> UUID:
    async with uow(tenant) as tx:
        party = (
            await tx.session.execute(
                text(
                    "INSERT INTO external_parties (tenant_id, client_id, display_name, kind, "
                    "note, created_by) VALUES (:t, :c, :n, :k, :note, :by) RETURNING id"
                ),
                {
                    "t": tenant.tenant_id,
                    "c": client_id,
                    "n": display_name,
                    "k": kind,
                    "note": note,
                    "by": actor_user_id,
                },
            )
        ).scalar_one()
        tx.record(
            "external_party.created",
            target=Target("external_party", UUID(str(party))),
            scope=Scope(client_id=client_id),
        )
    return UUID(str(party))
