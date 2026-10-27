"""The safeguards program (G-02-T20; SPEC-349 AC-27, AC-30; DEC-626, DEC-627). Contract:
`docs/contracts/security-center.md` §3, §4.

Behind `security_center.v1` (off: 404). Partners, firm admins and the QM owner read
(`security.read`); only the QI edits (`security.manage`, `security_admin`, fresh MFA).

- **Controls:** the Pub 4557 control definitions are platform content (`safeguards_controls`),
  imported by staff and published by a second staff member (`import_controls`,
  `publish_controls`); nothing here or in a migration holds one. A firm's status per control is
  `evidenced` or `open`; a published control the firm has no status for is open. "18 of 20
  evidenced" is `controls_evidenced` of `controls_total` over the published set.
- **The record:** QI, WISP and its approval, annual report dates, training, PTIN attestation and
  the quarterly access review, saved against `version` (409 `stale_version`). People named must be
  the firm's active staff (422 `safeguards_person_invalid`).
- **Export WISP pack (202):** a job (`wisp_packs`), audited `wisp_pack.prepared` naming the QI;
  `WispPackWorkflow` zips the WISP and the evidence its controls link, each read as the requester
  through evidence's item download (authorised, audited, fingerprint-checked), sealed in the
  exports bucket (`kernel.export_bundles`). The download is the API's own route (ADR-104).
- **Posture (AC-30):** registers `pub4557_open` (open controls of the published set).
"""

from __future__ import annotations

import json
import re
import tempfile
import zipfile
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Final, Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError

from abacus.kernel import clock
from abacus.kernel import export_bundles as bundles
from abacus.kernel._flags import SECURITY_CENTER_V1
from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.export_bundles import BundleKind
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Handler, OutboxEvent, Ref, Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    active_staff_among,
    member_context,
    names_of,
)
from abacus.modules.platform.events import WispPackRequested
from abacus.modules.platform.security_center_contract import (
    AccessReviewOut,
    GovernancePersonOut,
    SafeguardsControlIn,
    SafeguardsControlOut,
    SafeguardsIn,
    SafeguardsOut,
    WispOut,
    WispPackOut,
)
from abacus.modules.platform.workflow_types import WispPackFacts, WispPackFailure, WispPackInput
from abacus.modules.platform.workflows import WispPackWorkflow, wisp_pack_workflow_id


class _Document(Protocol):
    @property
    def content(self) -> bytes: ...
    @property
    def file_name(self) -> str: ...


DocumentReader = Callable[[AuthContext, UUID], Awaitable[_Document]]
_documents: list[DocumentReader] = []


def register_wisp_document_reader(reader: DocumentReader) -> None:
    """Evidence registers its item download (`evidence.api.latest_document`): the platform may not
    import evidence (ADR-008), and reads each document as the requester through it."""
    if _documents and _documents[0] is not reader:
        raise RuntimeError("the WISP document reader is already registered")
    _documents[:] = [reader]


SUBJECT: Final = "safeguards_program"
CONTROL: Final = "safeguards_control"
PACK: Final = "wisp_pack"
_KIND: Final[BundleKind] = "wisp-pack"
PACK_EXPIRY: Final = timedelta(days=7)
_ZIP_TIME: Final = (1980, 1, 1, 0, 0, 0)
_UNSAFE: Final = re.compile(r"[^A-Za-z0-9 ._()-]+")
_log = get_logger(__name__)


class SafeguardsStale(DomainConflict):
    """The record changed since it was read: read it again (409)."""

    code = "stale_version"


class SafeguardsPersonInvalid(DomainInvalid):
    """A person the record names is not one of the firm's active staff."""

    code = "safeguards_person_invalid"


class WispPackNotReady(DomainConflict):
    """The pack is still being prepared, or failed."""

    code = "export_not_ready"


class WispPackExpired(Exception):
    """410 `export_expired`: past its 7 days."""


class ControlSetExists(DomainConflict):
    code = "control_set_exists"


class ControlSetInvalid(DomainInvalid):
    code = "control_set_invalid"


