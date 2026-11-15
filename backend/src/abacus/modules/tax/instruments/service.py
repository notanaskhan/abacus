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


_RETURN: Final = text(
    "SELECT work_item_id, engagement_id, client_entity_id, form, tax_year FROM tax_returns "
    "WHERE work_item_id = :r"
)


async def _return(tenant: TenantContext, return_id: UUID) -> _Return:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_RETURN, {"r": return_id})).first()
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

_PROFILE: Final = text(
    "SELECT fiduciary_kind, agreement_date, revocable, irrevocable_since, settlor_name_sealed, "
    "settlor_died_year, residency_state, state_form FROM trust_profiles "
    "WHERE client_entity_id = :e"
)
_INSTRUMENT: Final = text(
    "SELECT id, evidence_version_id, supersedes_instrument_id, attached_by, attached_at "
    "FROM governing_instruments WHERE client_entity_id = :e "
    "AND NOT EXISTS (SELECT 1 FROM governing_instruments n WHERE n.supersedes_instrument_id = "
    "governing_instruments.id) ORDER BY attached_at DESC LIMIT 1"
)
_SEGMENTATION: Final = text(
    "SELECT id, status, text_source, confidence, clause_count FROM instrument_segmentations "
    "WHERE instrument_id = :i ORDER BY created_at DESC LIMIT 1"
)
_INTERPRETATION: Final = text(
    "SELECT id, status, scenario, read_run_id, version_no, content_hash, locked_at, row_version, "
    "instrument_id, segmentation_id FROM instrument_interpretations "
    "WHERE work_item_id = :w AND superseded_at IS NULL"
)
_DETERMINATIONS: Final = text(
    "SELECT d.id, d.key, v.seq, v.value_code, v.value_text_sealed, v.rationale_ref, "
    "v.citation_ids, v.set_by_kind, v.set_by_id, v.suggestion_id "
    "FROM instrument_determinations d JOIN LATERAL (SELECT * FROM "
    "instrument_determination_versions x WHERE x.determination_id = d.id "
    "ORDER BY x.seq DESC LIMIT 1) v ON true WHERE d.interpretation_id = :i ORDER BY d.key"
)
_CLAUSE_LABELS: Final = text(
    "SELECT c.id, c.label FROM instrument_clauses c WHERE c.segmentation_id = :s"
)


