"""Season setup: the manifest built and kept (T-08-T09; S51 partials, TASK-8737; DEC-5729;
SPEC-710 AC-1 to AC-3, AC-7; ENG-07). Dark behind `engagements.season_setup`.

- **Candidates** come from a registered source (tax registers the continuing tax clients from the
  prior year's returns; engagements never imports tax). With no source the build is refused
  (409 `no_candidate_source`), never an empty season.
- **Build** opens the season once, then writes a manifest version: cohorts by office and segment
  (`season_manifest.build`, code) and one row per client with its forms, carried people, binder
  source, letter plan, consents, invitees and the exception codes the rules give. The previous
  ready version is superseded; a rebuild is refused once a cohort is approved (409
  `cohort_approved`). Tallies and displays are computed on read, never stored.
- **Read**: the manifest's tally, offices and cohorts, and a cohort's rows, all without the rows
  of a client the reader is walled from (no row, no count; AC-7).
- **Reassign** a preparer, reviewer or signer to an active member not walled from the client, and
  **exclude** rows with a reason; both at the row version seen (If-Match) and only while the
  cohort is a draft (409 `cohort_approved`, the trigger behind it).
- **Export** the manifest as a workbook (injection-safe, deterministic).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.safe_xlsx import Sheet, workbook
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements import season_manifest as calc
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise,
    is_active_member,
    names_of,
    walled_from,
)
from abacus.modules.organisations.api import firm_names, firm_offices

Segment = Literal["individuals_trusts", "entities_exempt"]
SEGMENTS: Final[tuple[Segment, ...]] = ("individuals_trusts", "entities_exempt")
LetterKind = Literal["renewal", "new", "none"]


class NoCandidateSource(DomainConflict):
    code = "no_candidate_source"


class CohortApproved(DomainConflict):
    code = "cohort_approved"


class StaleRow(DomainConflict):
    code = "stale_version"


class AssigneeNotEligible(DomainConflict):
    code = "assignee_not_eligible"


@dataclass(frozen=True)
class SeasonCandidate:
    """One continuing client for the season, as its source states it."""

    client_id: UUID
    office_id: UUID
    segment: Segment
    forms: tuple[str, ...]
    client_entity_ids: tuple[UUID, ...] = ()
    preparer_user_id: UUID | None = None
    reviewer_user_id: UUID | None = None
    signer_user_id: UUID | None = None
    prior_engagement_id: UUID | None = None
    binders: int = 1
    binder_requests: int = 0
    letter_kind: LetterKind = "renewal"
    fee_change_pct: Decimal | None = None
    consent_purposes: tuple[str, ...] = ()
    invitee_contact_ids: tuple[UUID, ...] = ()
    flags: frozenset[str] = field(default_factory=frozenset[str])
    prospect: bool = False


CandidateSource = Callable[[TenantContext, int], Awaitable[list[SeasonCandidate]]]
_sources: list[CandidateSource] = []


def register_season_candidates(source: CandidateSource) -> None:
    """The module that owns the prior year's returns states the season's candidates (tax)."""
    _sources[:] = [source]


def _canonical(c: SeasonCandidate) -> dict[str, object]:
    raw = asdict(c)
    raw["flags"] = sorted(c.flags)
    return {k: (str(v) if isinstance(v, (UUID, Decimal)) else v) for k, v in raw.items()}


def inputs_hash(candidates: Sequence[SeasonCandidate]) -> str:
    body = json.dumps(
        sorted((_canonical(c) for c in candidates), key=lambda d: str(d["client_id"])),
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(body.encode()).hexdigest()


async def _firm(ctx: AuthContext, action: str) -> None:
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))


_SEASON_ID = text("SELECT id FROM seasons WHERE tax_year = :y")
_OPEN_SEASON = text(
    "INSERT INTO seasons (tenant_id, tax_year, opened_by) VALUES (:t, :y, :u) "
    "ON CONFLICT (tenant_id, tax_year) DO NOTHING RETURNING id"
)
_READY = text("SELECT id, version FROM season_manifests WHERE season_id = :s AND status = 'ready'")
_NEXT_VERSION = text(
    "SELECT coalesce(max(version), 0) + 1 FROM season_manifests WHERE season_id = :s"
)
_APPROVED = text(
    "SELECT EXISTS (SELECT 1 FROM season_cohorts c JOIN season_manifests m "
    "ON m.id = c.manifest_id WHERE m.season_id = :s AND m.status = 'ready' "
    "AND c.status <> 'draft')"
)
_SUPERSEDE = text("UPDATE season_manifests SET status = 'superseded' WHERE id = :m")
_NEW_MANIFEST = text(
    "INSERT INTO season_manifests (tenant_id, season_id, version, status, inputs_hash, built_by) "
    "VALUES (:t, :s, :v, 'building', :h, :u) RETURNING id"
)
_NEW_COHORT = text(
    "INSERT INTO season_cohorts (tenant_id, manifest_id, position, office_id, segment) "
    "VALUES (:t, :m, :p, :o, :seg) RETURNING id"
)
_NEW_ROW = text(
    "INSERT INTO season_manifest_rows (tenant_id, cohort_id, client_id, client_entity_ids, forms, "
    "preparer_user_id, reviewer_user_id, signer_user_id, prior_engagement_id, binder_source, "
    "letter_plan, consent_purposes, invitee_contact_ids, exception_codes) VALUES (:t, :c, "
    ":client, :entities, :forms, :prep, :rev, :sign, :prior, CAST(:binder AS jsonb), "
    "CAST(:letter AS jsonb), :consents, :invitees, :codes)"
)
_MARK_READY = text("UPDATE season_manifests SET status = 'ready' WHERE id = :m")


async def build_manifest(ctx: AuthContext, tax_year: int, *, rebuild: bool = False) -> UUID:
    """The season's ready manifest: the current one unless `rebuild`, else a new version."""
    await _firm(ctx, "season_setup.prepare")
    if not _sources:
        raise NoCandidateSource(facts={"tax_year": str(tax_year)})
    candidates = [c for c in await _sources[0](ctx.tenant, tax_year) if not c.prospect]
    digest = inputs_hash(candidates)
    async with tenant_session(ctx.tenant) as session:
        known = await session.scalar(_SEASON_ID, {"y": tax_year})
        current = None if known is None else (await session.execute(_READY, {"s": known})).first()
    if current is not None and not rebuild:
        return cast(UUID, current[0])  # the ready manifest; nothing is written
    async with uow(ctx.tenant) as tx:
        await tx.session.scalar(
            _OPEN_SEASON, {"t": ctx.tenant_id, "y": tax_year, "u": ctx.user_id}
        )
        season = cast(UUID, await tx.session.scalar(_SEASON_ID, {"y": tax_year}))
        ready = (await tx.session.execute(_READY, {"s": season})).first()
        if ready is not None and not rebuild:
            raise CohortApproved(facts={"tax_year": str(tax_year)})  # built meanwhile
        if ready is not None and await tx.session.scalar(_APPROVED, {"s": season}):
            raise CohortApproved(facts={"tax_year": str(tax_year)})
        if ready is not None:
            await tx.session.execute(_SUPERSEDE, {"m": ready[0]})
        version = int(cast(int, await tx.session.scalar(_NEXT_VERSION, {"s": season})))
        manifest = cast(
            UUID,
            await tx.session.scalar(
                _NEW_MANIFEST,
                {"t": ctx.tenant_id, "s": season, "v": version, "h": digest, "u": ctx.user_id},
            ),
        )
        by_client = {str(c.client_id): c for c in candidates}
        names = dict(await firm_offices(ctx.tenant))
        offices = sorted(
            dict.fromkeys(str(c.office_id) for c in candidates),
            key=lambda o: (names.get(UUID(o), ""), o),
        )  # cohorts by office name, then segment: a stable order
        order = [(o, s) for o in offices for s in SEGMENTS]
        cohorts = calc.build(
            [
                calc.Candidate(
                    str(c.client_id), str(c.office_id), c.segment, len(c.forms), c.binders,
                    None if c.preparer_user_id is None else str(c.preparer_user_id),
                    None if c.reviewer_user_id is None else str(c.reviewer_user_id),
                    c.flags,
                )
                for c in candidates
            ],
            order,
        )  # fmt: skip
        for position, cohort in enumerate(cohorts, start=1):
            cohort_id = await tx.session.scalar(
                _NEW_COHORT,
                {"t": ctx.tenant_id, "m": manifest, "p": position, "o": UUID(cohort.office),
                 "seg": cohort.segment},
            )  # fmt: skip
            for row in cohort.rows:
                c = by_client[row.candidate.client]
                await tx.session.execute(
                    _NEW_ROW,
                    {
                        "t": ctx.tenant_id, "c": cohort_id, "client": c.client_id,
                        "entities": list(c.client_entity_ids), "forms": list(c.forms),
                        "prep": c.preparer_user_id, "rev": c.reviewer_user_id,
                        "sign": c.signer_user_id, "prior": c.prior_engagement_id,
                        "binder": json.dumps(
                            {"binders": c.binders, "requests": c.binder_requests}
                        ),
                        "letter": json.dumps(
                            {"kind": c.letter_kind,
                             "fee_change_pct": None if c.fee_change_pct is None
                             else str(c.fee_change_pct)}
                        ),
                        "consents": list(c.consent_purposes),
                        "invitees": list(c.invitee_contact_ids),
                        "codes": list(row.exceptions),
                    },
                )  # fmt: skip
        await tx.session.execute(_MARK_READY, {"m": manifest})
        tx.record(
            "season_manifest.built",
            target=Target("season_manifest", manifest),
            after=Ref(version=version, rows=len(candidates)),
        )
    return manifest


