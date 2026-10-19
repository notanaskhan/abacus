"""Results, support, the conclusion, and the signed workpaper (SPEC-037 AC-4 to AC-6; TASK-084;
ADR-131).

People record a result on each selected entry (appended; the newest counts), link evidence the
engagement holds, or ask the client for support through an ordinary request. The preparer signs
the current state as ready, which makes a numbered version holding exactly what it includes and
the SHA-256 of its rendered content (D1); another person signs that version reviewed while
nothing has changed. A download re-renders a version and checks its fingerprint.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import check_facts, engagement_label, get_ref, lock_ref
from abacus.modules.evidence.api import evidence_versions_for
from abacus.modules.fieldwork.models import (
    EngagementMateriality,
    ItemResult,
    Procedure,
    SelectionRow,
    WorkpaperVersion,
)
from abacus.modules.fieldwork.repository import (
    all_items,
    get_conclusion,
    get_item,
    get_population,
    get_procedure,
    get_selection,
    insert_conclusion,
    insert_result,
    insert_signature,
    insert_support_request,
    insert_version,
    newest_conclusion,
    newest_materiality,
    newest_results,
    newest_selection,
    results_by_id,
    rule_counts,
    signatures_of,
    support_request_ids,
    support_requested,
    workpaper_versions,
)
from abacus.modules.fieldwork.workpaper import Row, Signature, Workpaper, render_workpaper
from abacus.modules.identity.api import AuthContext, authorise, engagement_role_of, engagement_team
from abacus.modules.requests.api import NewRequestItem, add_request_item, read_item_versions
from abacus.modules.sampling.api import RULES

RESULTS: Final = ("supported", "exception", "not_tested")
SUPPORT_AREA: Final = "Journal entries"
_PARAMETER_LABELS: Final = (
    ("threshold_percent", "Threshold (% of performance materiality)"),
    ("round_unit", "Round amount unit"),
    ("window_days", "Days before year end"),
    ("rare_count", "Rare account: fewer postings than"),
    ("keywords", "Flagged words"),
    ("manual_kinds_extra", "Extra manual entry types"),
    ("random_count", "Random entries"),
)


class ResultInvalid(DomainInvalid):
    """An exception needs a note, and not tested a reason; evidence must be this engagement's."""

    code = "result_invalid"


class NotReadyToSign(DomainConflict):
    """Every selected entry needs a result, and the procedure a conclusion."""

    code = "workpaper_incomplete"


class AlreadySigned(DomainConflict):
    code = "workpaper_already_signed"


class NothingToReview(DomainConflict):
    """No ready version, or it's already reviewed."""

    code = "workpaper_not_ready"


class ChangedSinceReady(DomainConflict):
    """Something changed after the preparer signed: sign as ready again first."""

    code = "workpaper_changed"


class OwnWork(DomainConflict):
    """ADR-131: the reviewer isn't the preparer."""

    code = "reviewer_is_preparer"


class FingerprintMismatch(DomainConflict):
    """A signed version no longer renders to the bytes that were signed."""

    code = "workpaper_fingerprint_mismatch"


async def _procedure(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID) -> Procedure:
    async with tenant_session(ctx.tenant) as session:
        found = await get_procedure(session, procedure_id)
    if found is None or found.engagement_id != engagement_id:
        raise NotFound("procedure")
    return found


async def _current_selection(ctx: AuthContext, procedure_id: UUID) -> SelectionRow:
    async with tenant_session(ctx.tenant) as session:
        found = await newest_selection(session, procedure_id)
    if found is None:
        raise NotFound("selection")
    return found


# --- Results and support (AC-4) ------------------------------------------------------------------