class ControlSetSamePerson(DomainConflict):
    """A second staff member publishes the set its importer imported."""

    code = "control_set_same_person"


async def _gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, SECURITY_CENTER_V1):
        raise NotFound(SECURITY_CENTER_V1.name)


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(action, "role")


# --- platform content: the control definitions ---------------------------------------------------

_IMPORT = text("SELECT safeguards_controls_import(:version, CAST(:rows AS jsonb), :staff)")
_PUBLISH = text("SELECT safeguards_controls_publish(:version, :staff)")
_PUBLISHED = text('SELECT control_key, title, "position" FROM safeguards_controls_published()')


async def import_controls(version: int, rows: Sequence[Mapping[str, object]], staff: str) -> int:
    """Staff: a draft set of control definitions; how many rows."""
    try:
        async with platform_transaction(f"staff:{staff}") as conn:
            return int(
                (
                    await conn.execute(
                        _IMPORT, {"version": version, "rows": json.dumps(rows), "staff": staff}
                    )
                ).scalar_one()
            )
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise ControlSetExists from None
        raise ControlSetInvalid from None
    except DBAPIError:
        raise ControlSetInvalid from None


async def publish_controls(version: int, staff: str) -> int:
    """Staff: publish a draft set as a second staff member; the previous set is superseded."""
    try:
        async with platform_transaction(f"staff:{staff}") as conn:
            published = int(
                (await conn.execute(_PUBLISH, {"version": version, "staff": staff})).scalar_one()
            )
    except DBAPIError as exc:
        if getattr(getattr(exc, "orig", None), "sqlstate", None) == "42501":
            raise ControlSetSamePerson from None
        raise
    if published == 0:
        raise NotFound("safeguards_control_set")
    return published


@dataclass(frozen=True)
class _Control:
    key: str
    title: str
    position: int


async def _published(tenant: TenantContext) -> list[_Control]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_PUBLISHED)).mappings().all()
    return [_Control(str(r["control_key"]), str(r["title"]), int(r["position"])) for r in rows]


# --- the firm's record -------------------------------------------------------------------------

_PROGRAM = text(
    "SELECT qi_user_id, wisp_name, wisp_evidence_item_id, wisp_approved_by, wisp_approved_on, "
    "annual_report_last_on, annual_report_next_due_month, access_review_quarter, "
    "access_review_due_on, access_review_status, training_completed, ptin_attested, "
    "ptin_total, version, updated_by, updated_at FROM safeguards_programs"
)
_STATUSES = text(
    "SELECT control_key, status, due_on, scheduled_on, evidence_item_id "
    "FROM safeguards_control_statuses"
)

Row = Mapping[Any, Any]  # Any: an untyped database row (a RowMapping)


def _person(user: UUID | None, names: Mapping[UUID, str]) -> GovernancePersonOut | None:
    return (
        None
        if user is None
        else GovernancePersonOut(user_id=user, display_name=names.get(user, ""))
    )


def _control_out(control: _Control, status: Row | None) -> SafeguardsControlOut:
    return SafeguardsControlOut(
        control_key=control.key,
        title=control.title,
        status=status["status"] if status is not None else "open",
        due_on=cast(date | None, status["due_on"]) if status is not None else None,
        scheduled_on=cast(date | None, status["scheduled_on"]) if status is not None else None,
        evidence_item_id=(
            cast(UUID | None, status["evidence_item_id"]) if status is not None else None
        ),
    )


async def _program(tenant: TenantContext) -> tuple[Row | None, Mapping[str, Row]]:
    async with tenant_session(tenant) as session:
        program = (await session.execute(_PROGRAM)).mappings().one_or_none()
        statuses = {
            str(r["control_key"]): r for r in (await session.execute(_STATUSES)).mappings()
        }
    return program, statuses


async def open_controls(tenant: TenantContext) -> int:
    """AC-30: the posture's Pub 4557 items open, over the published set."""
    controls = await _published(tenant)
    _, statuses = await _program(tenant)
    return sum(
        1 for c in controls if (s := statuses.get(c.key)) is None or s["status"] != "evidenced"
    )