# --- reads -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RowView:
    row_id: UUID
    cohort_id: UUID
    client_id: UUID
    client_name: str
    forms: tuple[str, ...]
    preparer_user_id: UUID | None
    reviewer_user_id: UUID | None
    signer_user_id: UUID | None
    binders: int
    requests: int
    letter_kind: str
    fee_change_pct: Decimal | None
    consent_purposes: tuple[str, ...]
    invitees: int
    exception_codes: tuple[str, ...]
    excluded: bool
    created: bool
    failed: bool
    row_version: int

    @property
    def display(self) -> str:
        if self.excluded:
            return "excluded"
        if self.failed:
            return "failed"
        if self.created:
            return "created"
        return "check" if self.exception_codes else "ready"


@dataclass(frozen=True)
class CohortView:
    cohort_id: UUID
    position: int
    office_id: UUID
    office_name: str
    segment: str
    status: str
    approver_user_id: UUID | None
    rows: tuple[RowView, ...]

    def _live(self) -> list[RowView]:
        return [r for r in self.rows if not r.excluded]

    @property
    def engagements(self) -> int:
        return len({r.client_id for r in self._live()})

    @property
    def returns(self) -> int:
        return sum(len(r.forms) for r in self._live())

    @property
    def binders(self) -> int:
        return sum(r.binders for r in self._live())

    @property
    def letters(self) -> int:
        return sum(1 for r in self._live() if r.letter_kind != "none")

    @property
    def invitations(self) -> int:
        return sum(r.invitees for r in self._live())

    @property
    def exceptions(self) -> int:
        return sum(1 for r in self._live() if r.exception_codes and not r.created)

    @property
    def created(self) -> int:
        return sum(1 for r in self._live() if r.created)

    @property
    def display(self) -> str:
        if self.status == "draft":
            return "review_required" if self.exceptions else "draft"
        return self.status

    @property
    def rows_hash(self) -> str:
        body = ",".join(
            f"{r.row_id}:{r.row_version}" for r in sorted(self.rows, key=lambda r: str(r.row_id))
        )
        return hashlib.sha256(body.encode()).hexdigest()


