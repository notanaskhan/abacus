"""The instrument service (T-07-T12; TASK-8039; T-07 §3.1 to §3.5; SPEC-656 AC-1.1 to AC-5.2).

- **Attach** (AC-1.2): a client-level file becomes the trust's governing instrument on the 1041
  (P-40); a second instrument supersedes the first (an amendment or restatement), which moves the
  first one's clause citations (`move_clause_citations`, ADR-343 §5). The instrument is segmented
  in code at once (`segment.py`) over the version's word layer; a new current interpretation
  (`unread`) replaces the return's previous one.
- **Read** (AC-1.1): TXT-01's model: the trust profile, the instrument, its segmentation, the
  current interpretation, the seven determinations (latest version each, clause labels from
  their verified citations), cited-by and the reader's availability.
- **Clauses** (AC-1.3): the clause tree with pages, regions and hashes, never text; manual
  marking while the segmentation `needs_review`.
- **Determinations** (AC-1.6, AC-3.1 to AC-3.3): a person records or edits one; each change is a
  new insert-only version. A clause-governed key needs at least one verified, live citation in
  the return's engagement (422 `uncited_change`); an edit carries a reason and the version it
  read (409 `version_conflict`); nothing changes while the interpretation is approved (409
  `interpretation_locked`).
- **Review** (AC-4.1, AC-4.2): `instrument_interpretation` is a reviewable at L1 and L3 (DEC-84);
  an L3 sign-off approves and locks the interpretation (`sign_off.recorded`), and a Manager or
  Partner reopens it with a reason (AC-5.2), which stales the TXT-02 sign-off through the content
  hash.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, cast, get_args
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.evidence.api import (
    citation_locators,
    supported_citations,
    version_file_facts,
    version_word_layers,
)
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, names_of
from abacus.modules.review.api import (
    Reviewable,
    ReviewableFacts,
    register_reviewable,
    register_reviewable_facts,
)
from abacus.modules.tax.fiduciary_contract import (
    CLAUSE_GOVERNED,
    ClauseMarkIn,
    ClauseRegionOut,
    DeterminationEditIn,
    DeterminationKey,
    DeterminationRecordIn,
    FiduciaryAction,
    GoverningInstrumentOut,
    InstrumentAttachIn,
    InstrumentClauseOut,
    InstrumentClausesOut,
    InstrumentDeterminationOut,
    InstrumentInterpretationOut,
    InstrumentOut,
    InstrumentReaderOut,
    InstrumentSegmentationOut,
    InterpretationLocked,
    InterpretationReopenIn,
    TrustProfileOut,
)
from abacus.modules.tax.instrument_citations import KIND as CLAUSE_KIND
from abacus.modules.tax.instrument_citations import move_clause_citations
from abacus.modules.tax.instrument_events import (
    InstrumentInterpretationAdopted,
    InstrumentInterpretationApproved,
    InstrumentInterpretationReopened,
)
from abacus.modules.tax.instruments import repository as repo
from abacus.modules.tax.instruments.segment import SEGMENTATION_VERSION, segment

TARGET: Final = "instrument_interpretation"
LEVELS: Final = (1, 3)  # DEC-84: preparer L1, approver L3
_VALUE_AAD: Final = "tax.instrument_determination.value"
_REASON_AAD: Final = "tax.instrument_determination.reason"
_REOPEN_AAD: Final = "tax.instrument_interpretation.reopen"


class UncitedChange(DomainInvalid):
    """AC-3.1: a clause-governed determination needs a verified clause citation (422)."""

    code = "uncited_change"


class VersionConflict(DomainConflict):
    code = "version_conflict"


class SegmentationFinal(DomainConflict):
    """Clauses are marked by hand only while the segmentation needs review."""

    code = "segmentation_final"


class NotApproved(DomainConflict):
    """Only an approved interpretation is reopened."""

    code = "interpretation_not_approved"


# --- the return and its scope -------------------------------------------------------------------


@dataclass(frozen=True)
class _Return:
    work_item_id: UUID
    engagement_id: UUID
    client_entity_id: UUID
    form: str
    tax_year: int


async def _return(tenant: TenantContext, return_id: UUID) -> _Return:
    async with tenant_session(tenant) as session:
        row = (await session.execute(repo.RETURN, {"r": return_id})).first()
    if row is None or row.client_entity_id is None or row.form not in ("1041", "706"):
        raise NotFound("tax_return")
    return _Return(row[0], row[1], row[2], row[3], int(row[4]))


async def _authorised(ctx: AuthContext, engagement_id: UUID, action: str) -> None:
    try:
        await authorise(ctx, action, await engagement_resource_of(ctx.tenant, engagement_id))
    except NotFound:
        raise NotFound("tax_return") from None


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


# --- reads --------------------------------------------------------------------------------------


async def _profile(session: AsyncSession, tenant: TenantContext, entity: UUID) -> TrustProfileOut:
    row = (await session.execute(repo.PROFILE, {"e": entity})).first()
    if row is None:
        return TrustProfileOut(
            client_entity_id=entity,
            fiduciary_kind="trust",
            agreement_date=None,
            revocable=False,
            irrevocable_since=None,
            settlor_name=None,
            settlor_died_year=None,
            residency_state=None,
            state_form=None,
            ein=None,
        )
    settlor = (
        (
            await open_sealed(tenant.tenant_id, row.settlor_name_sealed, "tax.trust.settlor")
        ).decode()
        if row.settlor_name_sealed is not None
        else None
    )
    return TrustProfileOut(
        client_entity_id=entity,
        fiduciary_kind=row.fiduciary_kind,
        agreement_date=row.agreement_date,
        revocable=row.revocable,
        irrevocable_since=row.irrevocable_since,
        settlor_name=settlor,
        settlor_died_year=row.settlor_died_year,
        residency_state=row.residency_state,
        state_form=row.state_form,
        ein=None,  # the profile's EIN joins with the entity's sealed TIN through P-12's mask
    )


async def _determinations(
    session: AsyncSession,
    tenant: TenantContext,
    interpretation: Row[Any],  # Any: a raw text() row of tax_instrument_interpretations
    locked: bool,
) -> list[InstrumentDeterminationOut]:
    rows = list((await session.execute(repo.DETERMINATIONS, {"i": interpretation.id})).all())
    labels = {
        r.id: r.label
        for r in (await session.execute(repo.CLAUSE_LABELS, {"s": interpretation.segmentation_id}))
    }
    people = await names_of(
        sorted({r.set_by_id for r in rows if r.set_by_kind == "human"}, key=str)
    )
    cited = await _clause_of_citations(session, [c for r in rows for c in r.citation_ids])
    out: list[InstrumentDeterminationOut] = []
    for r in rows:
        value = (await open_sealed(tenant.tenant_id, r.value_text_sealed, _VALUE_AAD)).decode()
        name = people.get(r.set_by_id, "") if r.set_by_kind == "human" else "Accrued Agent"
        out.append(
            InstrumentDeterminationOut(
                id=r.id,
                key=r.key,
                value_code=r.value_code,
                value_text=value,
                rationale_ref=r.rationale_ref,
                citation_ids=list(r.citation_ids),
                clause_labels=[
                    labels[c] for c in (cited.get(i) for i in r.citation_ids) if c in labels
                ],
                set_by_kind=r.set_by_kind,
                set_by_name=name,
                suggestion_id=r.suggestion_id,
                version=r.seq,
                clause_required=r.key in CLAUSE_GOVERNED and not locked,
            )
        )
    return out


async def _clause_of_citations(session: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """Citation → clause id, for `instrument_clause` citations (the locator names the clause).
    The citations are evidence's; it reads their locators (OWN-001)."""
    out: dict[UUID, UUID] = {}
    for citation_id, locator in (await citation_locators(session, ids, CLAUSE_KIND)).items():
        try:
            out[citation_id] = UUID(str(locator.get("clause_id")))
        except ValueError:
            continue
    return out