async def read(ctx: AuthContext) -> SafeguardsOut:
    """AC-27: the record, with the counts over the published controls and the open ones listed
    in their published order."""
    await _gate(ctx)
    controls = await _published(ctx.tenant)
    program, statuses = await _program(ctx.tenant)
    evidenced = [
        c
        for c in controls
        if (s := statuses.get(c.key)) is not None and s["status"] == "evidenced"
    ]
    still_open = [c for c in controls if c not in evidenced]
    people = {
        cast(UUID, program[k])
        for k in ("qi_user_id", "wisp_approved_by", "updated_by")
        if program is not None and program[k] is not None
    }
    names = await names_of(sorted(people, key=str))
    p = program or {}
    wisp = None
    if program is not None and (program["wisp_name"] or program["wisp_evidence_item_id"]):
        wisp = WispOut(
            name=str(program["wisp_name"] or ""),
            format="irs_pub_5708",
            evidence_item_id=cast(UUID | None, program["wisp_evidence_item_id"]),
            approved_by=_person(cast(UUID | None, program["wisp_approved_by"]), names),
            approved_on=cast(date | None, program["wisp_approved_on"]),
        )
    review = None
    if program is not None and program["access_review_quarter"] is not None:
        review = AccessReviewOut(
            quarter=str(program["access_review_quarter"]),
            due_on=cast(date, program["access_review_due_on"]),
            status=cast(Any, program["access_review_status"] or "not_started"),  # Any: CHECKed
        )
    return SafeguardsOut(
        qualified_individual=_person(cast(UUID | None, p.get("qi_user_id")), names),
        wisp=wisp,
        annual_report_last_on=cast(date | None, p.get("annual_report_last_on")),
        annual_report_next_due_month=cast(str | None, p.get("annual_report_next_due_month")),
        controls_evidenced=len(evidenced),
        controls_total=len(controls),
        open_controls=[_control_out(c, statuses.get(c.key)) for c in still_open],
        training_completed=cast(int | None, p.get("training_completed")),
        training_total=None,
        ptin_attested=cast(int | None, p.get("ptin_attested")),
        ptin_total=cast(int | None, p.get("ptin_total")),
        access_review=review,
        updated_at=cast(datetime | None, p.get("updated_at")),
        updated_by=_person(cast(UUID | None, p.get("updated_by")), names),
        version=int(cast(int, p.get("version", 0))),
    )


_INSERT_PROGRAM = text(
    "INSERT INTO safeguards_programs (tenant_id, qi_user_id, wisp_name, wisp_evidence_item_id, "
    "wisp_approved_by, wisp_approved_on, annual_report_last_on, annual_report_next_due_month, "
    "access_review_quarter, access_review_due_on, access_review_status, training_completed, "
    "ptin_attested, ptin_total, updated_by) VALUES (:tenant, :qi, :wisp_name, :wisp_item, "
    ":wisp_by, :wisp_on, :last_on, :next_due, :quarter, :review_due, :review_status, "
    ":training, :ptin, :ptin_total, :by) ON CONFLICT (tenant_id) DO NOTHING RETURNING version"
)
_UPDATE_PROGRAM = text(
    "UPDATE safeguards_programs SET qi_user_id = :qi, wisp_name = :wisp_name, "
    "wisp_evidence_item_id = :wisp_item, wisp_approved_by = :wisp_by, "
    "wisp_approved_on = :wisp_on, annual_report_last_on = :last_on, "
    "annual_report_next_due_month = :next_due, access_review_quarter = :quarter, "
    "access_review_due_on = :review_due, access_review_status = :review_status, "
    "training_completed = :training, ptin_attested = :ptin, ptin_total = :ptin_total, "
    "updated_by = :by, version = version + 1 WHERE version = :version RETURNING version"
)


