"""C19 condition 6, the read half: whether §7216 consents are in force (T-01-T11; T-01 §3.2;
ADR-167; ADR P-12). PROTECTED-adjacent: the gateway and the matrix both rely on it.

A consent is in force at `at` when its row is `signed` (signed at or before `at`), not revoked,
not expired (`expires_at` after `at`, or none), every required signer has signed (both spouses
on a joint filing unit), it covers the tax year asked about, and it was signed under the
provider terms in force now (`provider_terms_version` equals the covering Bedrock entry's
`material` hash; a material change means re-consent, chapter 05 §5.4.2 item 8; while no entry
covers Bedrock no real route may carry client data, so the comparison waits for one). Nothing is
cached: every check reads the rows, so a revocation binds the next call. Time is business time
(`kernel.clock.now`): a synthetic tenant's demo clock moves its consents' expiry too; production
never has one.

- `consent_state`, `tri_consent_verdict`: the C19 module API (fail closed: an unknown subject is
  missing both purposes).
- `consent_given` providers for `use` and `ai_disclosure` (`register_consent_check`), which the
  matrix's `consent(<purpose>)` condition reads.
- `covering_consents`, which engagements registers with the AI gateway
  (`register_tri_consent_check`; organisations never imports the gateway, P-07-T04).
- `require_tri_consent`: the tool-layer refusal (409 `consent_required`, naming the client
  entity), writing one `tri.tool_read` access event per subject and covering consent when it
  allows.

T-01-T10 builds capture (request, sign, record, renew); this module only reads.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Final, NamedTuple
from uuid import UUID

from sqlalchemy import ColumnElement, and_, column, func, literal, or_, select, table, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from abacus.kernel import provider_terms
from abacus.kernel.clock import now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow.access import AccessSubject, record_reads, register_access_kind
from abacus.modules.identity.api import (
    OFFSHORE_DISCLOSURE,
    register_consent_check,
)
from abacus.modules.organisations.consents_contract import ConsentState, TriVerdict

TRI_PURPOSES: Final = ("use", "ai_disclosure")


class TriSubject(NamedTuple):
    """A taxpayer whose return information is read: the client entity and the return's year.
    `entity_id` None is a TRI field whose subject could not be resolved (refused)."""

    entity_id: UUID | None
    tax_year: int | None


_ROUTE: Final = "bedrock"  # the only route that may carry client data (ADR-113)

register_access_kind("tri.tool_read", ["tri"])

# One indexed query (`consents_in_force`): signed, unrevoked, unexpired, every required signer
# signed, the year covered (or any year when none is asked), the current material terms.
_IN_FORCE = text(
    """
    SELECT c.id, c.client_entity_id, c.purpose, c.status, c.expires_at
      FROM consents c
     WHERE c.client_entity_id = ANY(:entities)
       AND c.purpose = ANY(:purposes)
       AND c.status = 'signed'
       AND c.signed_at <= :at
       AND c.revoked_at IS NULL
       AND (c.expires_at IS NULL OR c.expires_at > :at)
       AND (CAST(:year AS integer) IS NULL OR CAST(:year AS integer) = ANY(c.tax_years))
       AND (CAST(:terms AS text) IS NULL OR c.provider_terms_version = :terms)
       AND NOT EXISTS (
           SELECT 1 FROM consent_signers s
            WHERE s.tenant_id = c.tenant_id AND s.consent_id = c.id
              AND s.required AND s.signed_at IS NULL
       )
     ORDER BY c.client_entity_id, c.purpose, c.signed_at DESC
    """
)


class TriConsentRequired(DomainConflict):
    """A read of tax return information without the taxpayer's `use` and `ai_disclosure`
    consents in force (`facts.client_entity_id`, `facts.purpose`)."""

    code = "consent_required"


def _terms(at: datetime) -> str | None:
    """The material-terms hash a consent must have been signed under, or None while no entry
    covers Bedrock (then no real route may carry client data at all: the boundary refuses
    `terms`, and only the `fake` route and synthetic firms run, where the check is moot)."""
    covering = provider_terms.covering(_ROUTE, at.date())
    return None if covering is None or not covering.material else covering.material


async def _in_force(
    tenant: TenantContext,
    entities: Sequence[UUID],
    purposes: Sequence[str],
    at: datetime,
    tax_year: int | None,
) -> dict[tuple[UUID, str], UUID]:
    """(entity, purpose) -> the newest consent in force for it."""
    terms = _terms(at)
    if not entities:
        return {}
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                _IN_FORCE,
                {
                    "entities": list(entities),
                    "purposes": list(purposes),
                    "at": at,
                    "year": tax_year,
                    "terms": terms,
                },
            )
        ).all()
    found: dict[tuple[UUID, str], UUID] = {}
    for row in rows:
        found.setdefault((row.client_entity_id, row.purpose), row.id)
    return found


async def consent_state(
    tenant: TenantContext, entity_ids: list[UUID], purpose: str, tax_year: int
) -> list[ConsentState]:
    """The consent in force for each entity, purpose and year, or a `missing` row."""
    at = await now(tenant)
    found = await _in_force(tenant, entity_ids, [purpose], at, tax_year)
    return [
        ConsentState(
            client_entity_id=entity,
            purpose=purpose,
            tax_year=tax_year,
            status="signed" if (entity, purpose) in found else "missing",
            consent_id=found.get((entity, purpose)),
            expires_at=None,
        )
        for entity in entity_ids
    ]


async def tri_consent_verdict(
    tenant: TenantContext, subjects: list[UUID], at: datetime, *, tax_year: int | None = None
) -> TriVerdict:
    """Condition 6: valid only when every subject holds `use` and `ai_disclosure` in force at
    `at` (for `tax_year` when given). Fail closed: an unknown subject is missing both."""
    found = await _in_force(tenant, subjects, TRI_PURPOSES, at, tax_year)
    missing = tuple(
        (subject, purpose)
        for subject in subjects
        for purpose in TRI_PURPOSES
        if (subject, purpose) not in found
    )
    return TriVerdict(valid=bool(subjects) and not missing, missing=missing)


async def covering_consents(
    tenant: TenantContext, subjects: Sequence[TriSubject], at: datetime
) -> tuple[UUID, ...] | None:
    """The consent ids covering every subject for its own year, or None if any is missing."""
    ids: list[UUID] = []
    years = sorted({s.tax_year for s in subjects if s.tax_year is not None})
    for year in years:
        entities = sorted({s.entity_id for s in subjects if s.tax_year == year and s.entity_id})
        found = await _in_force(tenant, entities, TRI_PURPOSES, at, year)
        for entity in entities:
            for purpose in TRI_PURPOSES:
                consent = found.get((entity, purpose))
                if consent is None:
                    return None
                ids.append(consent)
    if not ids or any(s.entity_id is None or s.tax_year is None for s in subjects):
        return None
    return tuple(dict.fromkeys(ids))


async def require_tri_consent(
    tenant: TenantContext,
    subjects: Sequence[TriSubject],
    *,
    run_id: UUID | None = None,
    engagement_id: UUID | None = None,
) -> tuple[UUID, ...]:
    """The tool-layer refusal (ADR-167): raise `consent_required` naming the first subject
    without both consents; otherwise record the read, per subject and covering consent."""
    at = await now(tenant)
    for subject in subjects:
        if subject.entity_id is None or subject.tax_year is None:
            raise TriConsentRequired(facts={"purpose": "use"})
        found = await _in_force(tenant, [subject.entity_id], TRI_PURPOSES, at, subject.tax_year)
        for purpose in TRI_PURPOSES:
            if (subject.entity_id, purpose) not in found:
                raise TriConsentRequired(
                    facts={"client_entity_id": str(subject.entity_id), "purpose": purpose}
                )
    covering = await covering_consents(tenant, subjects, at)
    if covering is None:
        raise TriConsentRequired(facts={"purpose": "use"})
    await record_reads(
        tenant,
        "tri.tool_read",
        [
            *(
                AccessSubject(
                    "client_entity",
                    s.entity_id,
                    engagement_id=engagement_id,
                    tax_year=s.tax_year,
                )
                for s in subjects
                if s.entity_id is not None
            ),
            *(AccessSubject("consent", c, engagement_id=engagement_id) for c in covering),
        ],
        run_id=run_id,
    )
    return covering


async def _given(tenant: TenantContext, entity_id: UUID, purpose: str, at: datetime) -> bool:
    """`consent_given` for the matrix's `consent(<purpose>)`: in force now, any year."""
    return (entity_id, purpose) in await _in_force(tenant, [entity_id], [purpose], at, None)


