"""Interim G9: the audit file archived in the firm's own tool, recorded against a final binder
export (A-01-T23; A-01 §3.5 Story 5.3; OQ-3; DEC-83, P-43, DEC-591). PROTECTED (red path).

While the firm's `assurance_release_mode` is `external`, a manager or the engagement partner
records that the file now lives in the firm's tool, naming the ready final binder export that
left Accrued and the tool's reference ("CaseWare BH-2025-031"):

- **Who.** `assurance.record_archive`: the engagement partner or a manager, with independence
  and a fresh second factor (403 `mfa_required` when stale, DEC-547), a live person's own act
  (INV-1; `assurance.archive_recorded` is on the human-only register).
- **Against what.** The audit is Released (409 `record_out_of_phase`), and the export is this
  work item's ready `final_binder` export, read FOR SHARE in this unit and current: evidence's
  `final_export_for_archive` refuses one that is not (409 `final_export_required`) or whose
  selection changed after its snapshot (409 `export_stale`, the newer event named). The table's
  insert trigger re-reads the export under the same lock (data layer).
- **What.** The insert-only row keeps the export id and its manifest SHA-256 and the reference
  sealed under the tenant key; the derived move to Archived names G9; C1's archived transition
  sets `work_items.archived_at` and archives the engagement once all its work items are, which
  makes it read-only through `authorise` (every write 403). `archive_locked_at` stays NULL: no
  seal, no database immutability (A-07, P-43).

The G9 provider registered for every firm is `g9` below: SPEC-314's in-app lock or this record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance import completion
from abacus.modules.assurance.external_models import (
    ExternalArchive,
    external_archive_of,
    ref_context,
)
from abacus.modules.assurance.phase import advance_by_gate
from abacus.modules.assurance.record_auth import authorise_record, fresh_mfa_at
from abacus.modules.assurance.release import RecordOutOfPhase, require_external
from abacus.modules.engagements.api import (
    GateFact,
    archive_work_item,
    assurance_item,
    engagement_type_of,
    lock_assurance_item,
    lock_ref,
)
from abacus.modules.evidence.api import ArchiveRow, BinderSection, final_export_for_archive
from abacus.modules.identity.api import AuthContext

ACTION: Final = "assurance.record_archive"
FIRM_TOOL_REF_MAX: Final = 120


@dataclass(frozen=True)
class ArchiveRecord:
    work_item_id: UUID
    export_id: UUID
    manifest_sha256: str
    phase: str
    recorded_at: datetime


async def record_archive(
    ctx: AuthContext, work_item_id: UUID, export_id: UUID, reference: str
) -> ArchiveRecord:
    """Story 5.3: the external archive, against a ready, current final binder export."""
    text = reference.strip()
    if not text or len(text) > FIRM_TOOL_REF_MAX or "\n" in text:
        raise ValueError("firm_tool_ref")  # the contract model bounds it first (422)
    found = await assurance_item(ctx.tenant, work_item_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, found.engagement_id)
        await authorise_record(ctx, ACTION, ref.resource())
        await require_external(ctx.tenant)
        item = await lock_assurance_item(tx, work_item_id)
        if item.phase != "released":
            raise RecordOutOfPhase(facts={"phase": item.phase})
        final = await final_export_for_archive(tx, ctx.tenant, work_item_id, export_id)
        mfa_at = fresh_mfa_at(ctx)
        sealed = await seal(ctx.tenant_id, text.encode(), ref_context(work_item_id))
        row = ExternalArchive(
            work_item_id=item.work_item_id,
            tenant_id=ctx.tenant_id,
            engagement_id=item.engagement_id,
            export_id=final.export_id,
            manifest_sha256=final.manifest_sha256,
            firm_tool_ref_sealed=sealed,
            recorded_by=ctx.user_id,
            actor_kind="human",
            mfa_at=mfa_at,
        )
        tx.session.add(row)
        await advance_by_gate(tx, ctx.tenant, item.engagement_id, "archived", "G9", ctx.user_id)
        engagement_archived = await archive_work_item(
            tx, item.work_item_id, await clock.now(ctx.tenant)
        )
        tx.record(
            "assurance.archive_recorded",
            target=Target("engagement", item.engagement_id),
            after=Ref(
                work_item=item.work_item_id,
                export=final.export_id,
                manifest_sha256=final.manifest_sha256,
                as_of_seq=final.as_of_seq,
                engagement_archived=int(engagement_archived),
                mfa_at=int(mfa_at.timestamp()),
            ),
            scope=Scope(engagement_id=item.engagement_id, work_item_id=item.work_item_id),
        )
        await tx.session.refresh(row)
        return ArchiveRecord(
            item.work_item_id, final.export_id, final.manifest_sha256, "archived", row.recorded_at
        )


async def g9(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    """G9 for every firm: SPEC-314's archive lock, or the external archive record."""
    in_app = await completion.g9(tenant, engagement_id)
    if in_app.met:
        return in_app
    async with tenant_session(tenant) as session:
        recorded = await external_archive_of(session, engagement_id)
    if recorded is not None:
        return GateFact(met=True, blockers=())
    return in_app