async def save(ctx: AuthContext, body: SafeguardsIn) -> SafeguardsOut:
    """The QI saves the record against the `version` read (0: none yet). Audited
    `safeguards.updated`."""
    await _gate(ctx)
    _human(ctx, "security.manage")
    named = [
        u
        for u in (body.qualified_individual_user_id, body.wisp_approved_by_user_id)
        if u is not None
    ]
    params: dict[str, object] = {
        "tenant": ctx.tenant_id,
        "qi": body.qualified_individual_user_id,
        "wisp_name": body.wisp_name,
        "wisp_item": body.wisp_evidence_item_id,
        "wisp_by": body.wisp_approved_by_user_id,
        "wisp_on": body.wisp_approved_on,
        "last_on": body.annual_report_last_on,
        "next_due": body.annual_report_next_due_month,
        "quarter": body.access_review_quarter,
        "review_due": body.access_review_due_on,
        "review_status": body.access_review_status,
        "training": body.training_completed,
        "ptin": body.ptin_attested,
        "ptin_total": body.ptin_total,
        "by": ctx.user_id,
        "version": body.version,
    }
    async with uow(ctx.tenant) as tx:
        if named and set(named) - await active_staff_among(tx.session, named):
            raise SafeguardsPersonInvalid
        statement = _INSERT_PROGRAM if body.version == 0 else _UPDATE_PROGRAM
        try:
            version = await tx.session.scalar(statement, params)
        except IntegrityError:
            raise SafeguardsPersonInvalid from None
        if version is None:
            raise SafeguardsStale
        tx.record(
            "safeguards.updated",
            target=Target(SUBJECT, ctx.tenant_id),
            after=Ref(version=int(version)),
        )
    return await read(ctx)


_UPSERT_CONTROL = text(
    "INSERT INTO safeguards_control_statuses (tenant_id, control_key, status, due_on, "
    "scheduled_on, evidence_item_id, note, updated_by) VALUES (:tenant, :key, :status, :due, "
    ":scheduled, :item, :note, :by) ON CONFLICT (tenant_id, control_key) DO UPDATE SET "
    "status = EXCLUDED.status, due_on = EXCLUDED.due_on, scheduled_on = EXCLUDED.scheduled_on, "
    "evidence_item_id = EXCLUDED.evidence_item_id, note = EXCLUDED.note, "
    "updated_by = EXCLUDED.updated_by RETURNING control_key, status, due_on, scheduled_on, "
    "evidence_item_id"
)


async def put_control(
    ctx: AuthContext, key: str, body: SafeguardsControlIn
) -> SafeguardsControlOut:
    """One control's status; 404 for a key the published definitions don't have. Audited
    `safeguards_control.updated`."""
    await _gate(ctx)
    _human(ctx, "security.manage")
    control = next((c for c in await _published(ctx.tenant) if c.key == key), None)
    if control is None:
        raise NotFound(CONTROL)
    async with uow(ctx.tenant) as tx:
        row = (
            (
                await tx.session.execute(
                    _UPSERT_CONTROL,
                    {
                        "tenant": ctx.tenant_id,
                        "key": key,
                        "status": body.status,
                        "due": body.due_on,
                        "scheduled": body.scheduled_on,
                        "item": body.evidence_item_id,
                        "note": body.note,
                        "by": ctx.user_id,
                    },
                )
            )
            .mappings()
            .one()
        )
        tx.record(
            "safeguards_control.updated",
            target=Target(CONTROL, control.position),
            after=Ref(evidenced=int(body.status == "evidenced")),
        )
    return _control_out(control, row)


# --- Export WISP pack --------------------------------------------------------------------------

_PACK = text(
    "SELECT id, requested_by, status, document_count, segment_count, bundle_bytes, expires_at, "
    "created_at FROM wisp_packs WHERE id = :id"
)


async def _pack_out(row: Row, names: Mapping[UUID, str]) -> WispPackOut:
    ready = row["status"] == "ready"
    return WispPackOut(
        id=cast(UUID, row["id"]),
        status="ready" if ready else "preparing",
        document_count=cast(int | None, row["document_count"]),
        file_name=f"wisp-pack-{cast(datetime, row['created_at']).date().isoformat()}.zip"
        if ready
        else None,
        requested_by=cast(GovernancePersonOut, _person(cast(UUID, row["requested_by"]), names)),
        requested_at=cast(datetime, row["created_at"]),
        download_url=f"/v1/firm/safeguards/wisp-pack/{row['id']}/download" if ready else None,
        expires_at=cast(datetime | None, row["expires_at"]),
    )