@dataclass(frozen=True)
class ManifestView:
    manifest_id: UUID
    season_id: UUID
    tax_year: int
    version: int
    status: str
    built_by: UUID
    built_at: datetime
    inputs_hash: str
    cohorts: tuple[CohortView, ...]


_MANIFEST = text(
    "SELECT m.id, m.season_id, s.tax_year, m.version, m.status, m.built_by, m.built_at, "
    "m.inputs_hash FROM season_manifests m JOIN seasons s ON s.id = m.season_id "
    "WHERE m.id = :m AND s.tax_year = :y"
)
_COHORTS = text(
    "SELECT id, position, office_id, segment, status, approver_user_id FROM season_cohorts "
    "WHERE manifest_id = :m ORDER BY position"
)
_ROWS = text(
    "SELECT r.id, r.cohort_id, r.client_id, '', r.forms, r.preparer_user_id, "
    "r.reviewer_user_id, r.signer_user_id, r.binder_source, r.letter_plan, r.consent_purposes, "
    "cardinality(r.invitee_contact_ids), r.exception_codes, r.excluded_at IS NOT NULL, "
    "EXISTS (SELECT 1 FROM season_row_steps st WHERE st.row_id = r.id "
    "AND st.step = 'engagement' AND st.status = 'ok'), "
    "EXISTS (SELECT 1 FROM season_row_steps st WHERE st.row_id = r.id AND st.status = 'failed' "
    "AND NOT EXISTS (SELECT 1 FROM season_row_steps ok WHERE ok.row_id = st.row_id "
    "AND ok.step = st.step AND ok.status = 'ok' AND ok.attempt > st.attempt)), r.row_version "
    "FROM season_manifest_rows r JOIN season_cohorts c ON c.id = r.cohort_id "
    "WHERE c.manifest_id = :m ORDER BY r.id"
)