# =================================================================================================
# In-app assembly: the archive, its nine items and the binder index (A-07-T31; A-07 F7; SPEC-644;
# DEC-3108). PROTECTED.
#
# `report.released` opens the archive (Assembling) through `evidence.api.open_archive`, with the
# documentation completion date at release + 60 and retention from the P-14 policy over the
# five-year floor. AUD-25 reads nine items computed live, never ticked by hand, and a binder index
# built by code over the file's sections (A to H, superseded versions kept). "Request lock…" is a
# senior's or above's ask of the lockers (manager, EP) once all nine hold; the lock itself and the
# seal are A-07-T37's.
# =================================================================================================

ARCHIVE_ITEMS: Final[tuple[tuple[str, str], ...]] = (
    ("workpapers_signed", "All workpapers signed"),
    ("review_notes_resolved", "Review notes resolved"),
    ("versions_handled", "Versions handled"),
    ("binder_index_complete", "Binder index complete"),
    ("final_report_filed", "Final report and deliverables filed"),
    ("governance_filed", "Governance communications filed"),
    ("independence_filed", "Independence confirmations filed"),
    ("run_logs_packaged", "Agent run logs packaged"),
    ("type_filing", "Type-specific filing confirmation"),
)
BINDER_TITLES: Final[dict[str, str]] = {
    "A": "Planning",
    "B": "Fieldwork",
    "C": "Testing",
    "D": "Completion",
    "E": "Reporting",
    "F": "Source documents",
    "G": "Agent run logs",
    "H": "Independence confirmations",
}
# AUD-02 rail rows to binder sections: by band, with the EBP test papers under C (AUD-25's "C
# Testing · Eligibility to Form 5500 tie-out"). Overview rows are not workpapers.
_BAND_LETTER: Final[dict[str, str]] = {
    "planning": "A",
    "group": "B",
    "fieldwork": "B",
    "completion": "D",
    "reporting": "E",
}
_KEY_LETTER: Final[dict[str, str]] = {
    "ebp_03": "C",
    "ebp_04": "C",
    "ebp_05": "C",
    "ebp_06": "C",
    "ebp_07": "C",
}
LOCK_REQUESTERS: Final = "archive.request_lock"


@dataclass(frozen=True)
class ArchiveItem:
    key: str
    title: str
    done: bool
    detail: str | None = None


@dataclass(frozen=True)
class ArchiveState:
    archive: ArchiveRow | None
    items: tuple[ArchiveItem, ...]
    binder: tuple[BinderSection, ...]
    days_left: int | None

    @property
    def done(self) -> int:
        return sum(1 for i in self.items if i.done)

    @property
    def checklist_sha256(self) -> str:
        import hashlib
        import json

        body = json.dumps(
            [{"key": i.key, "done": i.done} for i in self.items], separators=(",", ":")
        )
        return hashlib.sha256(body.encode()).hexdigest()


