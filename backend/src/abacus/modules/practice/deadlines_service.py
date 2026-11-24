"""Filing deadlines: the recompute and HOME-03's reads (T-08-T10; S51 partials, TASK-8741;
DEC-5732; SPEC-710 AC-9 to AC-16). Dark behind `practice.filing_deadlines`.

- **Recompute** (nightly, and on demand): every return with a due date becomes one
  `filing_deadlines` row keyed (source kind, source ref, filing label), upserted only when its
  `inputs_hash` changed (metadata only: client, office, filing, dates, stage, owners; never TRI or
  an amount). Every source kind registered to platform's slot is asked for a window from the
  season before to eighteen months ahead (T-08-T20: tax, closes, notices, assurance, signatures and
  organisations each register theirs; practice imports none of them). Rows whose source is gone
  are left as they are (their source owns deletion).
- **Read**: the window's rows the viewer may see (a walled client contributes no row, day count
  or "+n more"; AC-14), risk tier and days left computed on read in the firm's zone, month grid
  days with three chips each, list and week views, and a detail with the reference-set versions.
- **Export**: a one-off xlsx (safe_xlsx) or RFC 5545 ics, no TIN, no amount (AC-16).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel.clock import FIRM_ZONE
from abacus.kernel.clock import now as clock_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.safe_xlsx import Sheet, workbook
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise, walled_from
from abacus.modules.platform.api import FilingDeadlineFact, FilingDeadlineWindow
from abacus.modules.practice.compute import deadlines as calc

_log = get_logger(__name__)


@dataclass(frozen=True)
class Row:
    deadline_id: UUID
    source_kind: str
    client_id: UUID | None
    filing_label: str
    original_due_on: date
    extended_due_on: date | None
    extension_form: str | None
    due_on: date
    postponed_from: date | None
    stage_code: str
    done: bool
    owner_user_ids: tuple[UUID, ...]
    signer_user_id: UUID | None
    work_item_id: UUID | None
    office_id: UUID | None
    service_line: str
    reference_set_version_ids: tuple[UUID, ...]
    computed_at: datetime
    internal_target_on: date | None = None  # T-08-T44 (DF-10): stored and exported, not shown

    def deadline(self) -> calc.Deadline:
        return calc.Deadline(str(self.deadline_id), self.due_on, None, self.done)


_UPSERT = text(
    "INSERT INTO filing_deadlines (tenant_id, source_kind, source_ref, client_id, office_id, "
    "service_line, filing_label, rule_key, reference_set_version_ids, original_due_on, "
    "extension_form, extension_filed_on, extended_due_on, due_on, postponement_notice_id, "
    "postponed_from, internal_target_on, owner_user_ids, signer_user_id, stage_code, done_at, "
    "work_item_id, inputs_hash) VALUES (:t, :kind, :ref, :client, :office, :line, :label, :rule, "
    ":sets, :orig, :ext_form, :ext_filed, :ext, :due, :notice, :postponed, :target, :owners, "
    ":signer, :stage, CASE WHEN :done THEN clock_timestamp() END, :wi, :hash) "
    "ON CONFLICT (tenant_id, source_kind, source_ref, filing_label) DO UPDATE SET "
    "client_id = EXCLUDED.client_id, office_id = EXCLUDED.office_id, "
    "service_line = EXCLUDED.service_line, rule_key = EXCLUDED.rule_key, "
    "reference_set_version_ids = EXCLUDED.reference_set_version_ids, "
    "original_due_on = EXCLUDED.original_due_on, extension_form = EXCLUDED.extension_form, "
    "extension_filed_on = EXCLUDED.extension_filed_on, "
    "extended_due_on = EXCLUDED.extended_due_on, due_on = EXCLUDED.due_on, "
    "postponement_notice_id = EXCLUDED.postponement_notice_id, "
    "postponed_from = EXCLUDED.postponed_from, "
    "internal_target_on = EXCLUDED.internal_target_on, "
    "owner_user_ids = EXCLUDED.owner_user_ids, signer_user_id = EXCLUDED.signer_user_id, "
    "stage_code = EXCLUDED.stage_code, "
    "done_at = CASE WHEN :done THEN coalesce(filing_deadlines.done_at, clock_timestamp()) END, "
    "work_item_id = EXCLUDED.work_item_id, inputs_hash = EXCLUDED.inputs_hash, "
    "computed_at = clock_timestamp() "
    "WHERE filing_deadlines.inputs_hash <> EXCLUDED.inputs_hash RETURNING id"
)
# The window every source is asked for: the season before (overdue and filed rows) to eighteen
# months ahead.
BACK: Final = timedelta(days=400)
AHEAD: Final = timedelta(days=548)


def inputs_hash(fact: FilingDeadlineFact, internal_target_on: date | None = None) -> str:
    """The fact's inputs, hashed: a recompute writes a row only when this moved (AC-15)."""
    body = {
        "target": None if internal_target_on is None else str(internal_target_on),
        "client": None if fact.client_id is None else str(fact.client_id),
        "office": None if fact.office_id is None else str(fact.office_id),
        "line": fact.service_line, "rule": fact.rule_key, "orig": str(fact.original_due_on),
        "ext_form": fact.extension_form, "ext_filed": str(fact.extension_filed_on),
        "ext": str(fact.extended_due_on), "due": str(fact.due_on),
        "notice": None if fact.postponement_notice_id is None
        else str(fact.postponement_notice_id),
        "postponed": str(fact.postponed_from),
        "owners": [str(u) for u in fact.owner_user_ids],
        "signer": None if fact.signer_user_id is None else str(fact.signer_user_id),
        "stage": fact.stage_code, "done": fact.done,
        "sets": [str(s) for s in fact.reference_set_version_ids],
        "work": None if fact.work_item_id is None else str(fact.work_item_id),
    }  # fmt: skip
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