async def record_result(
    ctx: AuthContext,
    engagement_id: UUID,
    procedure_id: UUID,
    item_id: UUID,
    *,
    result: str,
    note: str | None,
    evidence_ids: Sequence[UUID],
) -> None:
    note = (note or "").strip() or None
    if result not in RESULTS or (result != "supported" and note is None):
        raise ResultInvalid(str(item_id))
    if evidence_ids:
        held = {v.id for v in await evidence_versions_for(ctx, engagement_id)}
        if not set(evidence_ids) <= held:
            raise ResultInvalid(str(item_id))
    await _procedure(ctx, engagement_id, procedure_id)
    selection = await _current_selection(ctx, procedure_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "procedure.run", ref.resource())
        item = await get_item(tx.session, item_id)
        if item is None or item.selection_id != selection.id:
            raise NotFound("selected_item")
        await insert_result(
            tx.session,
            tenant_id=ctx.tenant_id,
            selected_item_id=item_id,
            result=result,
            note=note[:2000] if note else None,
            evidence_version_ids=list(dict.fromkeys(evidence_ids))[:20],
            recorded_by=ctx.user_id,
        )
        tx.record(
            "procedure.result_recorded",
            target=Target("selected_item", item_id),
            after=Ref(result=RESULTS.index(result), evidence=len(evidence_ids)),
        )


def support_wording(reference: str, posted_on: str, amount: Decimal) -> str:
    """AC-6: only the entry's own reference, date and amount reach the client, never its
    description (which can be internal)."""
    label = f"journal entry {reference}" if reference else "the journal entry"
    return (
        f"Support for {label} of {posted_on}, {amount:,.2f}: the approved entry and the "
        "documents behind it"
    )


async def request_support(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, item_id: UUID
) -> UUID:
    """An ordinary request to the client for one entry's support, linked to the entry."""
    await _procedure(ctx, engagement_id, procedure_id)
    selection = await _current_selection(ctx, procedure_id)
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.run", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        item = await get_item(session, item_id)
    if item is None or item.selection_id != selection.id:
        raise NotFound("selected_item")
    made = await add_request_item(
        ctx,
        engagement_id,
        NewRequestItem(
            support_wording(item.reference, item.posted_on.isoformat(), item.amount),
            SUPPORT_AREA,
        ),
    )
    async with uow(ctx.tenant) as tx:
        await insert_support_request(
            tx.session,
            tenant_id=ctx.tenant_id,
            selected_item_id=item_id,
            request_item_id=made.id,
            requested_by=ctx.user_id,
        )
        tx.record(
            "procedure.support_requested",
            target=Target("selected_item", item_id),
            after=Ref(request_item_id=made.id),
        )
    return made.id


async def set_conclusion(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, text: str
) -> None:
    text = text.strip()
    if not 1 <= len(text) <= 4000:
        raise ResultInvalid(str(procedure_id))
    await _procedure(ctx, engagement_id, procedure_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "procedure.run", ref.resource())
        await insert_conclusion(
            tx.session,
            tenant_id=ctx.tenant_id,
            procedure_id=procedure_id,
            text=text,
            written_by=ctx.user_id,
        )
        tx.record("procedure.concluded", target=Target("procedure", procedure_id))


# --- The workpaper (AC-5) ----------------------------------------------------------------------


@dataclass(frozen=True)
class _Inputs:
    selection: SelectionRow
    materiality: EngagementMateriality
    results: dict[UUID, ItemResult]
    conclusion_id: UUID | None
    conclusion: str


async def _inputs_now(ctx: AuthContext, procedure: Procedure) -> _Inputs | None:
    async with tenant_session(ctx.tenant) as session:
        selection = await newest_selection(session, procedure.id)
        materiality = await newest_materiality(session, procedure.engagement_id)
        if selection is None or materiality is None:
            return None
        results = await newest_results(session, selection.id)
        conclusion = await newest_conclusion(session, procedure.id)
    return _Inputs(
        selection,
        materiality,
        results,
        conclusion.id if conclusion else None,
        conclusion.text if conclusion else "",
    )


def _same(inputs: _Inputs, v: WorkpaperVersion) -> bool:
    return (
        v.selection_id == inputs.selection.id
        and v.materiality_id == inputs.materiality.id
        and v.conclusion_id == inputs.conclusion_id
        and set(v.result_ids) == {r.id for r in inputs.results.values()}
    )