async def binder_sections(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID
) -> tuple[BinderSection, ...]:
    """A to H, computed: the work item's rail rows in the file (a row whose provider answers a
    state), the engagement's source documents with superseded versions kept, its run logs and
    its team's independence confirmations."""
    from abacus.modules.agents.api import run_log_count
    from abacus.modules.assurance.sections import registered_sections
    from abacus.modules.engagements.api import independence_cleared
    from abacus.modules.evidence.api import source_document_count
    from abacus.modules.identity.api import team_of

    papers = dict.fromkeys("ABCDE", 0)
    for section in registered_sections():
        letter = _KEY_LETTER.get(section.key) or _BAND_LETTER.get(section.band)
        if letter is None:
            continue
        try:
            state = await section.state_provider(tenant, work_item_id)
        except Exception:  # a row that cannot answer is not counted as in the file
            state = None
        if state is not None:
            papers[letter] += 1
    documents = await source_document_count(tenant, engagement_id)
    runs, _ended = await run_log_count(tenant, engagement_id)
    team = {member for member, _role in await team_of(tenant.tenant_id, engagement_id)}
    cleared = sum([1 for m in team if await independence_cleared(tenant, engagement_id, m)])
    out = [BinderSection(k, BINDER_TITLES[k], papers[k], 0, 0) for k in "ABCDE"]
    out.append(BinderSection("F", BINDER_TITLES["F"], 0, documents, 0))
    out.append(BinderSection("G", BINDER_TITLES["G"], 0, 0, runs))
    out.append(BinderSection("H", BINDER_TITLES["H"], 0, 0, 0, cleared))
    return tuple(out)


async def _items(
    tenant: TenantContext,
    engagement_id: UUID,
    work_item_id: UUID,
    binder: tuple[BinderSection, ...],
) -> tuple[ArchiveItem, ...]:
    from abacus.modules.agents.api import run_log_count
    from abacus.modules.assurance import gates as gate_providers
    from abacus.modules.assurance.release import released
    from abacus.modules.assurance.release_facts import independence
    from abacus.modules.evidence.api import archive_of, index_sha256, latest_binder_index

    try:
        blockers = await gate_providers.g5_blockers(tenant, engagement_id)
    except Exception:
        blockers = ["review_unavailable"]
    unsigned = [b for b in blockers if b.startswith("unsigned:") or b == "no_reviewables"]
    stale = [b for b in blockers if b.startswith("stale:") or b == "review_unavailable"]
    notes = [b for b in blockers if b.startswith("review_note:")]
    archive = await archive_of(tenant, work_item_id)
    latest = None if archive is None else await latest_binder_index(tenant, archive.id)
    index_current = latest is not None and index_sha256(latest[1]) == index_sha256(binder)
    done = await released(tenant, work_item_id)
    async with tenant_session(tenant) as session:
        letters = (
            await session.execute(
                text(
                    "SELECT kind, status FROM governance_communications WHERE work_item_id = :wi"
                ),
                {"wi": work_item_id},
            )
        ).all()
        filing = (
            await session.execute(
                text("SELECT status FROM filings WHERE work_item_id = :wi AND form = 'form_5500'"),
                {"wi": work_item_id},
            )
        ).first()
    open_letters = [str(r.kind) for r in letters if r.status not in ("sent", "acknowledged")]
    team = await independence(tenant, engagement_id, work_item_id)
    runs, ended = await run_log_count(tenant, engagement_id)
    ebp = (await engagement_type_of(tenant, engagement_id)) == "ebp_audit"
    type_done = (filing is not None and filing.status == "filed") if ebp else True
    return (
        ArchiveItem(
            "workpapers_signed", ARCHIVE_ITEMS[0][1], not unsigned, f"{len(unsigned)} open"
        ),
        ArchiveItem("review_notes_resolved", ARCHIVE_ITEMS[1][1], not notes, f"{len(notes)} open"),
        ArchiveItem("versions_handled", ARCHIVE_ITEMS[2][1], not stale, f"{len(stale)} stale"),
        ArchiveItem(
            "binder_index_complete",
            ARCHIVE_ITEMS[3][1],
            index_current,
            None if latest is None else f"v{latest[0]}",
        ),
        ArchiveItem(
            "final_report_filed",
            ARCHIVE_ITEMS[4][1],
            done is not None and bool(done.deliverable_ids),
        ),
        ArchiveItem(
            "governance_filed",
            ARCHIVE_ITEMS[5][1],
            bool(letters) and not open_letters,
            ",".join(open_letters) or None,
        ),
        ArchiveItem("independence_filed", ARCHIVE_ITEMS[6][1], team.met, team.value),
        ArchiveItem("run_logs_packaged", ARCHIVE_ITEMS[7][1], runs == ended, f"{ended} of {runs}"),
        ArchiveItem(
            "type_filing",
            "EFAST2 acknowledgment" if ebp else ARCHIVE_ITEMS[8][1],
            type_done,
            None if ebp else "not_applicable",
        ),
    )


