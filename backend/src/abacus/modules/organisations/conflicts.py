"""Conflict checks and screening records, live (P-07-T36; CLI-06 a and h, CLI-08 c; SPEC-332
AC-23 to AC-26; DEC-373).

- **The search** is deterministic and synchronous: at most 50 names, a 2-second statement
  timeout, run as a system principal over metadata only (names and relationships, never
  documents), so walls do not narrow what is found. For each name: clients and client entities
  whose normalised name equals it (`exact`) or is similar to it (`trigram`, `pg_trgm`
  similarity of at least 0.6); contacts the same, except that a contact holding a counterparty
  role (custodian, recordkeeper, TPA, payroll provider) is a `counterparty` match on its client;
  and for each matched entity, every relationship edge to an entity of another client is a
  `relationship` match on that client. One result per matched client and kind (the best score).
  The names are sealed per tenant, bound to the check.
- **Redaction** happens when a check is read, per reader: every result on a client the reader
  is walled from collapses into one restricted row (the first one's id, the weakest kind,
  `pending`) and
  the check's `restricted_match` flag; the outcome counts only what the reader may see. No count
  of walled matches is given anywhere, and clearing one answers 404, as an unknown result does
  (DEC-375).
- **Clearance** is a person's (never an agent or the platform), with an assessment code and a
  sealed reason, as an insert-only event; the newest event is the result's assessment.
- **Screening** results are recorded by a person; nothing is looked up.

`clear_conflict_result` is named only here, in its route and in `organisations/api.py` (banned
pattern CONFLICT-001).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID, uuid4

import asyncpg
from sqlalchemy import RowMapping, TextClause, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound, ServiceUnavailable
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    hidden_clients,
    walled_from,
)
from abacus.modules.organisations.service import normalise
from abacus.modules.organisations.slots import evidence_visible, subject_visible

RUN: Final = "conflict.run"
CLEAR: Final = "conflict.clear"
RECORD: Final = "screening.record"
TRIGRAM_FLOOR: Final = 0.6
COUNTERPARTY_ROLES: Final = ("custodian", "recordkeeper", "tpa", "payroll_provider")
# Assessments that leave a hit standing; the others clear it.
_STANDING: Final = frozenset({"pending", "counterparty_review", "conflict"})
_NON_ALNUM: Final = re.compile(r"[^a-z0-9]+")
# DEC-375 (M2): however many matches fall on clients the reader is walled from, and of whatever
# kind or assessment, the reader sees one row: the first such result's id (an unwalled colleague
# sees that row in full), the weakest kind and `pending`. Nothing tells how many there are or
# how close they are, and clearing it answers 404 like an unknown result.
RESTRICTED_KIND: Final = "trigram"

SubjectKind = Literal["client", "client_entity", "engagement_draft", "client_intake_draft"]
MatchKind = Literal["exact", "trigram", "relationship", "counterparty"]
_AUDIT_TARGET: Final[dict[str, str]] = {
    "client": "client",
    "client_entity": "client_entity",
    "engagement_draft": "engagement_draft",
    "client_intake_draft": "client_intake_draft",
}


@dataclass(frozen=True)
class Hit:
    name_index: int
    ref_type: Literal["client", "client_entity", "contact"]
    ref_id: UUID
    client_id: UUID
    kind: MatchKind
    score: float
    counterparty_role: str | None = None


@dataclass(frozen=True)
class SubjectRef:
    kind: str
    id: UUID


@dataclass(frozen=True)
class ResultView:
    id: UUID
    redacted: bool
    match_kind: str
    assessment: str
    matched_client_id: UUID | None = None
    matched_name: str | None = None
    matched_ref_type: str | None = None
    matched_ref_id: UUID | None = None
    score: float | None = None
    cleared_by: UUID | None = None
    cleared_at: datetime | None = None
    allowed_actions: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class CheckView:
    id: UUID
    subject: SubjectRef
    names_count: int
    outcome: str
    run_by: UUID
    run_at: datetime
    results: list[ResultView]
    restricted_match: bool = False


@dataclass(frozen=True)
class ScreeningView:
    id: UUID
    subject: SubjectRef
    screening_list: str
    result: str
    evidence_version_id: UUID | None
    recorded_by: UUID
    recorded_at: datetime


def _binding(kind: str, row_id: UUID) -> str:
    return hashlib.sha256(f"{kind}:{row_id}".encode()).hexdigest()


def _person(name: str) -> str:
    """As contacts' generated `normalised_name` (0103's person rule: no suffixes dropped)."""
    return " ".join(_NON_ALNUM.sub(" ", name.lower()).split())


def _live_human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person's own act, never an agent, the platform, a client or a support session."""
    if ctx.client or ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