async def _document(ctx: AuthContext, procedure: Procedure, inputs: _Inputs) -> Workpaper:
    label = await engagement_label(ctx.tenant, procedure.engagement_id)
    facts = await check_facts(ctx.tenant, procedure.engagement_id)
    if facts is None:
        raise NotFound("engagement")
    evidence = {
        v.id: f"{v.source} v{v.version_no}"
        for v in await evidence_versions_for(ctx, procedure.engagement_id)
    }
    async with tenant_session(ctx.tenant) as session:
        population = await get_population(session, inputs.selection.population_id)
        items = await all_items(session, inputs.selection.id)
        counts = await rule_counts(session, inputs.selection.id)
        asked = await support_requested(session, inputs.selection.id)
    if population is None or label is None:
        raise NotFound("population")
    params = inputs.selection.parameters
    stamps = [inputs.selection.created_at, inputs.materiality.created_at]
    stamps += [r.created_at for r in inputs.results.values()]
    rows: list[Row] = []
    for item in items:
        result = inputs.results.get(item.id)
        rows.append(
            Row(
                item.posted_on,
                item.kind,
                item.reference,
                item.counterparty,
                tuple(item.accounts),
                item.amount,
                tuple(item.rules),
                item.reason,
                result.result if result else None,
                result.note if result else None,
                tuple(evidence.get(e, str(e)) for e in (result.evidence_version_ids or []))
                if result
                else (),
                item.id in asked,
            )
        )

    def shown(value: object) -> str:
        if isinstance(value, list):
            return ", ".join(str(v) for v in cast(list[object], value)) or "none"
        return str(value)

    return Workpaper(
        client_name=label.client_name,
        engagement_name=label.name,
        year_end=facts.fiscal_period_end,
        overall=inputs.materiality.overall,
        performance=inputs.materiality.performance,
        trivial=inputs.materiality.trivial,
        benchmark=inputs.materiality.benchmark,
        definition=procedure.definition,
        definition_version=procedure.definition_version,
        gl_snapshot_id=str(population.gl_snapshot_id),
        entry_count=population.entry_count,
        line_count=population.line_count,
        total_debit=population.total_debit,
        total_credit=population.total_credit,
        criteria_version=inputs.selection.criteria_version,
        random_method=inputs.selection.random_method,
        seed=inputs.selection.seed,
        threshold=Decimal(str(params.get("threshold", "0"))),
        parameters=[(label_, shown(params.get(key))) for key, label_ in _PARAMETER_LABELS],
        by_rule=[(r, counts[r]) for r in RULES if r in counts],
        rows=rows,
        conclusion=inputs.conclusion,
        not_performed=("after_year_end", "entered_by"),
        stamp=max(stamps),
    )


@dataclass(frozen=True)
class SignatureView:
    kind: str
    signed_by: UUID
    name: str
    role: str
    signed_at: datetime


@dataclass(frozen=True)
class VersionView:
    version: int
    created_at: datetime
    signatures: tuple[SignatureView, ...]


@dataclass(frozen=True)
class WorkpaperState:
    status: str  # not_started | draft | ready | reviewed
    entries: int
    with_result: int
    exceptions: int
    conclusion: str
    versions: tuple[VersionView, ...]


async def _names(ctx: AuthContext, engagement_id: UUID) -> dict[UUID, str]:
    return {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}


async def _versions(
    ctx: AuthContext, procedure: Procedure
) -> tuple[list[WorkpaperVersion], dict[UUID, list[SignatureView]]]:
    names = await _names(ctx, procedure.engagement_id)
    async with tenant_session(ctx.tenant) as session:
        versions = list(await workpaper_versions(session, procedure.id))
        signatures = await signatures_of(session, [v.id for v in versions])
    by_version: dict[UUID, list[SignatureView]] = {}
    for g in signatures:
        by_version.setdefault(g.workpaper_version_id, []).append(
            SignatureView(
                g.kind, g.signed_by, names.get(g.signed_by, "Former member"), g.role, g.created_at
            )
        )
    return versions, by_version