async def archive_state(tenant: TenantContext, work_item_id: UUID) -> ArchiveState:
    """AUD-25's read: the archive, the nine items and the binder index, all computed now."""
    from abacus.modules.evidence.api import archive_of

    found = await assurance_item(tenant, work_item_id)
    archive = await archive_of(tenant, work_item_id)
    binder = await binder_sections(tenant, found.engagement_id, work_item_id)
    items = await _items(tenant, found.engagement_id, work_item_id, binder)
    days_left = None
    if archive is not None:
        today = await clock.today(tenant)
        days_left = (archive.documentation_completion_date - today).days
    return ArchiveState(archive, items, binder, days_left)


async def build_binder_index(ctx: AuthContext, work_item_id: UUID) -> int:
    """`POST …/archive/binder-index`: a new code-built index version (the route authorised
    `archive.build_index`). 409 `record_out_of_phase` before release."""
    from abacus.modules.evidence.api import archive_of, record_binder_index

    found = await assurance_item(ctx.tenant, work_item_id)
    archive = await archive_of(ctx.tenant, work_item_id)
    if archive is None:
        raise RecordOutOfPhase(facts={"phase": "not_released"})
    sections = await binder_sections(ctx.tenant, found.engagement_id, work_item_id)
    async with uow(ctx.tenant) as tx:
        return await record_binder_index(tx, archive, sections)


class ChecklistIncomplete(DomainConflict):
    """Not all nine items hold (`facts.open`: the item keys still open)."""

    code = "checklist_incomplete"


async def request_lock(ctx: AuthContext, work_item_id: UUID) -> ArchiveState:
    """ "Request lock…" (a senior or above): with 9 of 9, ask the lockers to lock. Records the
    request and emits `archive.lock_requested`; it never locks (A-07-T37)."""
    from abacus.modules.assurance.events import ArchiveLockRequested

    state = await archive_state(ctx.tenant, work_item_id)
    if state.archive is None:
        raise RecordOutOfPhase(facts={"phase": "not_released"})
    still = [i.key for i in state.items if not i.done]
    if still:
        raise ChecklistIncomplete(facts={"open": ",".join(still)})
    archive_id = state.archive.id
    engagement_id = state.archive.engagement_id
    async with uow(ctx.tenant) as tx:
        tx.emit(
            ArchiveLockRequested(
                archive_id=archive_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                requested_by=ctx.user_id,
            )
        )
        tx.record(
            "archive.lock_requested",
            target=Target("archive", archive_id),
            after=Ref(checklist=state.checklist_sha256),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return state


async def on_report_released(event: OutboxEvent) -> None:
    """`report.released` → the archive opens Assembling (once; a redelivery finds the row)."""
    from abacus.modules.assurance.release import released
    from abacus.modules.evidence.api import open_archive

    work_item_id = UUID(str(event.payload["work_item_id"]))
    engagement_id = UUID(str(event.payload["engagement_id"]))
    tenant = TenantContext(event.tenant_id, "system", f"archive_open:{work_item_id}")
    done = await released(tenant, work_item_id)
    if done is None:
        return
    async with uow(tenant) as tx:
        await open_archive(
            tx,
            tenant,
            engagement_id=engagement_id,
            work_item_id=work_item_id,
            release_id=done.release_id,
            released_at=done.released_at,
            release_date=done.released_at.astimezone(clock.FIRM_ZONE).date(),
            service_line="audit",  # every A-07 engagement is an attest file (P-14's audit line)
        )


SUBSCRIPTIONS: Final = {"report.released": on_report_released}