async def recompute(tenant_id: UUID, *, client_id: UUID | None = None) -> int:
    """One firm's filing deadlines from every registered source (T-08-T20, DEC-5917; tax's
    returns, extensions, estimates, 8971s and 65-day windows; closes; notices; plan audits;
    envelopes; consents), with the firm's DF-10 overrides on top (T-08-T44, DEC-5921: internal
    targets, and a person's client relief applications); answers the rows that changed (only
    `client_id`'s when given). A source that fails is logged by kind and the others still run;
    an unregistered kind yields nothing (AC-20)."""
    from abacus.modules.platform.api import filing_deadline_source, filing_deadline_source_kinds
    from abacus.modules.practice import deadline_overrides as df10
    from abacus.modules.practice.due_dates import federal_holidays

    tenant = TenantContext(tenant_id, "system", "practice:filing_deadlines")
    today = calc.firm_today(await clock_now(tenant), str(FIRM_ZONE))
    window = FilingDeadlineWindow(today - BACK, today + AHEAD)
    overrides = await df10.overrides_in_effect(tenant_id, today)
    applied = await df10.applications(tenant, today, client_id)
    holidays: frozenset[date] = (
        await federal_holidays(window.end) if overrides is not None else frozenset()
    )
    changed = 0
    for kind in filing_deadline_source_kinds():
        provider = filing_deadline_source(kind)
        if provider is None:
            continue
        try:
            facts = await provider(tenant, window)
        except Exception as exc:
            _log.error("filing_deadlines.source_failed", kind=kind, error=type(exc).__name__)
            continue
        mine = [
            f for f in facts
            if f.source_kind == kind  # a provider answers its own kind only
            and (client_id is None or f.client_id == client_id)
        ]  # fmt: skip
        for raw, target, app, moved_to in df10.apply_overrides(mine, overrides, applied, holidays):
            fact = cast(FilingDeadlineFact, raw)
            pins = list(fact.reference_set_version_ids)
            if overrides is not None and target is not None:
                pins.append(overrides.version_id)
            if app is not None and moved_to is not None:
                pins.append(app.notice.version_id)
                fact = replace(
                    fact, due_on=moved_to, postponed_from=fact.due_on,
                    postponement_notice_id=app.id,
                )  # fmt: skip
            fact = replace(fact, reference_set_version_ids=tuple(dict.fromkeys(pins)))
            changed += await _upsert(tenant, fact, target)
    return changed