def _row(r: tuple[object, ...]) -> RowView:
    binder = cast(dict[str, object], r[8] or {})
    letter = cast(dict[str, object], r[9] or {})
    fee = letter.get("fee_change_pct")
    return RowView(
        cast(UUID, r[0]), cast(UUID, r[1]), cast(UUID, r[2]), str(r[3]),
        tuple(cast(list[str], r[4])), cast(UUID | None, r[5]), cast(UUID | None, r[6]),
        cast(UUID | None, r[7]), int(cast(int, binder.get("binders", 0))),
        int(cast(int, binder.get("requests", 0))), str(letter.get("kind", "none")),
        None if fee is None else Decimal(str(fee)), tuple(cast(list[str], r[10])),
        int(cast(int, r[11])), tuple(cast(list[str], r[12])), bool(r[13]), bool(r[14]),
        bool(r[15]), int(cast(int, r[16])),
    )  # fmt: skip


async def manifest(ctx: AuthContext, tax_year: int, manifest_id: UUID) -> ManifestView:
    """The manifest and its cohorts with the rows the reader may see (walls: no row or count)."""
    await _firm(ctx, "season.read")
    walled = await walled_from(ctx.tenant, ctx.user_id)
    async with tenant_session(ctx.tenant) as session:
        m = (await session.execute(_MANIFEST, {"m": manifest_id, "y": tax_year})).first()
        if m is None:
            raise NotFound("season_manifest")
        cohorts = [tuple(c) for c in await session.execute(_COHORTS, {"m": manifest_id})]
        rows = [_row(tuple(r)) for r in await session.execute(_ROWS, {"m": manifest_id})]
    offices = dict(await firm_offices(ctx.tenant))
    clients = {n.client_id: n.name for n in await firm_names(ctx.tenant) if n.id == n.client_id}
    kept = (replace(r, client_name=clients.get(r.client_id, "")) for r in rows)
    visible_rows = sorted(
        (r for r in kept if r.client_id not in walled),
        key=lambda r: (r.client_name, str(r.row_id)),
    )
    return ManifestView(
        cast(UUID, m[0]), cast(UUID, m[1]), int(cast(int, m[2])), int(cast(int, m[3])),
        str(m[4]), cast(UUID, m[5]), cast(datetime, m[6]), str(m[7]),
        tuple(
            CohortView(
                cast(UUID, c[0]), int(cast(int, c[1])), cast(UUID, c[2]),
                offices.get(cast(UUID, c[2]), ""), str(c[3]), str(c[4]), cast(UUID | None, c[5]),
                tuple(r for r in visible_rows if r.cohort_id == c[0]),
            )
            for c in cohorts
        ),
    )  # fmt: skip