async def instrument_read(ctx: AuthContext, return_id: UUID) -> InstrumentOut:
    ret = await _return(ctx.tenant, return_id)
    await _authorised(ctx, ret.engagement_id, "instrument.read")
    async with tenant_session(ctx.tenant) as session:
        profile = await _profile(session, ctx.tenant, ret.client_entity_id)
        instrument = (await session.execute(repo.INSTRUMENT, {"e": ret.client_entity_id})).first()
        segmentation = (
            (await session.execute(repo.SEGMENTATION, {"i": instrument.id})).first()
            if instrument is not None
            else None
        )
        interp = (await session.execute(repo.INTERPRETATION, {"w": return_id})).first()
        determinations = (
            await _determinations(session, ctx.tenant, interp, interp.status == "approved")
            if interp is not None
            else []
        )
    instrument_out: GoverningInstrumentOut | None = None
    if instrument is not None:
        facts = await version_file_facts(ctx.tenant, instrument.evidence_version_id)
        attached = await names_of([instrument.attached_by])
        instrument_out = GoverningInstrumentOut(
            id=instrument.id,
            evidence_version_id=instrument.evidence_version_id,
            file_name=facts.file_name,
            page_count=facts.page_count,
            supersedes_instrument_id=instrument.supersedes_instrument_id,
            attached_by_name=attached.get(instrument.attached_by, ""),
            attached_at=instrument.attached_at,
        )
    allowed: list[FiduciaryAction] = []
    for action in (
        "instrument.attach",
        "instrument.read_run",
        "instrument_determination.edit",
        "instrument_interpretation.reopen",
    ):
        try:
            await _authorised(ctx, ret.engagement_id, action)
            allowed.append(cast(FiduciaryAction, action))
        except Forbidden:
            continue
    return InstrumentOut(
        return_id=return_id,
        profile=profile,
        instrument=instrument_out,
        segmentation=(
            InstrumentSegmentationOut(
                id=segmentation.id,
                status=segmentation.status,
                text_source=segmentation.text_source,
                confidence=segmentation.confidence,
                clause_count=segmentation.clause_count,
            )
            if segmentation is not None
            else None
        ),
        interpretation=await _interpretation_out(ctx.tenant, interp) if interp else None,
        determinations=determinations,
        cited_by=[],  # T-07-T16's computation rows and T-04's return fields cite clauses later
        reader=InstrumentReaderOut(
            availability="agents_off",
            consents_signed=0,
            consents_required=2,
            run_id=None,
            progress_label=None,
        ),  # the reader's availability is T-07-T13's (consent and capability gate)
        allowed_actions=allowed,
    )


