"""Interim G8: the report released outside Accrued, recorded (A-01-T23; A-01 §3.5 Story 5.2;
DEC-83, DEC-590). PROTECTED (red path, chapter 03 §2.2).

While a firm's `assurance_release_mode` is `external` (the default; A-07 brings `in_app`), the
engagement partner records the date the report left the firm's own tool and whether there was a
report at all (AR-C 70 issues none):

- **Who.** `assurance.record_release`: the engagement partner only, with independence and a
  second factor verified in the last 15 minutes (a stale one is 403 `mfa_required`, DEC-547), a
  live person's own act (INV-1; the table's CHECK and insert trigger bind the row to the
  session's human actor; `assurance.release_recorded` is on the human-only register).
- **When.** `release_mode_in_app` (409) while the firm releases in Accrued; the date may not be
  after the firm's today (422 `release_date_future`); the phase must be In review, Completion or
  Ready to release (409 `record_out_of_phase`: SPEC-314's G6 and G7 are registered for every
  firm, so an external-mode firm cannot record Ready to release, DEC-590), and a work item is
  released once.
- **What.** One insert-only row, the derived move to Released naming G8 (`advance_by_gate`, the
  person named), and the audit event, in one unit of work. The 60-day documentation clock reads
  the recorded date (AU-C 230).

The G8 provider registered for every firm is `g8` below: met by SPEC-314's in-app release or by
this record, whichever the firm used. Code records what a person states; it never decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final, Literal
from uuid import UUID

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.assurance import completion
from abacus.modules.assurance.external_models import ExternalRelease, external_release_of
from abacus.modules.assurance.phase import advance_by_gate
from abacus.modules.assurance.record_auth import authorise_record, fresh_mfa_at
from abacus.modules.engagements.api import (
    GateFact,
    assurance_item,
    lock_assurance_item,
    lock_ref,
)
from abacus.modules.identity.api import AuthContext, SettingKey, stored_value

ACTION: Final = "assurance.record_release"
DOCUMENTATION_DAYS: Final = 60  # AU-C 230
ReleaseMode = Literal["external", "in_app"]
RELEASE_MODES: Final[tuple[str, ...]] = ("external", "in_app")
# The firm setting (A-01 §0): registered in the typed store, so only a firm admin with a fresh
# second factor changes it (`firm.manage_settings`), audited `firm_setting.updated`.
RELEASE_MODE_SETTING: Final = SettingKey(
    "defaults", "assurance_release_mode", "text", max_length=16, choices=RELEASE_MODES
)
# A release is recorded once fieldwork is behind the audit (DEC-590).
_RELEASABLE: Final = frozenset({"in_review", "completion", "ready_to_release"})


class ReleaseModeInApp(DomainConflict):
    """The firm releases reports in Accrued (`assurance_release_mode = in_app`): record mode is
    closed for release and archive."""

    code = "release_mode_in_app"


class ReleaseDateFuture(DomainInvalid):
    """The release date is after the firm's today."""

    code = "release_date_future"


class RecordOutOfPhase(DomainConflict):
    """The audit's phase does not take this record: a release from In review to Ready to
    release, an archive once Released (`facts.phase`)."""

    code = "record_out_of_phase"


@dataclass(frozen=True)
class ReleaseRecord:
    work_item_id: UUID
    report_released_on: date
    report_kind: str
    phase: str
    archive_due_on: date
    recorded_at: datetime


async def release_mode(tenant: TenantContext) -> ReleaseMode:
    """The firm's `assurance_release_mode`; unset reads `external` (the default)."""
    value = await stored_value(tenant, "defaults", "assurance_release_mode")
    return "in_app" if value == "in_app" else "external"


async def require_external(tenant: TenantContext) -> None:
    if await release_mode(tenant) == "in_app":
        raise ReleaseModeInApp(facts={"mode": "in_app"})


async def record_release(
    ctx: AuthContext, work_item_id: UUID, released_on: date, report_kind: str
) -> ReleaseRecord:
    """Story 5.2: "Report released outside Accrued on Jul 29, 2026"."""
    if report_kind not in ("opinion", "no_report"):
        raise DomainInvalid("report_kind")
    found = await assurance_item(ctx.tenant, work_item_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, found.engagement_id)
        await authorise_record(ctx, ACTION, ref.resource())
        await require_external(ctx.tenant)
        if released_on > await clock.today(ctx.tenant):
            raise ReleaseDateFuture(facts={"report_released_on": released_on.isoformat()})
        item = await lock_assurance_item(tx, work_item_id)
        if item.phase not in _RELEASABLE:
            raise RecordOutOfPhase(facts={"phase": item.phase})
        if await external_release_of(tx.session, item.engagement_id) is not None:
            raise RecordOutOfPhase(facts={"phase": item.phase})
        mfa_at = fresh_mfa_at(ctx)
        row = ExternalRelease(
            work_item_id=item.work_item_id,
            tenant_id=ctx.tenant_id,
            engagement_id=item.engagement_id,
            report_released_on=released_on,
            report_kind=report_kind,
            recorded_by=ctx.user_id,
            actor_kind="human",
            mfa_at=mfa_at,
        )
        tx.session.add(row)
        await advance_by_gate(tx, ctx.tenant, item.engagement_id, "released", "G8", ctx.user_id)
        tx.record(
            "assurance.release_recorded",
            target=Target("engagement", item.engagement_id),
            after=Ref(
                work_item=item.work_item_id,
                released_on=int(released_on.strftime("%Y%m%d")),
                no_report=int(report_kind == "no_report"),
                mfa_at=int(mfa_at.timestamp()),
            ),
            scope=Scope(engagement_id=item.engagement_id, work_item_id=item.work_item_id),
        )
        await tx.session.refresh(row)
        return ReleaseRecord(
            item.work_item_id,
            released_on,
            report_kind,
            "released",
            released_on + timedelta(days=DOCUMENTATION_DAYS),
            row.recorded_at,
        )


async def g8(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    """G8 for every firm: SPEC-314's in-app release, or the external release record."""
    in_app = await completion.g8(tenant, engagement_id)
    if in_app.met:
        return in_app
    async with tenant_session(tenant) as session:
        recorded = await external_release_of(session, engagement_id)
    if recorded is not None:
        return GateFact(met=True, blockers=())
    return in_app