# --- offshore disclosure (T-01-T12; G-01-T09's slot; DEC-52) -------------------------------------
#
# A client is covered when it has at least one taxpayer entity and every one of them holds an
# `offshore_disclosure` consent in force (signed by every required signer, unrevoked, unexpired).
# The check, the SQL predicate (ADM-03d's filter) and the count read the same rule.

_entities = table("client_entities", column("id"), column("client_id"))
_offshore = table(
    "consents",
    column("id"),
    column("tenant_id"),
    column("client_entity_id"),
    column("purpose"),
    column("status"),
    column("revoked_at"),
    column("expires_at"),
)
_signers = table(
    "consent_signers",
    column("tenant_id"),
    column("consent_id"),
    column("required"),
    column("signed_at"),
)


def _entity_covered(entity_id: ColumnElement[UUID], purpose: str) -> ColumnElement[bool]:
    unsigned = (
        select(literal(1))
        .where(
            _signers.c.tenant_id == _offshore.c.tenant_id,
            _signers.c.consent_id == _offshore.c.id,
            _signers.c.required.is_(True),
            _signers.c.signed_at.is_(None),
        )
        .exists()
    )
    return (
        select(literal(1))
        .where(
            _offshore.c.client_entity_id == entity_id,
            _offshore.c.purpose == purpose,
            _offshore.c.status == "signed",
            _offshore.c.revoked_at.is_(None),
            or_(_offshore.c.expires_at.is_(None), _offshore.c.expires_at > func.abacus_now()),
            ~unsigned,
        )
        .exists()
    )