async def _interpretation_out(
    tenant: TenantContext,
    interp: Row[Any],  # Any: a raw text() row of tax_instrument_interpretations
) -> InstrumentInterpretationOut:
    return InstrumentInterpretationOut(
        id=interp.id,
        status=interp.status,
        scenario=interp.scenario,
        version_no=interp.version_no,
        content_hash=interp.content_hash or "0" * 64,
        read_run_id=interp.read_run_id,
        adopted_by_name=None,
        adopted_on=None,
        approved_by_name=None,
        approved_on=interp.locked_at.date() if interp.locked_at is not None else None,
        clause_citation_count=0,
    )


# --- attach and segment (AC-1.2, AC-1.3) --------------------------------------------------------


async def attach(ctx: AuthContext, return_id: UUID, body: InstrumentAttachIn) -> None:
    _human(ctx, "instrument.attach")
    ret = await _return(ctx.tenant, return_id)
    await _authorised(ctx, ret.engagement_id, "instrument.attach")
    facts = await version_file_facts(ctx.tenant, body.evidence_version_id)
    if facts.client_entity_id not in (None, ret.client_entity_id):
        raise NotFound("evidence_version")  # another client's file is never attached (P-40)
    layers = await version_word_layers(ctx.tenant, body.evidence_version_id)
    found = segment(layers)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            repo.NEW_PROFILE,
            {
                "e": ret.client_entity_id,
                "t": ctx.tenant_id,
                "u": ctx.user_id,
                "k": "estate" if ret.form == "706" else "trust",
            },
        )
        previous = (await tx.session.execute(repo.INSTRUMENT, {"e": ret.client_entity_id})).first()
        instrument_id = cast(
            UUID,
            await tx.session.scalar(
                repo.NEW_INSTRUMENT,
                {
                    "t": ctx.tenant_id,
                    "e": ret.client_entity_id,
                    "v": body.evidence_version_id,
                    "s": previous.id if previous is not None else None,
                    "u": ctx.user_id,
                },
            ),
        )
        segmentation_id = cast(
            UUID,
            await tx.session.scalar(
                repo.NEW_SEGMENTATION,
                {
                    "t": ctx.tenant_id,
                    "i": instrument_id,
                    "sv": SEGMENTATION_VERSION,
                    "src": found.text_source,
                    "st": found.status,
                    "c": found.confidence,
                    "n": len(found.clauses),
                    "h": found.layer_sha256,
                },
            ),
        )
        ids: dict[str, UUID] = {}
        for clause in found.clauses:
            ids[clause.label] = cast(
                UUID,
                await tx.session.scalar(
                    repo.NEW_CLAUSE,
                    {
                        "t": ctx.tenant_id,
                        "s": segmentation_id,
                        "label": clause.label,
                        "heading": clause.heading,
                        "ordinal": clause.ordinal,
                        "parent": ids.get(clause.parent) if clause.parent else None,
                        "pf": clause.page_from,
                        "pt": clause.page_to,
                        "regions": json.dumps(clause.regions()),
                        "h": clause.text_sha256(),
                        "by": None,
                    },
                ),
            )
        await tx.session.execute(repo.SUPERSEDE_INTERPRETATION, {"w": return_id})
        await tx.session.execute(
            repo.NEW_INTERPRETATION,
            {
                "t": ctx.tenant_id,
                "e": ret.engagement_id,
                "w": return_id,
                "i": instrument_id,
                "s": segmentation_id,
            },
        )
        if previous is not None:
            await move_clause_citations(tx, previous.id, instrument_id)
        target = Target("governing_instrument", instrument_id)
        tx.record("instrument.attached", target=target, after=Ref(clauses=len(found.clauses)))
        tx.record("instrument.segmented", target=target)  # a Ref carries no status words