# --- the search ---------------------------------------------------------------------------------

_NAMED = text(
    """
    SELECT w.idx - 1 AS idx, 'client' AS ref_type, c.id AS ref_id, c.id AS client_id,
           similarity(c.normalised_name, w.name) AS score
      FROM unnest(CAST(:names AS text[])) WITH ORDINALITY AS w(name, idx)
      JOIN clients c ON c.normalised_name % w.name OR c.normalised_name = w.name
     WHERE w.name <> ''
    UNION ALL
    SELECT w.idx - 1, 'client_entity', e.id, e.client_id, similarity(e.normalised_name, w.name)
      FROM unnest(CAST(:names AS text[])) WITH ORDINALITY AS w(name, idx)
      JOIN client_entities e ON e.normalised_name % w.name OR e.normalised_name = w.name
     WHERE w.name <> ''
    """
)
_CONTACTS = text(
    """
    SELECT w.idx - 1 AS idx, c.id AS ref_id, c.client_id,
           similarity(c.normalised_name, w.name) AS score,
           (SELECT min(r.role) FROM contact_roles r
             WHERE r.contact_id = c.id AND r.role = ANY(:roles)) AS counterparty_role
      FROM unnest(CAST(:names AS text[])) WITH ORDINALITY AS w(name, idx)
      JOIN contacts c ON c.normalised_name % w.name OR c.normalised_name = w.name
     WHERE w.name <> ''
    """
)
_RELATED = text(
    """
    SELECT mine.id AS mine_id, other.id AS ref_id, other.client_id
      FROM entity_relationships r
      JOIN client_entities mine ON mine.id = r.from_entity_id OR mine.id = r.to_entity_id
      JOIN client_entities other
        ON other.id = CASE WHEN mine.id = r.from_entity_id THEN r.to_entity_id
                           ELSE r.from_entity_id END
     WHERE mine.id = ANY(:entities)
       AND other.client_id <> mine.client_id
       AND (r.effective_to IS NULL OR r.effective_to >= current_date)
    """
)
# The whole check's time budget (DEC-375, L3): three statements share it, each given what is
# left; past it, the check is refused (503) rather than answered half-searched.
SEARCH_BUDGET_MS: Final = 2000


class SearchTimedOut(ServiceUnavailable):
    """The conflict search did not finish inside its budget; run the check again."""


async def _bounded(
    session: AsyncSession, started: float, statement: TextClause, params: dict[str, object]
) -> list[RowMapping]:
    left = SEARCH_BUDGET_MS - int((time.monotonic() - started) * 1000)
    if left <= 0:
        raise SearchTimedOut
    await session.execute(
        text("SELECT set_config('statement_timeout', :ms, true)"), {"ms": f"{left}ms"}
    )
    try:
        return list((await session.execute(statement, params)).mappings().all())
    except DBAPIError as exc:
        if isinstance(exc.orig, asyncpg.QueryCanceledError) or "canceling statement" in str(
            exc.orig
        ):
            raise SearchTimedOut from None
        raise


def _score(raw: object) -> tuple[bool, float] | None:
    score = float(cast(float, raw)) if raw is not None else 0.0
    exact = score >= 1.0
    if not exact and score < TRIGRAM_FLOOR:
        return None
    return exact, 1.0 if exact else round(score, 4)


