"""A-05-T16: the EBP-02 provisions service (A-05 §3 F2; SPEC-641; DEC-2069).

A provisions review reads the plan's documents and verifies, one by one, the twenty provisions
the tests depend on (`compute/ebp/provisions.py`: the registry, the amendment rule and the SPD
comparison).

- **Start** (`POST …/ebp/plan-reviews`): a person names the document versions in order (the
  adoption agreement, the amendment when it governs, the SPD); the review is recorded
  (`ebp_plan_reviews`, review 1, 2, ...) and a section-drafter run of mode `ebp_provisions` starts
  on EBP-02. The mode's mapping gives the run those documents as D1 to D3 (masked page text); it
  suggests each provision's election (B<row>) and reference (C<row>), cited to the clause.
- **Provisions** are EBP-02's own cells: a person adopts a suggestion (C3, `workpaper_cell`), and
  **verifying** is a C3 field tick (L1) on the value cell; a tick on an earlier value is stale.
- **Sign off** waits for every provision verified: a sign-off guard on the `ebp_provisions` kind
  answers 409 `sign_off_blocked` with `facts.reason` `provisions_unverified` and how many remain.
- **Downstream** (EBP-03's entry rule, EBP-04's match formula, EBP-09's expenses clause) reads
  `verified_provisions`: only ticked values, never a draft. `entry_rule_read` is EBP-03's reader:
  until all three of its provisions are ticked, and in wording code can read, there is no rule
  and code computes no entry date (DEC-2482).
- **Conflicts**: code compares the governing wording with the SPD (`compute.conflicts`) over the
  values a person enters for the SPD; only a person raises one (SHL-15 → AUD-15).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Row

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.agents.api import (
    ModeDocument,
    ModeInputs,
    ModePage,
    SourcePaper,
    start_section_draft,
)
from abacus.modules.assurance.compute.ebp.eligibility import (
    ENTRY_RULE_KEYS,
    RATE_KEYS,
    EntryRule,
    Rates,
    entry_rule_from,
    rates_from,
)
from abacus.modules.assurance.compute.ebp.expenses import plan_may_pay
from abacus.modules.assurance.compute.ebp.provisions import (
    BY_KEY,
    PROVISIONS,
    Provision,
    amendment_governs,
    conflicts,
    provisions_for,
)
from abacus.modules.engagements.api import assurance_item, get_ref
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    citation_display,
    record_citations,
    review_material,
    version_view,
)
from abacus.modules.identity.api import AgentContext, AuthContext, Forbidden, authorise
from abacus.modules.review.api import (
    FieldState,
    field_states,
    reviewable_facts,
    sign_off_states,
)
from abacus.modules.workpapers.api import (
    CELL_TARGET,
    latest_version_id,
    paper_id_of_kind,
    paper_of_kind,
)

KIND: Final = "ebp_provisions"
PAPER_TARGET: Final = "workpaper"
MODE: Final = "ebp_provisions"
AUDIT_TARGET: Final = "ebp_plan_review"
UNVERIFIED: Final = "provisions_unverified"
DOCUMENT_TITLES: Final = ("Adoption agreement", "Amendment", "Summary plan description")
EntryRuleState = Literal["verified", "unverified", "unreadable"]


class ReviewInvalid(DomainInvalid):
    code = "plan_review_invalid"


class CitationUnverified(DomainInvalid):
    """The quote a person gave for a document value was not found on that page (C4)."""

    code = "citation_unverified"


DocumentSource = Literal["spd", "amendment"]
DOCUMENT_TARGET: Final = "ebp_provision"


@dataclass(frozen=True)
class DocumentValue:
    """A value a person read from the SPD or the amendment, with its verified citation."""

    text: str
    note: str
    page: int
    evidence_version_id: UUID
    match_id: str | None


@dataclass(frozen=True)
class CitedSpot:
    evidence_version_id: UUID
    page: int | None
    match_id: str
    # SHL-07's card on the reference (DEC-2491): code's title and location, the re-read quote.
    title: str = ""
    loc: str = ""
    quote: str | None = None


@dataclass(frozen=True)
class ProvisionDocuments:
    spd: DocumentValue | None = None
    amendment: DocumentValue | None = None
    amendment_effective_on: date | None = None


@dataclass(frozen=True)
class ProvisionState:
    provision: Provision
    value: str | None
    reference: str | None
    verified: bool
    citation_count: int
    value_hash: str | None = None  # what a tick on the value signs (None before a value)
    # A-05-T16 (DEC-2489): code's comparison with the SPD a person entered, and the amendment's
    # effective date on a provision it governs in this review.
    conflict: str | None = None
    conflict_source: DocumentValue | None = None
    amended_on: date | None = None
    # A-05-T17 (DEC-2490): where the value's first verified citation sits, for the viewer to light.
    source: CitedSpot | None = None


@dataclass(frozen=True)
class SignedLevel:
    level: int
    user_id: UUID
    at: datetime
    stale: bool


@dataclass(frozen=True)
class EntryRuleRead:
    """What EBP-03 may compute from: `rule` is set only when `state` is verified."""

    state: EntryRuleState
    rule: EntryRule | None = None


@dataclass(frozen=True)
class RatesRead:
    """EBP-03's escalation and missed amounts and EBP-04's expected figures: `rates` is set only
    when `state` is verified (A-05-T16; DEC-2488)."""

    state: EntryRuleState
    rates: Rates | None = None


@dataclass(frozen=True)
class ExpensesClauseRead:
    """EBP-09's Plan expenses election: whether the plan may pay, only when verified."""

    state: EntryRuleState
    wording: str | None = None
    plan_may_pay: bool | None = None