def offshore_column(client_id: ColumnElement[UUID], purpose: str) -> ColumnElement[bool]:
    """The client-id column is covered: it has an entity, and none lacks the consent."""
    entity = _entities.alias("covered_entity")
    has_entity = select(literal(1)).where(entity.c.client_id == client_id).exists()
    uncovered = (
        select(literal(1))
        .where(entity.c.client_id == client_id, ~_entity_covered(entity.c.id, purpose))
        .exists()
    )
    return and_(has_entity, ~uncovered)


async def _offshore_given(
    tenant: TenantContext, client_id: UUID, purpose: str, _at: datetime
) -> bool:
    """`consent_given` for `offshore_disclosure`, keyed by client (as G-01 asks)."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            select(offshore_column(literal(client_id, type_=PG_UUID(as_uuid=True)), purpose))
        )
    return bool(found)


async def _offshore_count(tenant: TenantContext, purpose: str) -> int:
    clients = table("clients", column("id"))
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            select(func.count()).select_from(clients).where(offshore_column(clients.c.id, purpose))
        )
    return int(found or 0)


def register_consent_gate() -> None:
    """Once, from `organisations.api`: the two TRI purposes' checks, and the offshore
    disclosure's check, predicate and count (T-01-T12). Organisations never imports the gateway
    (P-07-T04): engagements registers `covering_consents` with it."""
    for purpose in TRI_PURPOSES:
        register_consent_check(purpose, _given)
    register_consent_check(OFFSHORE_DISCLOSURE, _offshore_given, offshore_column, _offshore_count)


__all__ = [
    "TRI_PURPOSES",
    "TriConsentRequired",
    "TriSubject",
    "consent_state",
    "covering_consents",
    "offshore_column",
    "register_consent_gate",
    "require_tri_consent",
    "tri_consent_verdict",
]


_COUNTS = text(
    "SELECT y.client_id, y.tax_year, count(c.id) FILTER (WHERE c.status = 'signed' "
    "AND (c.expires_at IS NULL OR c.expires_at > :at)) AS signed, count(c.id) AS total "
    "FROM unnest(CAST(:clients AS uuid[]), CAST(:years AS integer[])) AS y(client_id, tax_year) "
    "JOIN consents c ON c.client_id = y.client_id AND y.tax_year = ANY(c.tax_years) "
    "AND c.status IN ('requested', 'signed', 'expired') GROUP BY y.client_id, y.tax_year"
)


async def consent_counts(
    tenant: TenantContext, pairs: Sequence[tuple[UUID, int]]
) -> dict[tuple[UUID, int], tuple[int, int]]:
    """CLI-05 / BND-01 (T-01-T14 follow-up, DEC-1288): per (client, tax year), the §7216
    consents in force and the consents asked for (requested, signed or lapsed; a declined,
    revoked or superseded one is not counted). Identifiers and counts only."""
    if not pairs:
        return {}
    at = await now(tenant)
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                _COUNTS,
                {
                    "clients": [p[0] for p in pairs],
                    "years": [p[1] for p in pairs],
                    "at": at,
                },
            )
        ).all()
    return {(r.client_id, int(r.tax_year)): (int(r.signed), int(r.total)) for r in rows}