async def _search(session: AsyncSession, names: Sequence[str]) -> list[Hit]:
    """Three bounded statements for every name at once (not three per name)."""
    started = time.monotonic()
    await session.execute(text("SET LOCAL pg_trgm.similarity_threshold = 0.6"))  # TRIGRAM_FLOOR
    best: dict[tuple[UUID, str], Hit] = {}

    def keep(hit: Hit) -> None:
        key = (hit.client_id, hit.kind)
        current = best.get(key)
        if current is None or hit.score > current.score:
            best[key] = hit

    entity_name: dict[UUID, int] = {}
    named = [normalise(n) for n in names]
    for r in await _bounded(session, started, _NAMED, {"names": named}):
        scored = _score(r["score"])
        if scored is None:
            continue
        index = int(r["idx"])
        if r["ref_type"] == "client_entity":
            entity_name.setdefault(cast(UUID, r["ref_id"]), index)
        keep(
            Hit(
                index,
                cast(Literal["client", "client_entity"], r["ref_type"]),
                cast(UUID, r["ref_id"]),
                cast(UUID, r["client_id"]),
                "exact" if scored[0] else "trigram",
                scored[1],
            )
        )
    people = [_person(n) for n in names]
    contacts = await _bounded(
        session, started, _CONTACTS, {"names": people, "roles": list(COUNTERPARTY_ROLES)}
    )
    for r in contacts:
        scored = _score(r["score"])
        if scored is None:
            continue
        role = cast(str | None, r["counterparty_role"])
        kind: MatchKind = (
            "counterparty" if role is not None else ("exact" if scored[0] else "trigram")
        )
        keep(
            Hit(
                int(r["idx"]),
                "contact",
                cast(UUID, r["ref_id"]),
                cast(UUID, r["client_id"]),
                kind,
                scored[1],
                role,
            )
        )
    if entity_name:
        related = await _bounded(session, started, _RELATED, {"entities": list(entity_name)})
        for r in related:
            keep(
                Hit(
                    entity_name[cast(UUID, r["mine_id"])],
                    "client_entity",
                    cast(UUID, r["ref_id"]),
                    cast(UUID, r["client_id"]),
                    "relationship",
                    1.0,
                )
            )
    return sorted(best.values(), key=lambda h: (h.name_index, h.kind, str(h.client_id)))


# --- subjects -----------------------------------------------------------------------------------


async def _subject_client(tenant: TenantContext, kind: str, subject_id: UUID) -> UUID | None:
    """The client a client or client-entity subject names (404 when unknown); drafts are
    engagements' (and P-07-T42's) references, which organisations does not read."""
    if kind not in ("client", "client_entity"):
        return None
    query = (
        "SELECT id FROM clients WHERE id = :id"
        if kind == "client"
        else "SELECT client_id FROM client_entities WHERE id = :id"
    )
    async with tenant_session(tenant) as session:
        found = (await session.execute(text(query), {"id": subject_id})).scalar_one_or_none()
    if found is None:
        raise NotFound(kind)
    return cast(UUID, found)


async def _visible_subject(ctx: AuthContext, kind: str, subject_id: UUID) -> None:
    """A client or client entity the caller is not walled from; a draft its owner module says
    the caller may see (DEC-375, L4: unregistered kinds fail closed)."""
    if kind not in ("client", "client_entity"):
        if not await subject_visible(ctx, kind, subject_id):
            raise NotFound(kind)
        return
    client = await _subject_client(ctx.tenant, kind, subject_id)
    if client is not None and await hidden_clients(ctx.tenant, ctx.user_id, [client]):
        raise NotFound(kind)


# --- reads --------------------------------------------------------------------------------------