async def _upsert(
    tenant: TenantContext, fact: FilingDeadlineFact, internal_target_on: date | None = None
) -> int:
    try:
        async with uow(tenant) as tx:
            moved = await tx.session.scalar(
                _UPSERT,
                {
                    "t": tenant.tenant_id, "kind": fact.source_kind, "ref": fact.source_ref,
                    "client": fact.client_id, "office": fact.office_id,
                    "line": fact.service_line, "label": fact.filing_label[:80],
                    "rule": fact.rule_key, "sets": list(fact.reference_set_version_ids),
                    "orig": fact.original_due_on, "ext_form": fact.extension_form,
                    "ext_filed": fact.extension_filed_on, "ext": fact.extended_due_on,
                    "due": fact.due_on, "notice": fact.postponement_notice_id,
                    "postponed": fact.postponed_from, "target": internal_target_on,
                    "owners": list(fact.owner_user_ids),
                    "signer": fact.signer_user_id, "stage": fact.stage_code, "done": fact.done,
                    "wi": fact.work_item_id, "hash": inputs_hash(fact, internal_target_on),
                },
            )  # fmt: skip
            if moved is None:
                raise _Unchanged
            tx.record("filing_deadline.recomputed", target=Target("filing_deadline", moved))
    except _Unchanged:
        return 0
    return 1


class _Unchanged(Exception):
    """The row's inputs are the same: nothing is written (the unit rolls back)."""


_ACTIVITY: Final = "practice.filing_deadlines_recompute"


@activity.defn(name=_ACTIVITY)
async def recompute_activity() -> int:
    """Every firm with the flag on; one firm's failure is logged by id and the others run."""
    from abacus.kernel._flags import PRACTICE_FILING_DEADLINES
    from abacus.kernel.flags import flag_enabled
    from abacus.modules.identity.api import firm_tenant_ids

    total = 0
    for tenant_id in await firm_tenant_ids():
        activity.heartbeat(str(tenant_id))
        try:
            tenant = TenantContext(tenant_id, "system", "practice:filing_deadlines")
            if await flag_enabled(tenant, PRACTICE_FILING_DEADLINES):
                total += await recompute(tenant_id)
        except Exception as exc:
            _log.error(
                "filing_deadlines.failed", tenant_id=str(tenant_id), error=type(exc).__name__
            )
    return total


# --- reads ---------------------------------------------------------------------------------------

_ROWS = text(
    "SELECT id, source_kind, client_id, filing_label, original_due_on, extended_due_on, "
    "extension_form, due_on, postponed_from, stage_code, done_at IS NOT NULL, owner_user_ids, "
    "signer_user_id, work_item_id, office_id, service_line, reference_set_version_ids, "
    "computed_at, internal_target_on FROM filing_deadlines WHERE due_on BETWEEN :f AND :t "
    "AND (CAST(:id AS uuid) IS NULL OR id = :id) ORDER BY due_on, filing_label, id"
)


def _row(r: tuple[object, ...]) -> Row:
    return Row(
        cast(UUID, r[0]), str(r[1]), cast(UUID | None, r[2]), str(r[3]), cast(date, r[4]),
        cast(date | None, r[5]), cast(str | None, r[6]), cast(date, r[7]),
        cast(date | None, r[8]), str(r[9]), bool(r[10]), tuple(cast(list[UUID], r[11])),
        cast(UUID | None, r[12]), cast(UUID | None, r[13]), cast(UUID | None, r[14]),
        str(r[15]), tuple(cast(list[UUID], r[16])), cast(datetime, r[17]),
        cast(date | None, r[18]),
    )  # fmt: skip


