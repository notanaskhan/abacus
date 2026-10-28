"""What CLI-06's single intake reads and writes in organisations (P-07-T42; DEC-374, DEC-430,
DEC-441). Engagements' intake service calls these through `organisations.api`.

- **Dedupe** (`dedupe_candidates`): the firm's clients and client entities whose normalised name
  matches the name typed, scored 0-1 (DEC-441): the same normalised name is 1.0; the same name
  once a fiduciary designator is set aside ("Estate of", "The", "Revocable Trust", "Trust") is
  1.0 less 0.02 per designator word (so "Estate of Walter Thornbury" against "Walter Thornbury"
  is 0.96, CLI-06 b); otherwise the `pg_trgm` similarity of the normalised names, at least 0.6
  (the conflict search's floor, DEC-373). One candidate per client, its best match. A client the
  person is walled from is never a candidate (DEC-43). No TIN is read: the dedupe takes a name.
- **Writes inside the caller's unit of work** (the intake commit authorised `client.intake` on
  the client): a relationship edge from the new entity to an entity of a client the person may
  see, and a contact with its roles on the new entity.
- **The conflict check** on an intake draft searches the draft's own names and is compared with
  the draft's names at commit (`conflicts.check_clear_for`; P-07-T42 security review, H1).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, cast, get_args
from uuid import UUID

from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, UnitOfWork
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise,
    hidden_clients,
    walled_from,
)
from abacus.modules.organisations.events import ContactCreated
from abacus.modules.organisations.models import EntityRelationship
from abacus.modules.organisations.repository import replace_contact_roles
from abacus.modules.organisations.service import EntityType, NewContact, add_contact, normalise

DEDUPE: Final = "client.create"
DEDUPE_FLOOR: Final = 0.6  # the conflict search's trigram floor (DEC-373)
DESIGNATOR_STEP: Final = 0.02  # DEC-441: what each fiduciary designator word costs
DEDUPE_LIMIT: Final = 5
# Leading and trailing words that name a fiduciary form of the same person or family.
_LEADING: Final[tuple[tuple[str, ...], ...]] = (
    ("the", "estate", "of"),
    ("estate", "of"),
    ("the",),
)
_TRAILING: Final[tuple[tuple[str, ...], ...]] = (
    ("revocable", "living", "trust"),
    ("irrevocable", "trust"),
    ("revocable", "trust"),
    ("living", "trust"),
    ("family", "trust"),
    ("trust",),
)
ENTITY_TYPES: Final[frozenset[str]] = frozenset(get_args(EntityType))
# `entity_relationships.kind` (0103) and `contact_roles.role` (0146), as their CHECKs list them.
RELATIONSHIP_KINDS: Final[frozenset[str]] = frozenset(
    {
        "spouse",
        "owner_of",
        "trustee_of",
        "beneficiary_of",
        "sponsor_of",
        "upper_tier_of",
        "executor_of",
        "gp_of",
        "lp_of",
        "estate_of",
    }
)
CONTACT_ROLES: Final[frozenset[str]] = frozenset(
    {
        "owner",
        "cfo",
        "controller",
        "trustee",
        "executor",
        "taxpayer",
        "spouse",
        "plan_sponsor_officer",
        "recordkeeper",
        "tpa",
        "custodian",
        "payroll_provider",
        "other",
    }
)

_MATCHES = text(
    """
    SELECT c.id AS client_id, c.name AS client_name, NULL::uuid AS entity_id,
           NULL::text AS entity_name, c.normalised_name AS normalised,
           similarity(c.normalised_name, :q) AS sim
      FROM clients c
     WHERE c.normalised_name % :q OR c.normalised_name IN (:q, :core)
    UNION ALL
    SELECT e.client_id, c.name, e.id, e.name, e.normalised_name, similarity(e.normalised_name, :q)
      FROM client_entities e JOIN clients c ON c.id = e.client_id
     WHERE e.normalised_name % :q OR e.normalised_name IN (:q, :core)
    """
)


def core_name(normalised: str) -> tuple[str, int]:
    """The name without its fiduciary designators, and how many words were set aside."""
    words = normalised.split()
    dropped = 0
    for lead in _LEADING:
        if len(words) > len(lead) and tuple(words[: len(lead)]) == lead:
            words, dropped = words[len(lead) :], dropped + len(lead)
            break
    for trail in _TRAILING:
        if len(words) > len(trail) and tuple(words[-len(trail) :]) == trail:
            words, dropped = words[: -len(trail)], dropped + len(trail)
            break
    return " ".join(words), dropped


def score_names(typed: str, stored: str, similarity: float) -> float | None:
    """DEC-441's score of a stored normalised name against the typed one, or None below the
    floor. Pure, so the unit suite pins the rule."""
    if not typed or not stored:
        return None
    if typed == stored:
        return 1.0
    typed_core, typed_dropped = core_name(typed)
    stored_core, stored_dropped = core_name(stored)
    if typed_core and typed_core == stored_core:
        return round(1.0 - DESIGNATOR_STEP * max(typed_dropped, stored_dropped, 1), 4)
    return round(similarity, 4) if similarity >= DEDUPE_FLOOR else None


@dataclass(frozen=True)
class DedupeMatch:
    client_id: UUID
    display_name: str
    client_entity_id: UUID | None
    entity_name: str | None
    score: float
    basis: str = "name"


async def dedupe_candidates(ctx: AuthContext, name: str) -> list[DedupeMatch]:
    """CLI-06 b's dedupe card: scored candidates the person may see, best first."""
    await authorise(ctx, DEDUPE, Resource.firm(ctx.tenant_id))
    typed = normalise(name)
    if not typed:
        return []
    core, _ = core_name(typed)
    async with tenant_session(ctx.tenant) as session:
        await session.execute(text("SET LOCAL pg_trgm.similarity_threshold = 0.6"))
        rows = (await session.execute(_MATCHES, {"q": typed, "core": core})).mappings().all()
    walled = await walled_from(ctx.tenant, ctx.user_id)
    best: dict[UUID, DedupeMatch] = {}
    for r in rows:
        client_id = cast(UUID, r["client_id"])
        if client_id in walled:
            continue  # DEC-43: never a candidate, never counted
        score = score_names(typed, cast(str, r["normalised"]), float(cast(float, r["sim"])))
        if score is None:
            continue
        match = DedupeMatch(
            client_id,
            cast(str, r["client_name"]),
            cast(UUID | None, r["entity_id"]),
            cast(str | None, r["entity_name"]),
            score,
        )
        current = best.get(client_id)
        if current is None or (match.score, current.client_entity_id is not None) > (
            current.score,
            match.client_entity_id is not None,
        ):
            best[client_id] = match
    ranked = sorted(best.values(), key=lambda m: (-m.score, m.display_name, str(m.client_id)))
    return ranked[:DEDUPE_LIMIT]