@dataclass(frozen=True)
class PlanReads:
    """Everything downstream reads from EBP-02, from one read of the verified values."""

    entry: EntryRuleRead
    rates: RatesRead
    expenses: ExpensesClauseRead


@dataclass(frozen=True)
class VersionDiff:
    """What the latest review adds to an earlier one (EBP-02 b2's ribbon)."""

    current_no: int
    added_labels: tuple[str, ...]


@dataclass(frozen=True)
class PlanReview:
    review_no: int
    provisions: tuple[ProvisionState, ...]
    workpaper_id: UUID | None = None
    sign_offs: tuple[SignedLevel, ...] = ()
    version_diff: VersionDiff | None = None

    @property
    def verified(self) -> int:
        return sum(1 for p in self.provisions if p.verified)


_LATEST: Final = text(
    "SELECT review_no, document_version_ids, amendment_in_force FROM ebp_plan_reviews "
    "WHERE work_item_id = :w ORDER BY review_no DESC LIMIT 1"
)
_BY_NO: Final = text(
    "SELECT review_no, document_version_ids, amendment_in_force FROM ebp_plan_reviews "
    "WHERE work_item_id = :w AND review_no = :n"
)
_DOCUMENTS: Final = text(
    "SELECT DISTINCT ON (provision_key) provision_key, value, amendment_effective_on "
    "FROM ebp_provisions WHERE work_item_id = :w AND origin IN ('human', 'import') "
    "ORDER BY provision_key, created_at DESC"
)
_PLAN_YEAR_END: Final = text("SELECT plan_year_end FROM ebp_plans WHERE work_item_id = :w")
_UPSERT_DOCUMENT: Final = text(
    "INSERT INTO ebp_provisions (tenant_id, engagement_id, work_item_id, workpaper_version_id, "
    "provision_key, value, origin) VALUES (:t, :e, :w, :v, :k, CAST(:value AS jsonb), 'human') "
    "ON CONFLICT (tenant_id, workpaper_version_id, provision_key) DO UPDATE SET "
    "value = ebp_provisions.value || EXCLUDED.value, origin = 'human' RETURNING id"
)
_SET_SPD: Final = text(
    "UPDATE ebp_provisions SET value = value || CAST(:value AS jsonb), citation_id = :c "
    "WHERE id = :id"
)
_SET_AMENDMENT: Final = text(
    "UPDATE ebp_provisions SET value = value || CAST(:value AS jsonb), "
    "amendment_effective_on = :on, amendment_citation_id = :c WHERE id = :id"
)
_AMENDED: Final = text(
    "SELECT latest_amendment_ref IS NOT NULL FROM ebp_plans WHERE work_item_id = :w"
)
_INSERT: Final = text(
    "INSERT INTO ebp_plan_reviews (tenant_id, engagement_id, work_item_id, workpaper_id, "
    "review_no, document_version_ids, amendment_in_force, started_by) "
    "SELECT :tenant, :engagement, :w, :paper, coalesce(max(review_no), 0) + 1, "
    "CAST(:docs AS uuid[]), :amended, :user FROM ebp_plan_reviews WHERE work_item_id = :w "
    "RETURNING id, review_no"
)