async def workpaper_state(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID
) -> WorkpaperState:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    procedure = await _procedure(ctx, engagement_id, procedure_id)
    inputs = await _inputs_now(ctx, procedure)
    versions, signed = await _versions(ctx, procedure)
    views = tuple(
        VersionView(v.version, v.created_at, tuple(signed.get(v.id, []))) for v in versions
    )
    if inputs is None:
        return WorkpaperState("not_started", 0, 0, 0, "", views)
    async with tenant_session(ctx.tenant) as session:
        entries = len(await all_items(session, inputs.selection.id))
    status = "draft"
    if versions and _same(inputs, versions[-1]):
        kinds = {g.kind for g in signed.get(versions[-1].id, [])}
        status = "reviewed" if "reviewed" in kinds else "ready"
    return WorkpaperState(
        status,
        entries,
        len(inputs.results),
        sum(1 for r in inputs.results.values() if r.result == "exception"),
        inputs.conclusion,
        views,
    )


def _signatures(
    versions: list[WorkpaperVersion], signed: dict[UUID, list[SignatureView]], upto: int
) -> list[Signature]:
    found: list[Signature] = []
    for v in versions:
        number = v.version
        if number > upto:
            continue
        for g in signed.get(v.id, []):
            found.append(Signature(g.kind, g.name, g.role, g.signed_at, number))
    return found


async def sign_ready(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID) -> WorkpaperState:
    """AC-5: the preparer signs the current state, which becomes the next version."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "workpaper.sign_ready", ref.resource())
    procedure = await _procedure(ctx, engagement_id, procedure_id)
    inputs = await _inputs_now(ctx, procedure)
    if inputs is None or inputs.conclusion_id is None:
        raise NotReadyToSign(str(procedure_id))
    async with tenant_session(ctx.tenant) as session:
        entries = len(await all_items(session, inputs.selection.id))
    if len(inputs.results) < entries:
        raise NotReadyToSign(str(procedure_id))
    versions, _signed = await _versions(ctx, procedure)
    if versions and _same(inputs, versions[-1]):
        raise AlreadySigned(str(procedure_id))
    content = render_workpaper(await _document(ctx, procedure, inputs), with_signoff=False)
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id) or "firm"
    async with uow(ctx.tenant) as tx:
        locked = await lock_ref(tx, engagement_id)
        await authorise(ctx, "workpaper.sign_ready", locked.resource())
        version_id = await insert_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            procedure_id=procedure_id,
            version=len(versions) + 1,
            selection_id=inputs.selection.id,
            result_ids=sorted(r.id for r in inputs.results.values()),
            conclusion_id=inputs.conclusion_id,
            materiality_id=inputs.materiality.id,
            sha256=hashlib.sha256(content).hexdigest(),
        )
        await insert_signature(
            tx.session,
            tenant_id=ctx.tenant_id,
            workpaper_version_id=version_id,
            kind="ready",
            signed_by=ctx.user_id,
            role=str(role),
        )
        tx.record(
            "workpaper.signed_ready",
            target=Target("procedure", procedure_id),
            after=Ref(version=len(versions) + 1),
        )
    return await workpaper_state(ctx, engagement_id, procedure_id)


async def sign_reviewed(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID
) -> WorkpaperState:
    """AC-5: another person signs the latest ready version, while nothing has changed."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "workpaper.sign_reviewed", ref.resource())
    procedure = await _procedure(ctx, engagement_id, procedure_id)
    versions, signed = await _versions(ctx, procedure)
    if not versions:
        raise NothingToReview(str(procedure_id))
    latest = versions[-1]
    kinds = {g.kind: g for g in signed.get(latest.id, [])}
    if "ready" not in kinds or "reviewed" in kinds:
        raise NothingToReview(str(procedure_id))
    if kinds["ready"].signed_by == ctx.user_id:
        raise OwnWork(str(procedure_id))
    inputs = await _inputs_now(ctx, procedure)
    if inputs is None or not _same(inputs, latest):
        raise ChangedSinceReady(str(procedure_id))
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id) or "firm"
    async with uow(ctx.tenant) as tx:
        locked = await lock_ref(tx, engagement_id)
        await authorise(ctx, "workpaper.sign_reviewed", locked.resource())
        made = await insert_signature(
            tx.session,
            tenant_id=ctx.tenant_id,
            workpaper_version_id=latest.id,
            kind="reviewed",
            signed_by=ctx.user_id,
            role=str(role),
        )
        if not made:
            raise NothingToReview(str(procedure_id))
        tx.record(
            "workpaper.signed_reviewed",
            target=Target("procedure", procedure_id),
            after=Ref(version=latest.version),
        )
    return await workpaper_state(ctx, engagement_id, procedure_id)