async def _profile(session: AsyncSession, tenant: TenantContext, entity: UUID) -> TrustProfileOut:
    row = (await session.execute(_PROFILE, {"e": entity})).first()
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
    session: AsyncSession, tenant: TenantContext, interpretation: Row[Any], locked: bool
) -> list[InstrumentDeterminationOut]:
    rows = list((await session.execute(_DETERMINATIONS, {"i": interpretation.id})).all())
    labels = {
        r.id: r.label
        for r in (await session.execute(_CLAUSE_LABELS, {"s": interpretation.segmentation_id}))
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
    """Citation → clause id, for `instrument_clause` citations (the locator names the clause)."""
    if not ids:
        return {}
    rows = await session.execute(
        text("SELECT id, locator FROM citations WHERE id = ANY(:ids) AND kind = :k"),
        {"ids": list(ids), "k": CLAUSE_KIND},
    )
    out: dict[UUID, UUID] = {}
    for citation_id, locator in rows.all():
        held = cast(
            dict[str, object], locator if isinstance(locator, dict) else json.loads(locator)
        )
        try:
            out[citation_id] = UUID(str(held.get("clause_id")))
        except ValueError:
            continue
    return out


async def instrument_read(ctx: AuthContext, return_id: UUID) -> InstrumentOut:
    ret = await _return(ctx.tenant, return_id)
    await _authorised(ctx, ret.engagement_id, "instrument.read")
    async with tenant_session(ctx.tenant) as session:
        profile = await _profile(session, ctx.tenant, ret.client_entity_id)
        instrument = (await session.execute(_INSTRUMENT, {"e": ret.client_entity_id})).first()
        segmentation = (
            (await session.execute(_SEGMENTATION, {"i": instrument.id})).first()
            if instrument is not None
            else None
        )
        interp = (await session.execute(_INTERPRETATION, {"w": return_id})).first()
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
    tenant: TenantContext, interp: Row[Any]
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

_NEW_PROFILE: Final = text(
    "INSERT INTO trust_profiles (client_entity_id, tenant_id, fiduciary_kind, created_by) "
    "VALUES (:e, :t, :k, :u) ON CONFLICT (client_entity_id) DO NOTHING"
)
_NEW_INSTRUMENT: Final = text(
    "INSERT INTO governing_instruments (tenant_id, client_entity_id, evidence_version_id, "
    "supersedes_instrument_id, attached_by) VALUES (:t, :e, :v, :s, :u) RETURNING id"
)
_NEW_SEGMENTATION: Final = text(
    "INSERT INTO instrument_segmentations (tenant_id, instrument_id, segmentation_version, "
    "text_source, status, confidence, clause_count, layer_sha256) "
    "VALUES (:t, :i, :sv, :src, :st, :c, :n, :h) RETURNING id"
)
_NEW_CLAUSE: Final = text(
    "INSERT INTO instrument_clauses (tenant_id, segmentation_id, label, heading, ordinal, "
    "parent_clause_id, page_from, page_to, regions, text_sha256, marked_by) VALUES (:t, :s, "
    ":label, :heading, :ordinal, :parent, :pf, :pt, CAST(:regions AS jsonb), :h, :by) RETURNING id"
)
_SUPERSEDE_INTERPRETATION: Final = text(
    "UPDATE instrument_interpretations SET superseded_at = abacus_now(), "
    "row_version = row_version + 1 WHERE work_item_id = :w AND superseded_at IS NULL"
)
_NEW_INTERPRETATION: Final = text(
    "INSERT INTO instrument_interpretations (tenant_id, engagement_id, work_item_id, "
    "instrument_id, segmentation_id) VALUES (:t, :e, :w, :i, :s) RETURNING id"
)


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
            _NEW_PROFILE,
            {
                "e": ret.client_entity_id,
                "t": ctx.tenant_id,
                "u": ctx.user_id,
                "k": "estate" if ret.form == "706" else "trust",
            },
        )
        previous = (await tx.session.execute(_INSTRUMENT, {"e": ret.client_entity_id})).first()
        instrument_id = cast(
            UUID,
            await tx.session.scalar(
                _NEW_INSTRUMENT,
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
                _NEW_SEGMENTATION,
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
                    _NEW_CLAUSE,
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
        await tx.session.execute(_SUPERSEDE_INTERPRETATION, {"w": return_id})
        await tx.session.execute(
            _NEW_INTERPRETATION,
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
        tx.record("instrument.segmented", target=target, after=Ref(status=found.status))


# --- clauses (AC-1.3) ---------------------------------------------------------------------------

_INSTRUMENT_BY_ID: Final = text(
    "SELECT g.id, g.client_entity_id FROM governing_instruments g WHERE g.id = :i"
)
_CLAUSES: Final = text(
    "SELECT id, label, heading, ordinal, parent_clause_id, page_from, page_to, regions, "
    "text_sha256 FROM instrument_clauses WHERE segmentation_id = :s ORDER BY ordinal"
)
_RETURN_OF_ENTITY: Final = text(
    "SELECT engagement_id FROM tax_returns WHERE client_entity_id = :e AND form IN ('1041', '706')"
)


async def _instrument_scope(ctx: AuthContext, instrument_id: UUID, action: str) -> UUID:
    """The instrument's entity, authorised on one of the entity's fiduciary returns."""
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_INSTRUMENT_BY_ID, {"i": instrument_id})).first()
        engagements = (
            list(await session.scalars(_RETURN_OF_ENTITY, {"e": row.client_entity_id}))
            if row is not None
            else []
        )
    for engagement_id in engagements:
        try:
            await _authorised(ctx, engagement_id, action)
            return cast(UUID, row.client_entity_id)  # type: ignore[union-attr]
        except (Forbidden, NotFound):
            continue
    raise NotFound("governing_instrument")


def _clause_out(r: Row[Any]) -> InstrumentClauseOut:
    stored: object = r.regions
    regions = cast(
        list[dict[str, Any]], stored if isinstance(stored, list) else json.loads(str(stored))
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
        seg = (await session.execute(_SEGMENTATION, {"i": instrument_id})).first()
        if seg is None:
            raise NotFound("instrument_segmentation")
        rows = list((await session.execute(_CLAUSES, {"s": seg.id})).all())
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
        seg = (await session.execute(_SEGMENTATION, {"i": instrument_id})).first()
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
            _NEW_CLAUSE,
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
                text(_CLAUSES.text.replace("WHERE segmentation_id = :s", "WHERE id = :c")),
                {"c": clause_id},
            )
        ).first()
    if row is None:
        raise NotFound("instrument_clause")
    return _clause_out(row)


def _words_in(layers: Sequence[Any], regions: Sequence[Any]) -> str:
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