async def start_review(
    ctx: AuthContext,
    work_item_id: UUID,
    document_version_ids: Sequence[UUID],
    idempotency_key: str,
) -> UUID:
    """A person starts a provisions read; the drafter run's id. The route authorised
    `workpaper.draft` and the flags; the drafter checks them again (defence in depth)."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden("workpaper.draft", "role")
    if len(set(document_version_ids)) != len(document_version_ids):
        raise ReviewInvalid(facts={"field": "document_version_ids"})
    item = await assurance_item(ctx.tenant, work_item_id)
    engagement = await get_ref(ctx, item.engagement_id)
    await authorise(ctx, "workpaper.draft", engagement.resource())
    for version_id in document_version_ids:
        if (await version_view(ctx.tenant, version_id)).engagement_id != item.engagement_id:
            raise NotFound("evidence_version")
    paper = await paper_of_kind(ctx, item.engagement_id, KIND)
    async with tenant_session(ctx.tenant) as session:
        amended = bool((await session.execute(_AMENDED, {"w": work_item_id})).scalar())
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                _INSERT,
                {
                    "tenant": ctx.tenant_id,
                    "engagement": item.engagement_id,
                    "w": work_item_id,
                    "paper": paper,
                    "docs": [str(v) for v in document_version_ids],
                    "amended": amended,
                    "user": ctx.user_id,
                },
            )
        ).one()
        tx.record(
            "ebp_plan_review.started",
            target=Target(AUDIT_TARGET, row.id),
            scope=Scope(engagement_id=item.engagement_id, work_item_id=work_item_id),
        )
    return await start_section_draft(
        ctx, item.engagement_id, paper, MODE, None, f"{idempotency_key}:{row.review_no}"
    )


async def provisions_inputs(actor: AgentContext, paper: SourcePaper) -> ModeInputs:
    """The `ebp_provisions` mode's documents: the latest review's versions as D1 to D3, masked
    page text only (fail closed: a version not yet scanned is left out)."""
    async with tenant_session(actor.tenant) as session:
        latest = (await session.execute(_LATEST, {"w": paper.work_item_id})).first()
    if latest is None:
        return ModeInputs()
    documents: list[ModeDocument] = []
    titles = DOCUMENT_TITLES if latest.amendment_in_force else DOCUMENT_TITLES[::2]
    for n, version_id in enumerate(latest.document_version_ids):
        material = await review_material(actor.tenant, version_id, sheets=False)
        if material is None or not material.pages:
            continue
        title = titles[n] if n < len(titles) else f"Document {n + 1}"
        documents.append(
            ModeDocument(
                version_id,
                title,
                tuple(ModePage(p, body) for p, body in sorted(material.pages.items())),
            )
        )
    return ModeInputs(documents=tuple(documents))


def _text_of(state: FieldState | None) -> str | None:
    if state is None or state.value is None:
        return None
    value = state.value.get("v")
    return None if value is None else str(value)


def _verified(state: FieldState) -> bool:
    """Verified: a current tick (any level) on a value that exists."""
    return bool(state.ticked_levels) and state.value is not None


async def _states(
    tenant: TenantContext, workpaper_id: UUID, rows: Sequence[Provision]
) -> dict[str, FieldState]:
    keys = [k for p in rows for k in (p.value_cell, p.reference_cell)]
    return await field_states(tenant, CELL_TARGET, workpaper_id, keys)


async def _review_row(
    tenant: TenantContext, work_item_id: UUID, review_no: int | None
) -> Row[Any] | None:  # Any: the row's columns are the query's (review_no, ids, amended)
    async with tenant_session(tenant) as session:
        if review_no is None:
            return (await session.execute(_LATEST, {"w": work_item_id})).first()
        return (await session.execute(_BY_NO, {"w": work_item_id, "n": review_no})).first()


async def _signed(tenant: TenantContext, paper: UUID) -> tuple[SignedLevel, ...]:
    """The paper's sign-offs: EBP-02's "✓ HL" and "Reviewed · HL Sep 17"."""
    facts = await reviewable_facts(tenant, PAPER_TARGET, paper)
    found = await sign_off_states(tenant, PAPER_TARGET, [paper], {paper: facts.content_hash})
    return tuple(
        SignedLevel(s.level, s.signed_by, s.signed_at, s.stale)
        for s in found[paper]
        if s.signed_by is not None and s.signed_at is not None
    )


def _document(raw: object) -> DocumentValue | None:
    if not isinstance(raw, dict):
        return None
    found = cast(dict[str, object], raw)
    return DocumentValue(
        str(found["text"]),
        str(found["note"]),
        int(cast(int, found["page"])),
        UUID(str(found["evidence_version_id"])),
        None if found.get("match_id") is None else str(found["match_id"]),
    )


async def _documents(
    tenant: TenantContext, work_item_id: UUID
) -> tuple[dict[str, ProvisionDocuments], date | None]:
    """The SPD and amendment values people entered, newest first per provision, and the plan
    year's end the amendment is read against."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_DOCUMENTS, {"w": work_item_id})).mappings().all()
        year_end = (await session.execute(_PLAN_YEAR_END, {"w": work_item_id})).scalar()
    out: dict[str, ProvisionDocuments] = {}
    for r in rows:
        value = cast(dict[str, object], r["value"] or {})
        out[str(r["provision_key"])] = ProvisionDocuments(
            _document(value.get("spd")),
            _document(value.get("amendment")),
            cast(date | None, r["amendment_effective_on"]),
        )
    return out, cast(date | None, year_end)