# --- clauses (AC-1.3) ---------------------------------------------------------------------------


async def _instrument_scope(ctx: AuthContext, instrument_id: UUID, action: str) -> UUID:
    """The instrument's entity, authorised on one of the entity's fiduciary returns."""
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(repo.INSTRUMENT_BY_ID, {"i": instrument_id})).first()
        engagements = (
            list(await session.scalars(repo.RETURN_OF_ENTITY, {"e": row.client_entity_id}))
            if row is not None
            else []
        )
    for engagement_id in engagements:
        try:
            await _authorised(ctx, engagement_id, action)
            # The row was found above, so it is not None.
            return cast(UUID, row.client_entity_id)  # type: ignore[union-attr] -- found above
        except (Forbidden, NotFound):
            continue
    raise NotFound("governing_instrument")


def _clause_out(
    r: Row[Any],  # Any: a raw text() row of tax_instrument_clauses
) -> InstrumentClauseOut:
    stored: object = r.regions
    regions = cast(
        list[dict[str, Any]],  # Any: stored jsonb regions
        stored if isinstance(stored, list) else json.loads(str(stored)),
    )
    return InstrumentClauseOut(
        id=r.id,
        label=r.label,
        heading=r.heading,
        ordinal=r.ordinal,
        parent_clause_id=r.parent_clause_id,
        page_from=r.page_from,
        page_to=r.page_to,
        regions=[ClauseRegionOut(page=g["page"], bbox=g["bbox"]) for g in regions],
        text_sha256=r.text_sha256,
    )


async def clauses(ctx: AuthContext, instrument_id: UUID) -> InstrumentClausesOut:
    await _instrument_scope(ctx, instrument_id, "instrument.read")
    async with tenant_session(ctx.tenant) as session:
        seg = (await session.execute(repo.SEGMENTATION, {"i": instrument_id})).first()
        if seg is None:
            raise NotFound("instrument_segmentation")
        rows = list((await session.execute(repo.CLAUSES, {"s": seg.id})).all())
    return InstrumentClausesOut(
        instrument_id=instrument_id,
        segmentation_id=seg.id,
        status=seg.status,
        clauses=[_clause_out(r) for r in rows],
    )