async def manifests(ctx: AuthContext) -> list[tuple[UUID, int, UUID | None, datetime]]:
    """Every season (id, tax year, its ready manifest, opened at), newest first."""
    await _firm(ctx, "season.read")
    async with tenant_session(ctx.tenant) as session:
        found = await session.execute(
            text(
                "SELECT s.id, s.tax_year, (SELECT m.id FROM season_manifests m WHERE "
                "m.season_id = s.id AND m.status = 'ready'), s.opened_at FROM seasons s "
                "ORDER BY s.tax_year DESC"
            )
        )
        return [
            (cast(UUID, r[0]), int(cast(int, r[1])), cast(UUID | None, r[2]),
             cast(datetime, r[3]))
            for r in found
        ]  # fmt: skip


_OF_COHORT = text(
    "SELECT s.tax_year, c.manifest_id FROM season_cohorts c JOIN season_manifests m "
    "ON m.id = c.manifest_id JOIN seasons s ON s.id = m.season_id WHERE c.id = :c"
)
_OF_ROW = text("SELECT cohort_id FROM season_manifest_rows WHERE id = :r")


async def cohort(ctx: AuthContext, cohort_id: UUID) -> CohortView:
    """A cohort with the rows the reader may see (its manifest read, walls applied)."""
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_OF_COHORT, {"c": cohort_id})).first()
    if found is None:
        raise NotFound("season_cohort")
    view = await manifest(ctx, int(cast(int, found[0])), cast(UUID, found[1]))
    return next(c for c in view.cohorts if c.cohort_id == cohort_id)


async def row(ctx: AuthContext, row_id: UUID) -> RowView:
    async with tenant_session(ctx.tenant) as session:
        cohort_id = await session.scalar(_OF_ROW, {"r": row_id})
    if cohort_id is None:
        raise NotFound("season_manifest_row")
    found = next(
        (r for r in (await cohort(ctx, cast(UUID, cohort_id))).rows if r.row_id == row_id), None
    )
    if found is None:
        raise NotFound("season_manifest_row")  # walled: no row
    return found


# --- writes on rows ------------------------------------------------------------------------------

_ROW_COHORT = text(
    "SELECT r.client_id, r.row_version, c.status, m.status FROM season_manifest_rows r "
    "JOIN season_cohorts c ON c.id = r.cohort_id JOIN season_manifests m ON m.id = c.manifest_id "
    "WHERE r.id = :r FOR UPDATE OF r"
)


async def _draft_row(ctx: AuthContext, row_id: UUID, walled: frozenset[UUID]) -> tuple[UUID, int]:
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_ROW_COHORT, {"r": row_id})).first()
    if found is None or cast(UUID, found[0]) in walled:
        raise NotFound("season_manifest_row")
    if found[2] != "draft" or found[3] != "ready":
        raise CohortApproved(facts={"row_id": str(row_id)})
    return cast(UUID, found[0]), int(cast(int, found[1]))


_REASSIGN = text(
    "UPDATE season_manifest_rows SET preparer_user_id = coalesce(:p, preparer_user_id), "
    "reviewer_user_id = coalesce(:r, reviewer_user_id), "
    "signer_user_id = coalesce(:s, signer_user_id), row_version = row_version + 1 "
    "WHERE id = :id AND row_version = :seen RETURNING row_version"
)


async def reassign(
    ctx: AuthContext,
    row_id: UUID,
    seen: int,
    *,
    preparer: UUID | None = None,
    reviewer: UUID | None = None,
    signer: UUID | None = None,
) -> None:
    """AC-3: an eligible person — an active member who is not walled from the client."""
    await _firm(ctx, "season_setup.prepare")
    walled = await walled_from(ctx.tenant, ctx.user_id)
    client, _ = await _draft_row(ctx, row_id, walled)
    people = [p for p in (preparer, reviewer, signer) if p is not None]
    if not people:
        raise DomainInvalid(facts={"field": "assignee"})
    for person in people:
        if not await is_active_member(ctx.tenant_id, person) or client in await walled_from(
            ctx.tenant, person
        ):
            raise AssigneeNotEligible(facts={"user_id": str(person)})
    async with uow(ctx.tenant) as tx:
        moved = await tx.session.scalar(
            _REASSIGN,
            {"p": preparer, "r": reviewer, "s": signer, "id": row_id, "seen": seen},
        )
        if moved is None:
            raise StaleRow(facts={"row_id": str(row_id)})
        tx.record(
            "season_manifest_row.reassigned",
            target=Target("season_manifest_row", row_id),
            after=Ref(version=int(cast(int, moved))),
        )