def compared(
    provision: Provision,
    value: str | None,
    docs: ProvisionDocuments | None,
    *,
    amendment_in_force: bool,
    plan_year_end: date | None,
) -> tuple[str | None, DocumentValue | None, date | None]:
    """A row's SPD conflict, its source and the amendment tag, by code (`compute/ebp/provisions`):
    the paper's value is the governing document's, an amendment a person entered governs from its
    effective date, and an SPD that reads differently after normalising is a conflict."""
    if docs is None:
        return None, None, None
    governed = (
        provision.amendment_governed
        and amendment_in_force
        and docs.amendment_effective_on is not None
        and plan_year_end is not None
        and amendment_governs(docs.amendment_effective_on, plan_year_end)
    )
    amended_on = docs.amendment_effective_on if governed else None
    if docs.spd is None or value is None:
        return None, None, amended_on
    found = conflicts(
        {
            provision.key: {
                "adoption_agreement": value,
                "amendment": docs.amendment.text if governed and docs.amendment else None,
                "spd": docs.spd.text,
            }
        },
        amendment_effective_on=docs.amendment_effective_on,
        plan_year_end=plan_year_end or date.max,
    )
    if not found:
        return None, None, amended_on
    return f"SPD: {docs.spd.text}"[:200], docs.spd, amended_on