async def request_pack(ctx: AuthContext) -> WispPackOut:
    """AC-27: 202 `preparing`; audited `wisp_pack.prepared` naming the QI."""
    await _gate(ctx)
    _human(ctx, "security.manage")
    pack_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO wisp_packs (id, tenant_id, requested_by) VALUES (:id, :tenant, :by)"
            ),
            {"id": pack_id, "tenant": ctx.tenant_id, "by": ctx.user_id},
        )
        tx.record("wisp_pack.prepared", target=Target(PACK, pack_id))
        tx.emit(WispPackRequested(pack_id=pack_id, requested_by=ctx.user_id))
    return await read_pack(ctx, pack_id)


async def read_pack(ctx: AuthContext, pack_id: UUID) -> WispPackOut:
    """The requester's pack; anyone else's answers 404."""
    await _gate(ctx)
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_PACK, {"id": pack_id})).mappings().one_or_none()
    if row is None or row["requested_by"] != ctx.user_id:
        raise NotFound(PACK)
    return await _pack_out(row, await names_of([ctx.user_id]))


@dataclass(frozen=True)
class PackDownload:
    file_name: str
    size: int
    tenant_id: UUID
    pack_id: UUID
    segments: int

    async def stream(self) -> AsyncIterator[bytes]:
        for n in range(self.segments):
            yield await bundles.get_segment(_KIND, self.tenant_id, self.pack_id, n)


async def download_pack(ctx: AuthContext, pack_id: UUID) -> PackDownload:
    """The requester's ready pack (409 `export_not_ready`, 410 `export_expired`)."""
    await _gate(ctx)
    _human(ctx, "security.manage")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_PACK, {"id": pack_id})).mappings().one_or_none()
    if row is None or row["requested_by"] != ctx.user_id:
        raise NotFound(PACK)
    if row["status"] != "ready":
        raise WispPackNotReady
    expires = cast(datetime | None, row["expires_at"])
    if expires is not None and max(await clock.now(ctx.tenant), clock.system_now()) >= expires:
        raise WispPackExpired
    return PackDownload(
        file_name=f"wisp-pack-{cast(datetime, row['created_at']).date().isoformat()}.zip",
        size=int(row["bundle_bytes"] or 0),
        tenant_id=ctx.tenant_id,
        pack_id=pack_id,
        segments=int(row["segment_count"] or 0),
    )


def _system(tenant_id: UUID, pack_id: UUID | str) -> TenantContext:
    return TenantContext(tenant_id, "system", f"wisp_pack:{pack_id}")