async def rows(
    ctx: AuthContext,
    window_from: date,
    window_to: date,
    *,
    office: UUID | None = None,
    service: str | None = None,
    person: UUID | None = None,
    deadline_id: UUID | None = None,
) -> list[Row]:
    await authorise(ctx, "filing_deadline.read", Resource.firm(ctx.tenant_id))
    walled = await walled_from(ctx.tenant, ctx.user_id)
    async with tenant_session(ctx.tenant) as session:
        found = [
            _row(tuple(r))
            for r in await session.execute(
                _ROWS, {"f": window_from, "t": window_to, "id": deadline_id}
            )
        ]
    return [
        r for r in found
        if (r.client_id is None or r.client_id not in walled)
        and (office is None or r.office_id == office)
        and (service is None or r.service_line == service)
        and (person is None or person in r.owner_user_ids or person == r.signer_user_id)
    ]  # fmt: skip


async def firm_today(ctx: AuthContext) -> date:
    return calc.firm_today(await clock_now(ctx.tenant), str(FIRM_ZONE))


async def detail(ctx: AuthContext, deadline_id: UUID) -> Row:
    found = await rows(ctx, date(1990, 1, 1), date(2100, 12, 31), deadline_id=deadline_id)
    if not found:
        raise NotFound("filing_deadline")
    return found[0]


def ics_text(value: str) -> str:
    """RFC 5545 TEXT: backslash, comma and semicolon escaped, and no line break survives (client
    content is hostile: a name must never start a property of its own; ADR-052)."""
    out = value.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")
    return out.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")[:200]


def ics(found: list[Row], names: dict[UUID, str]) -> bytes:
    """RFC 5545: one all-day event per deadline; summary is client and filing, no amount."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Accrued//Filing deadlines//EN"]
    for r in found:
        client = names.get(r.client_id, "") if r.client_id else ""
        summary = ics_text(f"{client} · {r.filing_label}".strip(" ·"))
        day = r.due_on.strftime("%Y%m%d")
        nxt = (r.due_on + timedelta(days=1)).strftime("%Y%m%d")
        lines += [
            "BEGIN:VEVENT", f"UID:{r.deadline_id}@filing-deadlines", f"DTSTAMP:{day}T000000Z",
            f"DTSTART;VALUE=DATE:{day}", f"DTEND;VALUE=DATE:{nxt}", f"SUMMARY:{summary}",
            "END:VEVENT",
        ]  # fmt: skip
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines) + "\r\n").encode()


async def export_deadlines(
    ctx: AuthContext, fmt: str, window_from: date, window_to: date
) -> bytes:
    found = await rows(ctx, window_from, window_to)
    await authorise(ctx, "export.create", Resource.firm(ctx.tenant_id))
    from abacus.modules.organisations.api import firm_names

    names = {n.client_id: n.name for n in await firm_names(ctx.tenant) if n.id == n.client_id}
    async with uow(ctx.tenant) as tx:
        tx.record(
            "filing_deadline.exported",
            target=Target("firm", ctx.tenant_id),
            after=Ref(rows=len(found)),
        )
    if fmt == "ics":
        return ics(found, names)
    today = await firm_today(ctx)
    sheet: list[list[str | int | bool | None]] = [
        ["Client", "Filing", "Due", "Original due", "Extension", "Stage", "Risk", "Days left"]
    ]
    for r in found:
        sheet.append(
            [names.get(r.client_id, "") if r.client_id else "", r.filing_label,
             r.due_on.isoformat(), r.original_due_on.isoformat(), r.extension_form,
             r.stage_code, calc.risk(r.deadline(), today), calc.days_left(r.deadline(), today)]
        )  # fmt: skip
    return workbook([Sheet("Filing deadlines", sheet)])


AUDIT_CLIENT_KINDS: Final = frozenset({"filing_deadline"})
_DEADLINE_CLIENTS = text(
    "SELECT id, client_id FROM filing_deadlines WHERE id = ANY(:i) AND client_id IS NOT NULL"
)


async def audit_clients(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """A deadline's audit events belong to its client (walls apply in the trail)."""
    if kind not in AUDIT_CLIENT_KINDS or not ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(_DEADLINE_CLIENTS, {"i": list(ids)})
        return {cast(UUID, r[0]): cast(UUID, r[1]) for r in rows}


__all__ = [
    "Row",
    "detail",
    "export_deadlines",
    "firm_today",
    "ics",
    "ics_text",
    "recompute",
    "recompute_activity",
    "rows",
]