async def mark_clause(
    ctx: AuthContext, instrument_id: UUID, body: ClauseMarkIn
) -> InstrumentClauseOut:
    """A person marks a clause while the code segmentation `needs_review` (AC-1.3). The text hash
    is the words inside the regions, read from the word layer."""
    _human(ctx, "instrument.attach")
    await _instrument_scope(ctx, instrument_id, "instrument.attach")
    async with tenant_session(ctx.tenant) as session:
        seg = (await session.execute(repo.SEGMENTATION, {"i": instrument_id})).first()
        version = await session.scalar(
            text("SELECT evidence_version_id FROM governing_instruments WHERE id = :i"),
            {"i": instrument_id},
        )
    if seg is None or version is None:
        raise NotFound("instrument_segmentation")
    if seg.status != "needs_review":
        raise SegmentationFinal(facts={"status": seg.status})
    words = _words_in(await version_word_layers(ctx.tenant, version), body.regions)
    regions = [{"page": r.page, "bbox": [round(v, 2) for v in r.bbox]} for r in body.regions]
    async with uow(ctx.tenant) as tx:
        clause_id = await tx.session.scalar(
            repo.NEW_CLAUSE,
            {
                "t": ctx.tenant_id,
                "s": seg.id,
                "label": body.label,
                "heading": body.heading,
                "ordinal": seg.clause_count,
                "parent": body.parent_clause_id,
                "pf": min(r.page for r in body.regions),
                "pt": max(r.page for r in body.regions),
                "regions": json.dumps(regions),
                "h": hashlib.sha256(words.encode("utf-8")).hexdigest(),
                "by": ctx.user_id,
            },
        )
        tx.record(
            "instrument_clause.marked", target=Target("instrument_clause", cast(UUID, clause_id))
        )
        row = (
            await tx.session.execute(
                text(repo.CLAUSES.text.replace("WHERE segmentation_id = :s", "WHERE id = :c")),
                {"c": clause_id},
            )
        ).first()
    if row is None:
        raise NotFound("instrument_clause")
    return _clause_out(row)


def _words_in(
    layers: Sequence[Any],  # Any: evidence word layers, duck-typed
    regions: Sequence[Any],  # Any: stored clause regions, duck-typed
) -> str:
    """The words whose centres fall inside the regions, in reading order."""
    picked: list[str] = []
    for region in regions:
        x0, top, x1, bottom = region.bbox
        for page in layers:
            if page.page != region.page:
                continue
            for w in sorted(page.words, key=lambda w: (w.top, w.x0)):
                cx, cy = (w.x0 + w.x1) / 2, (w.top + w.bottom) / 2
                if x0 <= cx <= x1 and top <= cy <= bottom:
                    picked.append(w.text)
    return " ".join(picked)


# --- determinations (AC-1.6, AC-3.1 to AC-3.3) --------------------------------------------------


async def _cited(
    ctx: AuthContext, engagement_id: UUID, key: str, citation_ids: Sequence[UUID]
) -> None:
    """AC-3.1: a governed key needs at least one citation, and every one verified and live."""
    if key in CLAUSE_GOVERNED and not citation_ids:
        raise UncitedChange(facts={"key": key})
    if citation_ids:
        supported = await supported_citations(ctx.tenant, engagement_id, list(citation_ids))
        if set(citation_ids) - supported:
            raise UncitedChange(facts={"key": key})


async def _content_hash(session: AsyncSession, interpretation_id: UUID) -> str:
    rows = [
        {
            "key": r.key,
            "seq": r.seq,
            "value": r.value_code,
            "citations": sorted(map(str, r.citation_ids)),
        }
        for r in (await session.execute(repo.HASH_ROWS, {"i": interpretation_id})).all()
    ]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()