async def _names(
    session: AsyncSession, refs: Sequence[tuple[str, UUID]]
) -> dict[tuple[str, UUID], str]:
    queries = {
        "client": "SELECT id, name FROM clients WHERE id = ANY(:ids)",
        "client_entity": "SELECT id, name FROM client_entities WHERE id = ANY(:ids)",
        "contact": "SELECT id, display_name AS name FROM contacts WHERE id = ANY(:ids)",
    }
    out: dict[tuple[str, UUID], str] = {}
    for ref_type, query in queries.items():
        ids = [i for t, i in refs if t == ref_type]
        if not ids:
            continue
        for r in (await session.execute(text(query), {"ids": ids})).mappings():
            out[(ref_type, cast(UUID, r["id"]))] = cast(str, r["name"])
    return out


async def _view(ctx: AuthContext, session: AsyncSession, check: RowMapping) -> CheckView:
    rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT r.*, e.assessment AS latest, e.cleared_by, e.cleared_at
                      FROM conflict_results r
                      LEFT JOIN LATERAL (
                          SELECT assessment, cleared_by, cleared_at FROM conflict_result_events
                           WHERE result_id = r.id ORDER BY cleared_at DESC, id DESC LIMIT 1
                      ) e ON true
                     WHERE r.check_id = :check
                     ORDER BY r.name_index, r.match_kind, r.id
                    """
                ),
                {"check": check["id"]},
            )
        )
        .mappings()
        .all()
    )
    walled = await walled_from(ctx.tenant, ctx.user_id)
    visible = [r for r in rows if r["matched_client_id"] not in walled]
    names = await _names(
        session,
        [(cast(str, r["matched_ref_type"]), cast(UUID, r["matched_ref_id"])) for r in visible],
    )
    may_clear = CLEAR in await allowed_actions(ctx, Resource.firm(ctx.tenant_id), [CLEAR])
    results: list[ResultView] = []
    for r in rows:
        default = "counterparty_review" if r["match_kind"] == "counterparty" else "pending"
        assessment = cast(str, r["latest"] or default)
        if r["matched_client_id"] in walled:
            continue  # collapsed into the one restricted row below (DEC-375, M2)
        results.append(
            ResultView(
                id=r["id"],
                redacted=False,
                match_kind=r["match_kind"],
                assessment=assessment,
                matched_client_id=r["matched_client_id"],
                matched_name=names.get((r["matched_ref_type"], r["matched_ref_id"])),
                matched_ref_type=r["matched_ref_type"],
                matched_ref_id=r["matched_ref_id"],
                score=float(cast(Decimal, r["score"])),
                cleared_by=r["cleared_by"],
                cleared_at=r["cleared_at"],
                allowed_actions=[CLEAR] if may_clear else [],
            )
        )
    # Outcome over the matches this reader may see; walled ones are only the flag and one row.
    standing = any(r.assessment in _STANDING for r in results)
    restricted = len(visible) < len(rows)
    if restricted:
        results.append(
            ResultView(
                id=cast(UUID, next(r["id"] for r in rows if r["matched_client_id"] in walled)),
                redacted=True,
                match_kind=RESTRICTED_KIND,
                assessment="pending",
            )
        )
    return CheckView(
        id=check["id"],
        subject=SubjectRef(check["subject_kind"], check["subject_id"]),
        names_count=check["names_count"],
        # DEC-375 note (re-review 2): never `clear` while a restricted match stands.
        outcome="hits" if standing or restricted else "clear",
        restricted_match=restricted,
        run_by=check["run_by"],
        run_at=check["run_at"],
        results=results,
    )


async def conflict_check(ctx: AuthContext, check_id: UUID) -> CheckView:
    """A check and its results, redacted for this reader."""
    _live_human(ctx, RUN)
    await authorise(ctx, RUN, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        check = (
            (
                await session.execute(
                    text("SELECT * FROM conflict_checks WHERE id = :id"), {"id": check_id}
                )
            )
            .mappings()
            .one_or_none()
        )
        if check is None:
            raise NotFound("conflict_check")
        await _visible_subject(ctx, check["subject_kind"], check["subject_id"])
        return await _view(ctx, session, check)


# --- writes -------------------------------------------------------------------------------------


async def run_conflict_check(
    ctx: AuthContext, *, subject_kind: SubjectKind, subject_id: UUID, names: Sequence[str]
) -> CheckView:
    """AC-23: run, store (names sealed) and answer the check, redacted for the caller."""
    _live_human(ctx, RUN)
    await authorise(ctx, RUN, Resource.firm(ctx.tenant_id))
    await _visible_subject(ctx, subject_kind, subject_id)
    system = TenantContext(ctx.tenant_id, "system", "conflict-search")
    async with tenant_session(system) as session:
        hits = await _search(session, names)
    check_id = uuid4()
    async with uow(ctx.tenant) as tx:
        sealed = await seal(
            ctx.tenant_id, json.dumps(list(names)).encode(), _binding("conflict_check", check_id)
        )
        await tx.session.execute(
            text(
                "INSERT INTO conflict_checks (id, tenant_id, subject_kind, subject_id, "
                "names_sealed, names_count, status, run_by) VALUES (:id, :tenant, :kind, "
                ":subject, :sealed, :count, :status, :by)"
            ),
            {
                "id": check_id,
                "tenant": ctx.tenant_id,
                "kind": subject_kind,
                "subject": subject_id,
                "sealed": sealed,
                "count": len(names),
                "status": "hits" if hits else "clear",
                "by": ctx.user_id,
            },
        )
        for hit in hits:
            await tx.session.execute(
                text(
                    "INSERT INTO conflict_results (tenant_id, check_id, name_index, "
                    "matched_ref_type, matched_ref_id, matched_client_id, match_kind, score, "
                    "counterparty_role) VALUES (:tenant, :check, :index, :ref_type, :ref_id, "
                    ":client, :kind, :score, :role)"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "check": check_id,
                    "index": hit.name_index,
                    "ref_type": hit.ref_type,
                    "ref_id": hit.ref_id,
                    "client": hit.client_id,
                    "kind": hit.kind,
                    "score": Decimal(str(hit.score)),
                    "role": hit.counterparty_role,
                },
            )
        tx.record(
            "conflict_check.run",
            target=Target(_AUDIT_TARGET[subject_kind], subject_id),
            # DEC-375 (L4): no count of matches, which would include walled ones.
            after=Ref(check_id=check_id, names=len(names)),
        )
    return await conflict_check(ctx, check_id)


async def clear_conflict_result(
    ctx: AuthContext, check_id: UUID, result_id: UUID, *, assessment: str, reason: str
) -> ResultView:
    """AC-25: a partner's or manager's assessment with a reason (human-only; insert-only event);
    a result on a client the caller is walled from answers 404 like an unknown one."""
    _live_human(ctx, CLEAR)
    await authorise(ctx, CLEAR, Resource.firm(ctx.tenant_id))
    reason = reason.strip()
    async with uow(ctx.tenant) as tx:
        found = (
            (
                await tx.session.execute(
                    text(
                        "SELECT r.matched_client_id, c.subject_kind, c.subject_id "
                        "FROM conflict_results r JOIN conflict_checks c ON c.id = r.check_id "
                        "WHERE r.id = :result AND r.check_id = :check"
                    ),
                    {"result": result_id, "check": check_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if found is None or await hidden_clients(
            ctx.tenant, ctx.user_id, [cast(UUID, found["matched_client_id"])]
        ):
            raise NotFound("conflict_result")
        await _visible_subject(ctx, found["subject_kind"], found["subject_id"])
        event_id = uuid4()
        await tx.session.execute(
            text(
                "INSERT INTO conflict_result_events (id, tenant_id, result_id, assessment, "
                "reason_sealed, cleared_by) VALUES (:id, :tenant, :result, :assessment, "
                ":sealed, :by)"
            ),
            {
                "id": event_id,
                "tenant": ctx.tenant_id,
                "result": result_id,
                "assessment": assessment,
                "sealed": await seal(
                    ctx.tenant_id, reason.encode(), _binding("conflict_result_event", event_id)
                ),
                "by": ctx.user_id,
            },
        )
        tx.record(
            "conflict.cleared",
            target=Target(_AUDIT_TARGET[found["subject_kind"]], found["subject_id"]),
            after=Ref(check_id=check_id, result_id=result_id),
        )
    view = await conflict_check(ctx, check_id)
    return next(r for r in view.results if r.id == result_id)


async def record_screening(
    ctx: AuthContext,
    *,
    subject_kind: SubjectKind,
    subject_id: UUID,
    screening_list: str,
    result: str,
    evidence_version_id: UUID | None,
    note: str | None,
) -> ScreeningView:
    """AC-26: a person records what a list they checked said; nothing is looked up."""
    _live_human(ctx, RECORD)
    await authorise(ctx, RECORD, Resource.firm(ctx.tenant_id))
    await _visible_subject(ctx, subject_kind, subject_id)
    if evidence_version_id is not None and not await evidence_visible(ctx, evidence_version_id):
        raise NotFound("evidence_version")  # DEC-375 (L4): a file the person may read
    record_id = uuid4()
    async with uow(ctx.tenant) as tx:
        sealed = (
            await seal(
                ctx.tenant_id, note.strip().encode(), _binding("screening_record", record_id)
            )
            if note and note.strip()
            else None
        )
        row = (
            (
                await tx.session.execute(
                    text(
                        "INSERT INTO screening_records (id, tenant_id, subject_kind, subject_id, "
                        "list, result, evidence_version_id, note_sealed, recorded_by) VALUES "
                        "(:id, :tenant, :kind, :subject, :list, :result, :evidence, :sealed, "
                        ":by) RETURNING recorded_at"
                    ),
                    {
                        "id": record_id,
                        "tenant": ctx.tenant_id,
                        "kind": subject_kind,
                        "subject": subject_id,
                        "list": screening_list,
                        "result": result,
                        "evidence": evidence_version_id,
                        "sealed": sealed,
                        "by": ctx.user_id,
                    },
                )
            )
            .mappings()
            .one()
        )
        tx.record(
            "screening.recorded",
            target=Target(_AUDIT_TARGET[subject_kind], subject_id),
            after=Ref(record_id=record_id),
        )
    return ScreeningView(
        id=record_id,
        subject=SubjectRef(subject_kind, subject_id),
        screening_list=screening_list,
        result=result,
        evidence_version_id=evidence_version_id,
        recorded_by=ctx.user_id,
        recorded_at=cast(datetime, row["recorded_at"]),
    )


# --- the independence conclusion's precondition (P-07-T41; SPEC-332 AC-19) ----------------------

_STANDING_FOR_CLIENT = text(
    """
    SELECT r.id
      FROM conflict_results r
      JOIN conflict_checks c ON c.id = r.check_id
      LEFT JOIN LATERAL (
          SELECT assessment FROM conflict_result_events
           WHERE result_id = r.id ORDER BY cleared_at DESC, id DESC LIMIT 1
      ) e ON true
     WHERE (
            (c.subject_kind = 'client' AND c.subject_id = :client)
         OR (c.subject_kind = 'client_entity'
             AND c.subject_id IN (SELECT id FROM client_entities WHERE client_id = :client))
         OR c.id = ANY(CAST(:checks AS uuid[]))
           )
       AND r.matched_client_id <> :client
       AND COALESCE(
               e.assessment,
               CASE WHEN r.match_kind = 'counterparty' THEN 'counterparty_review'
                    ELSE 'pending' END
           ) IN ('pending', 'counterparty_review', 'conflict')
     ORDER BY r.id
    """
)


async def standing_conflict_results(
    tenant: TenantContext, client_id: UUID, check_ids: Sequence[UUID] = ()
) -> list[UUID]:
    """The conflict results still standing (pending, counterparty review or conflict) on the
    checks run for the client or its entities, and on any checks named (an intake's, linked to
    the engagement), leaving out matches on the client itself. Identifiers only, for a caller
    that authorised reading the client's engagement; walls do not narrow it, since the answer
    is a precondition, never a list a person reads (DEC-428)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            _STANDING_FOR_CLIENT, {"client": client_id, "checks": list(check_ids)}
        )
        return [cast(UUID, r) for r in rows.scalars().all()]