async def record_document_value(
    ctx: AuthContext,
    work_item_id: UUID,
    key: str,
    source: DocumentSource,
    *,
    value: str,
    evidence_version_id: UUID,
    page: int,
    quote: str,
    note: str,
    effective_on: date | None,
) -> None:
    """A person keys what the SPD or the amendment says for one provision (DV-EBP-02-1's agent-off
    path; DEC-2489). The quote must be found on that page of that document (C4), or 422
    `citation_unverified`; the note is required. The route authorised `ebp_provision.enter`."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden("ebp_provision.enter", "role")
    provision = BY_KEY.get(key)
    if provision is None:
        raise NotFound(DOCUMENT_TARGET)
    if source == "amendment" and (not provision.amendment_governed or effective_on is None):
        raise ReviewInvalid(facts={"field": "effective_on"})
    if source == "spd" and effective_on is not None:
        raise ReviewInvalid(facts={"field": "effective_on"})
    if not value.strip() or not note.strip() or not quote.strip():
        raise ReviewInvalid(facts={"field": "note"})
    item = await assurance_item(ctx.tenant, work_item_id)
    if (await version_view(ctx.tenant, evidence_version_id)).engagement_id != item.engagement_id:
        raise NotFound("evidence_version")
    paper = await paper_of_kind(ctx, item.engagement_id, KIND)
    version = await latest_version_id(ctx.tenant, paper)
    if version is None:
        raise NotFound("workpaper_version")
    async with uow(ctx.tenant) as tx:
        row_id = (
            await tx.session.execute(
                _UPSERT_DOCUMENT,
                {
                    "t": ctx.tenant_id,
                    "e": item.engagement_id,
                    "w": work_item_id,
                    "v": version,
                    "k": key,
                    "value": "{}",
                },
            )
        ).scalar_one()
        [cited] = await record_citations(
            tx,
            actor=ctx,
            anchor=CitationAnchor(
                type=DOCUMENT_TARGET,
                id=row_id,
                ref=f"{provision.label} ({source})",
                engagement_id=item.engagement_id,
                work_item_id=work_item_id,
            ),
            claims=[
                CitationClaim(
                    "document_text",
                    {"evidence_version_id": str(evidence_version_id), "page": page},
                    quote=quote.strip(),
                )
            ],
        )
        if not cited.verified:
            raise CitationUnverified(facts={"reason": cited.verification_reason or "unverified"})
        entered = {
            "text": value.strip(),
            "note": note.strip(),
            "page": page,
            "evidence_version_id": str(evidence_version_id),
            "match_id": cited.match_id,
        }
        await tx.session.execute(
            _SET_SPD if source == "spd" else _SET_AMENDMENT,
            {
                "value": json.dumps({source: entered}),
                "c": cited.id,
                "id": row_id,
                **({} if source == "spd" else {"on": effective_on}),
            },
        )
        tx.record(
            "ebp_provision.document_value_recorded",
            target=Target(DOCUMENT_TARGET, row_id),
            after=Ref(citation=cited.id),
            scope=Scope(engagement_id=item.engagement_id, work_item_id=work_item_id),
        )


async def _spot(ctx: AuthContext, citation_ids: Sequence[UUID]) -> CitedSpot | None:
    """The first of a value's citations the reader may see that is verified and has a region on
    a document: what hovering the provision lights in the viewer (DV-EBP-02-3)."""
    for citation_id in citation_ids:
        try:
            view = await citation_display(ctx, citation_id)
        except (NotFound, Forbidden):
            continue
        version = view.source.evidence_version_id
        if view.verified and view.match_id is not None and version is not None:
            return CitedSpot(
                version, view.source.page, view.match_id, view.title, view.loc, view.quote
            )
    return None


async def review_of(ctx: AuthContext, work_item_id: UUID, review_no: int | None) -> PlanReview:
    """EBP-02's provisions for the latest review (or `review_no`, read-only b2): each row's
    adopted value and reference, and whether its value is verified now."""
    item = await assurance_item(ctx.tenant, work_item_id)
    found = await _review_row(ctx.tenant, work_item_id, review_no)
    if found is None:
        if review_no is not None:
            raise NotFound("ebp_plan_review")
        return PlanReview(0, ())
    paper = await paper_of_kind(ctx, item.engagement_id, KIND)
    rows = provisions_for(amendment_in_force=bool(found.amendment_in_force))
    states = await _states(ctx.tenant, paper, rows)
    docs, year_end = await _documents(ctx.tenant, work_item_id)
    spots = {p.key: await _spot(ctx, states[p.value_cell].citation_ids) for p in rows}
    latest = None if review_no is None else await _review_row(ctx.tenant, work_item_id, None)
    version_diff = None
    if latest is not None and latest.review_no != found.review_no:
        held = {p.key for p in rows}
        version_diff = VersionDiff(
            int(latest.review_no),
            tuple(
                p.label
                for p in provisions_for(amendment_in_force=bool(latest.amendment_in_force))
                if p.key not in held
            ),
        )
    return PlanReview(
        int(found.review_no),
        tuple(
            ProvisionState(
                p,
                _text_of(states.get(p.value_cell)),
                _text_of(states.get(p.reference_cell)),
                bool(states[p.value_cell].ticked_levels)
                and states[p.value_cell].value is not None,
                len(states[p.value_cell].citation_ids),
                states[p.value_cell].content_hash or None,
                *compared(
                    p,
                    _text_of(states.get(p.value_cell)),
                    docs.get(p.key),
                    amendment_in_force=bool(found.amendment_in_force),
                    plan_year_end=year_end,
                ),
                spots[p.key],
            )
            for p in rows
        ),
        workpaper_id=paper,
        sign_offs=await _signed(ctx.tenant, paper),
        version_diff=version_diff,
    )


_EARLIER: Final = text(
    "SELECT review_no, created_at FROM ebp_plan_reviews WHERE work_item_id = :w "
    "AND review_no < (SELECT max(review_no) FROM ebp_plan_reviews WHERE work_item_id = :w) "
    "ORDER BY review_no DESC"
)


async def earlier_reviews(tenant: TenantContext, work_item_id: UUID) -> list[tuple[int, datetime]]:
    """Every review before the latest, newest first, with when it started (the rail's children);
    the cockpit's reader authorised the work item."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_EARLIER, {"w": work_item_id})).all()
    return [(int(r.review_no), cast(datetime, r.created_at)) for r in rows]


async def unverified_count(tenant: TenantContext, workpaper_id: UUID, work_item_id: UUID) -> int:
    async with tenant_session(tenant) as session:
        latest = (await session.execute(_LATEST, {"w": work_item_id})).first()
    rows = provisions_for(amendment_in_force=True if latest is None else latest.amendment_in_force)
    return unverified_of(rows, await _states(tenant, workpaper_id, rows))


async def sign_off_guard(
    tenant: TenantContext, workpaper_id: UUID, work_item_id: UUID | None
) -> tuple[str, int] | None:
    """EBP-02 signs off once every provision is verified (fail closed without a work item)."""
    if work_item_id is None:
        return (UNVERIFIED, len(PROVISIONS))
    left = await unverified_count(tenant, workpaper_id, work_item_id)
    return None if left == 0 else (UNVERIFIED, left)


async def verified_provisions(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID, workpaper_id: UUID
) -> Mapping[str, str]:
    """The verified elections by provision key, for EBP-03, EBP-04 and EBP-09's engines: a value
    without a current tick is left out, so a draft is never consumed downstream."""
    del engagement_id  # the caller authorised on it
    async with tenant_session(tenant) as session:
        latest = (await session.execute(_LATEST, {"w": work_item_id})).first()
    if latest is None:
        return {}
    rows = provisions_for(amendment_in_force=latest.amendment_in_force)
    return verified_of(rows, await _states(tenant, workpaper_id, rows))


def entry_rule_of(verified: Mapping[str, str]) -> EntryRuleRead:
    """Verified only when all three provisions are ticked and their wording is one code reads."""
    if any(key not in verified for key in ENTRY_RULE_KEYS):
        return EntryRuleRead("unverified")
    rule = entry_rule_from(verified)
    return EntryRuleRead("unreadable") if rule is None else EntryRuleRead("verified", rule)


async def entry_rule_read(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID
) -> EntryRuleRead:
    """EBP-03's entry rule (the caller authorised on the engagement). No EBP-02 paper or no review
    yet reads as unverified."""
    return (await plan_reads(tenant, engagement_id, work_item_id)).entry


def rates_of(verified: Mapping[str, str]) -> RatesRead:
    """Verified only when the default rate, the escalation and the match are all ticked and their
    wording is one code reads; QACA's constants never stand in."""
    if any(key not in verified for key in RATE_KEYS):
        return RatesRead("unverified")
    rates = rates_from(verified)
    return RatesRead("unreadable") if rates is None else RatesRead("verified", rates)


def expenses_clause_of(verified: Mapping[str, str]) -> ExpensesClauseRead:
    wording = verified.get("plan_expenses")
    if wording is None:
        return ExpensesClauseRead("unverified")
    may = plan_may_pay(wording)
    return ExpensesClauseRead("unreadable" if may is None else "verified", wording, may)


async def plan_reads(tenant: TenantContext, engagement_id: UUID, work_item_id: UUID) -> PlanReads:
    """EBP-03, EBP-04 and EBP-09's reads of the verified provisions (the caller authorised on the
    engagement); an unticked or drafted value is never among them."""
    paper = await paper_id_of_kind(tenant, engagement_id, KIND)
    verified: Mapping[str, str] = (
        {}
        if paper is None
        else await verified_provisions(tenant, engagement_id, work_item_id, paper)
    )
    return PlanReads(entry_rule_of(verified), rates_of(verified), expenses_clause_of(verified))


def unverified_of(rows: Sequence[Provision], states: Mapping[str, FieldState]) -> int:
    return sum(1 for p in rows if not _verified(states[p.value_cell]))


def verified_of(rows: Sequence[Provision], states: Mapping[str, FieldState]) -> dict[str, str]:
    """Only the ticked values: an untouched, drafted or since-changed value is left out."""
    out: dict[str, str] = {}
    for p in rows:
        state = states[p.value_cell]
        value = _text_of(state)
        if _verified(state) and value is not None:
            out[p.key] = value
    return out