_DETERMINATION_OF: Final = text(
    "SELECT d.id, d.key, d.interpretation_id, i.work_item_id, i.engagement_id, i.status, "
    "(SELECT max(seq) FROM instrument_determination_versions v WHERE v.determination_id = d.id) "
    "AS seq FROM instrument_determinations d JOIN instrument_interpretations i "
    "ON i.id = d.interpretation_id WHERE d.id = :d"
)
_NEW_DETERMINATION: Final = text(
    "INSERT INTO instrument_determinations (tenant_id, interpretation_id, key) "
    "VALUES (:t, :i, :k) ON CONFLICT (interpretation_id, key) DO NOTHING"
)
_DETERMINATION_ID: Final = text(
    "SELECT id FROM instrument_determinations WHERE interpretation_id = :i AND key = :k"
)
_NEW_VERSION: Final = text(
    "INSERT INTO instrument_determination_versions (tenant_id, determination_id, key, seq, "
    "value_code, value_text_sealed, rationale_ref, citation_ids, set_by_kind, set_by_id, "
    "reason_sealed) VALUES (:t, :d, :k, :seq, :code, :value, :rationale, :citations, 'human', "
    ":u, :reason)"
)
_ADOPT: Final = text(
    "UPDATE instrument_interpretations SET status = 'adopted', version_no = version_no + 1, "
    "content_hash = :h, row_version = row_version + 1 WHERE id = :i"
)
_HASH_ROWS: Final = text(
    "SELECT d.key, v.seq, v.value_code, v.citation_ids FROM instrument_determinations d "
    "JOIN LATERAL (SELECT * FROM instrument_determination_versions x WHERE x.determination_id "
    "= d.id ORDER BY x.seq DESC LIMIT 1) v ON true WHERE d.interpretation_id = :i ORDER BY d.key"
)


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
        for r in (await session.execute(_HASH_ROWS, {"i": interpretation_id})).all()
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
            _NEW_DETERMINATION, {"t": ctx.tenant_id, "i": interpretation_id, "k": key}
        )
        determination = cast(
            UUID, await tx.session.scalar(_DETERMINATION_ID, {"i": interpretation_id, "k": key})
        )
        await tx.session.execute(
            _NEW_VERSION,
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
        await tx.session.execute(
            _ADOPT,
            {"i": interpretation_id, "h": await _content_hash(tx.session, interpretation_id)},
        )
        tx.record(
            "instrument_determination.recorded",
            target=Target("instrument_determination", determination),
            after=Ref(key=key, seq=seq),
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
        interp = (await session.execute(_INTERPRETATION, {"w": return_id})).first()
        existing = (
            await session.scalar(_DETERMINATION_ID, {"i": interp.id, "k": body.key})
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
        row = (await session.execute(_DETERMINATION_OF, {"d": determination_id})).first()
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

_INTERPRETATION_BY_ID: Final = text(
    "SELECT id, engagement_id, work_item_id, status FROM instrument_interpretations WHERE id = :i"
)
_REOPEN: Final = text(
    "UPDATE instrument_interpretations SET status = 'reopened', locked_at = NULL, "
    "reopen_reason_sealed = :r, version_no = version_no + 1, row_version = row_version + 1 "
    "WHERE id = :i AND status = 'approved' RETURNING id"
)
_LOCK: Final = text(
    "UPDATE instrument_interpretations SET status = 'approved', locked_at = abacus_now(), "
    "row_version = row_version + 1 WHERE id = :i AND status IN ('adopted', 'proposed') "
    "AND superseded_at IS NULL RETURNING id"
)


async def reopen(
    ctx: AuthContext, interpretation_id: UUID, body: InterpretationReopenIn
) -> InstrumentInterpretationOut:
    _human(ctx, "instrument_interpretation.reopen")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_INTERPRETATION_BY_ID, {"i": interpretation_id})).first()
    if row is None:
        raise NotFound("instrument_interpretation")
    await _authorised(ctx, row.engagement_id, "instrument_interpretation.reopen")
    if row.status != "approved":
        raise NotApproved(facts={"status": row.status})
    reason = await seal(ctx.tenant_id, body.reason.strip().encode(), _REOPEN_AAD)
    async with uow(ctx.tenant) as tx:
        if await tx.session.scalar(_REOPEN, {"i": interpretation_id, "r": reason}) is None:
            raise NotApproved(facts={"status": "changed"})
        tx.record(
            "instrument_interpretation.reopened",
            target=Target("instrument_interpretation", interpretation_id),
        )
    async with tenant_session(ctx.tenant) as session:
        fresh = (await session.execute(_INTERPRETATION, {"w": row.work_item_id})).first()
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
        if await tx.session.scalar(_LOCK, {"i": UUID(target)}) is not None:
            tx.record("instrument_interpretation.approved", target=Target(TARGET, UUID(target)))


# --- the reviewable (DEC-84: L1 and L3) ---------------------------------------------------------

_REVIEWABLES: Final = text(
    "SELECT i.id, i.content_hash, i.version_no, i.work_item_id, i.status FROM "
    "instrument_interpretations i WHERE i.engagement_id = :e AND i.superseded_at IS NULL"
)
_REVIEWABLE: Final = text(
    "SELECT i.id, i.engagement_id, i.work_item_id, i.content_hash, i.version_no, i.status, "
    "(SELECT array_agg(DISTINCT v.set_by_id) FROM instrument_determinations d "
    "JOIN instrument_determination_versions v ON v.determination_id = d.id "
    "WHERE d.interpretation_id = i.id AND v.set_by_kind = 'human') AS preparers, "
    "(SELECT count(*) FROM instrument_determinations d WHERE d.interpretation_id = i.id) AS keys "
    "FROM instrument_interpretations i WHERE i.id = :i"
)


async def interpretation_reviewables(
    tenant: TenantContext, engagement_id: UUID
) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = list((await session.execute(_REVIEWABLES, {"e": engagement_id})).all())
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
        r = (await session.execute(_REVIEWABLE, {"i": target_id})).first()
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