_EIN_MATCHES = text(
    """
    SELECT e.tin_fingerprint AS fingerprint, c.id AS client_id, c.name AS client_name,
           e.id AS entity_id, e.name AS entity_name
      FROM client_entities e JOIN clients c ON c.id = e.client_id
     WHERE e.tin_kind = 'ein' AND e.tin_fingerprint = ANY(:fingerprints)
    """
)


async def ein_matches(ctx: AuthContext, fingerprints: Sequence[bytes]) -> dict[bytes, DedupeMatch]:
    """CLI-06's bulk import (P-07-T52): the entity whose EIN fingerprint (`fingerprint_tin`) is
    each given one, scored 1.0 on basis `ein`; one per fingerprint (the index is unique per
    firm). A client the person is walled from is never a match (DEC-43). No digits are read."""
    await authorise(ctx, DEDUPE, Resource.firm(ctx.tenant_id))
    if not fingerprints:
        return {}
    async with tenant_session(ctx.tenant) as session:
        rows = (
            (
                await session.execute(
                    _EIN_MATCHES, {"fingerprints": list(dict.fromkeys(fingerprints))}
                )
            )
            .mappings()
            .all()
        )
    walled = await walled_from(ctx.tenant, ctx.user_id)
    return {
        bytes(cast(bytes, r["fingerprint"])): DedupeMatch(
            cast(UUID, r["client_id"]),
            cast(str, r["client_name"]),
            cast(UUID, r["entity_id"]),
            cast(str, r["entity_name"]),
            1.0,
            "ein",
        )
        for r in rows
        if cast(UUID, r["client_id"]) not in walled
    }


async def same_name_client(ctx: AuthContext, name: str) -> UUID | None:
    """A client the person may see whose normalised name is exactly `name`'s (the commit's 409
    `possible_duplicate` for a new client)."""
    for match in await dedupe_candidates(ctx, name):
        if match.score >= 1.0 and match.client_entity_id is None:
            return match.client_id
    return None


# --- writes inside the commit's unit of work ---------------------------------------------------


async def add_intake_relationship(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    client_id: UUID,
    from_entity_id: UUID,
    to_entity_id: UUID,
    kind: str,
    effective_from: date,
) -> UUID:
    """An edge from the intake's entity to an entity of a client the person may see (a walled
    or unknown entity is 404, the same answer)."""
    other = (
        await tx.session.execute(
            text("SELECT client_id FROM client_entities WHERE id = :id"), {"id": to_entity_id}
        )
    ).scalar_one_or_none()
    if other is None or await hidden_clients(ctx.tenant, ctx.user_id, [cast(UUID, other)]):
        raise NotFound("client_entity")
    try:
        async with tx.session.begin_nested():
            edge = (
                await tx.session.execute(
                    insert(EntityRelationship)
                    .values(
                        tenant_id=ctx.tenant_id,
                        from_entity_id=from_entity_id,
                        to_entity_id=to_entity_id,
                        kind=kind,
                        effective_from=effective_from,
                        created_by=ctx.user_id,
                    )
                    .returning(EntityRelationship.id)
                )
            ).scalar_one()
    except IntegrityError:
        raise NotFound("client_entity") from None
    tx.record("entity_relationship.created", target=Target("client", client_id))
    return edge


async def add_intake_contact(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    client_id: UUID,
    entity_id: UUID,
    name: str,
    email: str | None,
    roles: Sequence[str],
) -> UUID:
    """A client contact with its roles on the intake's entity (CLI-06 d)."""
    contact_id = await add_contact(
        tx, ctx.tenant_id, client_id, NewContact(name, "client_person", email=email)
    )
    await replace_contact_roles(
        tx.session,
        ctx.tenant_id,
        contact_id,
        [(role, "client_entity", entity_id, None) for role in dict.fromkeys(roles)],
    )
    tx.emit(ContactCreated(client_id=client_id, contact_id=contact_id))
    return contact_id