async def _write_version(
    ctx: AuthContext,
    interpretation_id: UUID,
    key: str,
    seq: int,
    value_code: str,
    value_text: str,
    citation_ids: Sequence[UUID],
    reason: str | None,
) -> UUID:
    value = await seal(ctx.tenant_id, value_text.encode(), _VALUE_AAD)
    sealed_reason = (
        await seal(ctx.tenant_id, reason.encode(), _REASON_AAD) if reason is not None else None
    )
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            repo.NEW_DETERMINATION, {"t": ctx.tenant_id, "i": interpretation_id, "k": key}
        )
        determination = cast(
            UUID,
            await tx.session.scalar(repo.DETERMINATION_ID, {"i": interpretation_id, "k": key}),
        )
        await tx.session.execute(
            repo.NEW_VERSION,
            {
                "t": ctx.tenant_id,
                "d": determination,
                "k": key,
                "seq": seq,
                "code": value_code,
                "value": value,
                "rationale": None,
                "citations": list(citation_ids),
                "u": ctx.user_id,
                "reason": sealed_reason,
            },
        )
        before = (await tx.session.execute(repo.BEFORE_ADOPT, {"i": interpretation_id})).first()
        await tx.session.execute(
            repo.ADOPT,
            {"i": interpretation_id, "h": await _content_hash(tx.session, interpretation_id)},
        )
        if before is not None and before.status != "adopted":
            tx.emit(
                InstrumentInterpretationAdopted(
                    interpretation_id=interpretation_id,
                    work_item_id=before.work_item_id,
                    engagement_id=before.engagement_id,
                    by_user=ctx.user_id,
                )
            )
        tx.record(
            "instrument_determination.recorded",
            target=Target("instrument_determination", determination),
            after=Ref(seq=seq),  # a Ref carries no text (the key)
        )
    return determination


async def record_determination(
    ctx: AuthContext, return_id: UUID, body: DeterminationRecordIn
) -> InstrumentDeterminationOut:
    """The agents-off path (AC-1.6): the first version of a key, by a person."""
    _human(ctx, "instrument_determination.edit")
    ret = await _return(ctx.tenant, return_id)
    await _authorised(ctx, ret.engagement_id, "instrument_determination.edit")
    async with tenant_session(ctx.tenant) as session:
        interp = (await session.execute(repo.INTERPRETATION, {"w": return_id})).first()
        existing = (
            await session.scalar(repo.DETERMINATION_ID, {"i": interp.id, "k": body.key})
            if interp is not None
            else None
        )
    if interp is None:
        raise NotFound("instrument_interpretation")
    if interp.status == "approved":
        raise InterpretationLocked(facts={"interpretation_id": str(interp.id)})
    if existing is not None:
        raise VersionConflict(facts={"key": body.key})  # recorded already: edit it instead
    await _cited(ctx, ret.engagement_id, body.key, body.citation_ids)
    determination = await _write_version(
        ctx, interp.id, body.key, 1, body.value_code, body.value_text, body.citation_ids, body.note
    )
    return await _determination_out(ctx, return_id, determination)


async def edit_determination(
    ctx: AuthContext, determination_id: UUID, body: DeterminationEditIn
) -> InstrumentDeterminationOut:
    """A new version with a reason (AC-3.2); the version read must be the latest (AC-3.3)."""
    _human(ctx, "instrument_determination.edit")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(repo.DETERMINATION_OF, {"d": determination_id})).first()
    if row is None:
        raise NotFound("instrument_determination")
    await _authorised(ctx, row.engagement_id, "instrument_determination.edit")
    if row.status == "approved":
        raise InterpretationLocked(facts={"interpretation_id": str(row.interpretation_id)})
    if row.seq != body.expected_version:
        raise VersionConflict(facts={"version": int(row.seq or 0)})
    await _cited(ctx, row.engagement_id, row.key, body.citation_ids)
    await _write_version(
        ctx,
        row.interpretation_id,
        row.key,
        int(row.seq) + 1,
        body.value_code,
        body.value_text,
        body.citation_ids,
        body.reason,
    )
    return await _determination_out(ctx, row.work_item_id, determination_id)


async def _determination_out(
    ctx: AuthContext, return_id: UUID, determination_id: UUID
) -> InstrumentDeterminationOut:
    read = await instrument_read(ctx, return_id)
    found = next((d for d in read.determinations if d.id == determination_id), None)
    if found is None:
        raise NotFound("instrument_determination")
    return found