async def on_requested(event: OutboxEvent) -> None:
    """`wisp_pack.requested` starts the build, once per pack (reuse rejected)."""
    pack_id = UUID(str(event.payload["pack_id"]))
    try:
        await dispatch(
            WispPackWorkflow,
            WispPackInput(str(event.tenant_id), str(pack_id)),
            id=wisp_pack_workflow_id(str(event.tenant_id), str(pack_id)),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
    except WorkflowAlreadyStartedError:
        return


SUBSCRIPTIONS: dict[str, Handler] = {WispPackRequested.event_type: on_requested}


def _beat(progress: int) -> None:
    """Heartbeat inside the activity; the same build called directly (tests, tooling) has none."""
    if activity.in_activity():
        activity.heartbeat(progress)


def _decided(code: str) -> ApplicationError:
    return ApplicationError(code, type=code, non_retryable=True)


def _safe(name: str) -> str:
    return _UNSAFE.sub("_", name).strip(" ._") or "document"


async def build_pack(given: WispPackInput) -> WispPackFacts:
    """The WISP and every evidence item a control links, each read as the requester (evidence's
    download: authorised, audited, fingerprint-checked), zipped and sealed."""
    tenant_id, pack_id = UUID(given.tenant_id), UUID(given.pack_id)
    async with tenant_session(_system(tenant_id, pack_id)) as session:
        row = (await session.execute(_PACK, {"id": pack_id})).mappings().one_or_none()
    if row is None:
        raise _decided("requester_not_member")
    ctx = await member_context(tenant_id, cast(UUID, row["requested_by"]))
    if ctx is None:
        raise _decided("requester_not_member")
    if not bundles.configured() or not _documents:
        raise _decided("exports_unavailable")
    program, statuses = await _program(ctx.tenant)
    if program is None or program["wisp_evidence_item_id"] is None:
        raise _decided("wisp_missing")
    items: list[UUID] = [cast(UUID, program["wisp_evidence_item_id"])]
    for status in statuses.values():
        item = cast(UUID | None, status["evidence_item_id"])
        if item is not None and item not in items:
            items.append(item)
    with tempfile.TemporaryFile() as bundle:
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for n, item in enumerate(items, start=1):
                document = await _documents[0](ctx, item)
                info = zipfile.ZipInfo(f"{n:02d} {_safe(document.file_name)}", date_time=_ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, document.content)
                _beat(n)
        size = bundle.tell()
        bundle.seek(0)
        segments = await bundles.put_bundle(_KIND, tenant_id, pack_id, bundle)
    return WispPackFacts(given.tenant_id, given.pack_id, len(items), size, segments)


_READY = text(
    "UPDATE wisp_packs SET status = 'ready', document_count = :documents, "
    "segment_count = :segments, bundle_bytes = :bytes, expires_at = :expires "
    "WHERE id = :id AND status = 'preparing' RETURNING id"
)
_FAILED = text(
    "UPDATE wisp_packs SET status = 'failed', failure_code = :code "
    "WHERE id = :id AND status = 'preparing' RETURNING id"
)


async def mark_pack_ready(facts: WispPackFacts) -> str:
    tenant_id, pack_id = UUID(facts.tenant_id), UUID(facts.pack_id)
    system = _system(tenant_id, pack_id)
    expires = max(await clock.now(system), clock.system_now()) + PACK_EXPIRY
    async with uow(system) as tx:
        done = await tx.session.scalar(
            _READY,
            {
                "id": pack_id,
                "documents": facts.document_count,
                "segments": facts.segment_count,
                "bytes": facts.bundle_bytes,
                "expires": expires,
            },
        )
        if done is None:
            return "unchanged"
        tx.record(
            "wisp_pack.ready",
            target=Target(PACK, pack_id),
            after=Ref(documents=facts.document_count),
        )
    return "ready"


async def mark_pack_failed(failure: WispPackFailure) -> str:
    tenant_id, pack_id = UUID(failure.tenant_id), UUID(failure.pack_id)
    async with uow(_system(tenant_id, pack_id)) as tx:
        done = await tx.session.scalar(_FAILED, {"id": pack_id, "code": failure.code})
        if done is None:
            return "unchanged"
        tx.record("wisp_pack.failed", target=Target(PACK, pack_id))
    _log.warning("wisp_pack.failed", tenant_id=str(tenant_id), code=failure.code)
    return "failed"


@activity.defn(name="platform.wisp_pack_build")
async def build_pack_activity(given: WispPackInput) -> WispPackFacts:
    return await build_pack(given)


@activity.defn(name="platform.wisp_pack_ready")
async def pack_ready_activity(facts: WispPackFacts) -> str:
    return await mark_pack_ready(facts)


@activity.defn(name="platform.wisp_pack_failed")
async def pack_failed_activity(failure: WispPackFailure) -> str:
    return await mark_pack_failed(failure)


ACTIVITIES: tuple[object, ...] = (build_pack_activity, pack_ready_activity, pack_failed_activity)

__all__ = [
    "ACTIVITIES",
    "SUBSCRIPTIONS",
    "PackDownload",
    "WispPackExpired",
    "WispPackNotReady",
    "download_pack",
    "import_controls",
    "open_controls",
    "publish_controls",
    "put_control",
    "read",
    "read_pack",
    "register_wisp_document_reader",
    "request_pack",
    "save",
]