_EXCLUDE = text(
    "UPDATE season_manifest_rows SET excluded_at = clock_timestamp(), excluded_by = :u, "
    "exclusion_reason = :reason, row_version = row_version + 1 "
    "WHERE id = :id AND excluded_at IS NULL RETURNING id"
)


async def exclude(ctx: AuthContext, row_ids: Sequence[UUID], reason: str) -> int:
    """Rows leave the season with a reason (insert-only history in the audit trail)."""
    await _firm(ctx, "season_setup.prepare")
    walled = await walled_from(ctx.tenant, ctx.user_id)
    for row_id in row_ids:
        await _draft_row(ctx, row_id, walled)
    done = 0
    try:
        async with uow(ctx.tenant) as tx:
            for row_id in row_ids:
                if await tx.session.scalar(
                    _EXCLUDE, {"u": ctx.user_id, "reason": reason, "id": row_id}
                ):
                    done += 1
                    tx.record(
                        "season_manifest_row.excluded",
                        target=Target("season_manifest_row", row_id),
                    )
            if done == 0:
                raise _Nothing  # every row was excluded already: no write, no event
    except _Nothing:
        return 0
    return done


class _Nothing(Exception):
    """Leave the unit of work without a commit (nothing changed)."""


# --- export --------------------------------------------------------------------------------------


async def export_xlsx(ctx: AuthContext, tax_year: int, manifest_id: UUID) -> bytes:
    """The manifest as the reader sees it, one sheet: cohort, client, forms, people, exceptions."""
    found = await manifest(ctx, tax_year, manifest_id)
    await _firm(ctx, "export.create")
    people = {
        u
        for c in found.cohorts
        for r in c.rows
        for u in (r.preparer_user_id, r.reviewer_user_id, r.signer_user_id)
        if u is not None
    }
    names = await names_of(sorted(people, key=str)) if people else {}

    def name(u: UUID | None) -> str:
        return "" if u is None else names.get(u, "Former member")

    rows: list[list[str | int | Decimal | bool | None]] = [
        ["Cohort", "Office", "Segment", "Client", "Forms", "Preparer", "Reviewer", "Signer",
         "Binders", "Letter", "Exceptions", "Status"],
    ]  # fmt: skip
    for c in found.cohorts:
        for r in c.rows:
            rows.append(
                [c.position, c.office_name, c.segment, r.client_name, ", ".join(r.forms),
                 name(r.preparer_user_id), name(r.reviewer_user_id), name(r.signer_user_id),
                 r.binders, r.letter_kind, ", ".join(r.exception_codes), r.display]
            )  # fmt: skip
    async with uow(ctx.tenant) as tx:
        tx.record("season_manifest.exported", target=Target("season_manifest", manifest_id))
    return workbook([Sheet(f"TY{tax_year} manifest", rows)])


AUDIT_CLIENT_KINDS: Final = frozenset({"season_manifest_row"})
_ROW_CLIENTS = text("SELECT id, client_id FROM season_manifest_rows WHERE id = ANY(:i)")


async def audit_clients(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """A manifest row's audit events belong to its client (walls apply in the trail)."""
    if kind not in AUDIT_CLIENT_KINDS or not ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(_ROW_CLIENTS, {"i": list(ids)})
        return {cast(UUID, r[0]): cast(UUID, r[1]) for r in rows}


__all__ = [
    "AssigneeNotEligible",
    "CandidateSource",
    "CohortApproved",
    "CohortView",
    "ManifestView",
    "NoCandidateSource",
    "RowView",
    "SeasonCandidate",
    "StaleRow",
    "build_manifest",
    "cohort",
    "exclude",
    "export_xlsx",
    "inputs_hash",
    "manifest",
    "manifests",
    "reassign",
    "register_season_candidates",
    "row",
]