# --- reopen (AC-5.2) and the L3 lock (AC-4.2) ---------------------------------------------------


async def reopen(
    ctx: AuthContext, interpretation_id: UUID, body: InterpretationReopenIn
) -> InstrumentInterpretationOut:
    _human(ctx, "instrument_interpretation.reopen")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(repo.INTERPRETATION_BY_ID, {"i": interpretation_id})).first()
    if row is None:
        raise NotFound("instrument_interpretation")
    await _authorised(ctx, row.engagement_id, "instrument_interpretation.reopen")
    if row.status != "approved":
        raise NotApproved(facts={"status": row.status})
    reason = await seal(ctx.tenant_id, body.reason.strip().encode(), _REOPEN_AAD)
    async with uow(ctx.tenant) as tx:
        if await tx.session.scalar(repo.REOPEN, {"i": interpretation_id, "r": reason}) is None:
            raise NotApproved(facts={"status": "changed"})
        tx.record(
            "instrument_interpretation.reopened",
            target=Target("instrument_interpretation", interpretation_id),
        )
        tx.emit(
            InstrumentInterpretationReopened(
                interpretation_id=interpretation_id, engagement_id=row.engagement_id
            )
        )
    async with tenant_session(ctx.tenant) as session:
        fresh = (await session.execute(repo.INTERPRETATION, {"w": row.work_item_id})).first()
    if fresh is None:
        raise NotFound("instrument_interpretation")
    return await _interpretation_out(ctx.tenant, fresh)


async def on_sign_off_recorded(event: OutboxEvent) -> None:
    """AC-4.2: an L3 sign-off on the interpretation approves and locks it (all seven
    determinations with it). Idempotent: a locked or superseded interpretation is left alone."""
    p = event.payload
    if p.get("target_type") != TARGET or p.get("level") != 3:
        return
    target = p.get("target_id")
    if not isinstance(target, str):
        return
    tenant = TenantContext(event.tenant_id, "system", "tax:instrument_lock")
    async with uow(tenant) as tx:
        engagement = await tx.session.scalar(repo.LOCK, {"i": UUID(target)})
        if engagement is not None:
            tx.record("instrument_interpretation.approved", target=Target(TARGET, UUID(target)))
            tx.emit(
                InstrumentInterpretationApproved(
                    interpretation_id=UUID(target), engagement_id=cast(UUID, engagement)
                )
            )


# --- the reviewable (DEC-84: L1 and L3) ---------------------------------------------------------


async def interpretation_reviewables(
    tenant: TenantContext, engagement_id: UUID
) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = list((await session.execute(repo.REVIEWABLES, {"e": engagement_id})).all())
    return [
        Reviewable(
            TARGET,
            r.id,
            f"instrument:{r.work_item_id}",
            "Instrument interpretation",
            r.content_hash or "0" * 64,
            r.content_hash is not None,
        )
        for r in rows
    ]


async def interpretation_facts(tenant: TenantContext, target_id: UUID) -> ReviewableFacts | None:
    async with tenant_session(tenant) as session:
        r = (await session.execute(repo.REVIEWABLE, {"i": target_id})).first()
    if r is None:
        return None
    keys = int(r.keys or 0)
    return ReviewableFacts(
        target_type=TARGET,
        target_id=r.id,
        engagement_id=r.engagement_id,
        content_hash=r.content_hash or "0" * 64,
        version_no=r.version_no,
        preparer_user_ids=frozenset(r.preparers or ()),
        required_levels=LEVELS,
        locked=r.status == "approved",
        label="Instrument interpretation",
        work_item_id=r.work_item_id,
        incomplete_count=len(get_args(DeterminationKey)) - keys,
    )


def register() -> None:
    register_reviewable(TARGET, interpretation_reviewables)
    register_reviewable_facts(TARGET, interpretation_facts)


__all__ = [
    "attach",
    "clauses",
    "edit_determination",
    "instrument_read",
    "mark_clause",
    "on_sign_off_recorded",
    "record_determination",
    "register",
    "reopen",
]


# Public names for the trust and estate services (T-07-T16, T22).
return_of = _return
authorised_on = _authorised