async def workpaper_file(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, version: int | None
) -> tuple[bytes, str]:
    """The current draft, or a signed version re-rendered and checked against its fingerprint."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    procedure = await _procedure(ctx, engagement_id, procedure_id)
    versions, signed = await _versions(ctx, procedure)
    if version is None:
        inputs = await _inputs_now(ctx, procedure)
        if inputs is None:
            raise NotFound("selection")
        document = await _document(ctx, procedure, inputs)
        return render_workpaper(document, []), "journal-entry-testing-draft.xlsx"
    found = next((v for v in versions if v.version == version), None)
    if found is None:
        raise NotFound("workpaper_version")
    async with tenant_session(ctx.tenant) as session:
        selection = await get_selection(session, found.selection_id)
        results = await results_by_id(session, list(found.result_ids))
        conclusion = await get_conclusion(session, found.conclusion_id)
        materiality = await session.get(EngagementMateriality, found.materiality_id)
    if selection is None or conclusion is None or materiality is None:
        raise NotFound("workpaper_version")
    inputs = _Inputs(selection, materiality, results, conclusion.id, conclusion.text)
    document = await _document(ctx, procedure, inputs)
    content = render_workpaper(document, with_signoff=False)
    if hashlib.sha256(content).hexdigest() != found.sha256:
        raise FingerprintMismatch(str(procedure_id))
    return (
        render_workpaper(document, _signatures(versions, signed, version)),
        f"journal-entry-testing-v{version}.xlsx",
    )


# --- For the entry assessor (SPEC-037 Q4; TASK-085 D1) ------------------------------------------

MAX_DOCUMENTS: Final = 3


@dataclass(frozen=True)
class EntryFacts:
    """A selected entry as the assessor may see it, and the documents a person tied to it: the
    evidence linked on its newest result, then what fulfilled its support requests."""

    engagement_id: UUID
    procedure_id: UUID
    posted_on: str
    kind: str
    reference: str
    counterparty: str
    accounts: tuple[str, ...]
    amount: Decimal
    descriptions: tuple[str, ...]
    evidence_version_ids: tuple[UUID, ...]


async def entry_facts(tenant: TenantContext, item_id: UUID) -> EntryFacts | None:
    """For a caller that authorises `procedure.read` on the engagement it returns (None when the
    entry isn't in the tenant)."""
    async with tenant_session(tenant) as session:
        item = await get_item(session, item_id)
        if item is None:
            return None
        selection = await get_selection(session, item.selection_id)
        if selection is None:
            return None
        procedure = await get_procedure(session, selection.procedure_id)
        results = await newest_results(session, item.selection_id)
        requested = await support_request_ids(session, item_id)
    if procedure is None:
        return None
    newest = results.get(item_id)
    linked: list[UUID] = list(newest.evidence_version_ids or []) if newest is not None else []
    for request_item in requested:
        linked += await read_item_versions(tenant, request_item)
    return EntryFacts(
        procedure.engagement_id,
        procedure.id,
        item.posted_on.isoformat(),
        item.kind,
        item.reference,
        item.counterparty,
        tuple(item.accounts),
        item.amount,
        tuple(item.descriptions),
        tuple(dict.fromkeys(linked))[:MAX_DOCUMENTS],
    )


async def assessable_items(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID
) -> list[UUID]:
    """The current selection's entries with at least one document to read."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    await _procedure(ctx, engagement_id, procedure_id)
    selection = await _current_selection(ctx, procedure_id)
    async with tenant_session(ctx.tenant) as session:
        items = await all_items(session, selection.id)
    found: list[UUID] = []
    for item in items:
        facts = await entry_facts(ctx.tenant, item.id)
        if facts is not None and facts.evidence_version_ids:
            found.append(item.id)
    return found


async def selection_item_ids(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID
) -> list[UUID]:
    """The current selection's entries (none before a selection)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    await _procedure(ctx, engagement_id, procedure_id)
    async with tenant_session(ctx.tenant) as session:
        selection = await newest_selection(session, procedure_id)
        if selection is None:
            return []
        return [i.id for i in await all_items(session, selection.id)]
