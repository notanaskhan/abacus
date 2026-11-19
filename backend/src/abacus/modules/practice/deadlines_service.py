"""Filing deadlines: the recompute and HOME-03's reads (T-08-T10; S51 partials, TASK-8741;
DEC-5732; SPEC-710 AC-9 to AC-16). Dark behind `practice.filing_deadlines`.

- **Recompute** (nightly, and on demand): every return with a due date becomes one
  `filing_deadlines` row keyed (source kind, source ref, filing label), upserted only when its
  `inputs_hash` changed (metadata only: client, office, filing, dates, stage, owners; never TRI or
  an amount). The due date is the extended one when the return is extended. Rows whose source is
  gone are left as they are (their source owns deletion). Return deadlines are the source built
  now; the other source kinds register with their owners.
- **Read**: the window's rows the viewer may see (a walled client contributes no row, day count
  or "+n more"; AC-14), risk tier and days left computed on read in the firm's zone, month grid
  days with three chips each, list and week views, and a detail with the reference-set versions.
- **Export**: a one-off xlsx (safe_xlsx) or RFC 5545 ics, no TIN, no amount (AC-16).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
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
from abacus.modules.practice.compute import deadlines as calc

SOURCE: Final = "tax_return"
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

    def deadline(self) -> calc.Deadline:
        return calc.Deadline(str(self.deadline_id), self.due_on, None, self.done)


_UPSERT = text(
    "INSERT INTO filing_deadlines (tenant_id, source_kind, source_ref, client_id, office_id, "
    "service_line, filing_label, rule_key, reference_set_version_ids, original_due_on, "
    "extension_form, extended_due_on, due_on, owner_user_ids, signer_user_id, stage_code, "
    "done_at, work_item_id, inputs_hash) VALUES (:t, :kind, :ref, :client, :office, 'tax', "
    ":label, NULL, :sets, :orig, :ext_form, :ext, :due, :owners, :signer, :stage, "
    "CASE WHEN :done THEN clock_timestamp() END, :wi, :hash) "
    "ON CONFLICT (tenant_id, source_kind, source_ref, filing_label) DO UPDATE SET "
    "client_id = EXCLUDED.client_id, office_id = EXCLUDED.office_id, "
    "reference_set_version_ids = EXCLUDED.reference_set_version_ids, "
    "original_due_on = EXCLUDED.original_due_on, extension_form = EXCLUDED.extension_form, "
    "extended_due_on = EXCLUDED.extended_due_on, due_on = EXCLUDED.due_on, "
    "owner_user_ids = EXCLUDED.owner_user_ids, signer_user_id = EXCLUDED.signer_user_id, "
    "stage_code = EXCLUDED.stage_code, "
    "done_at = CASE WHEN :done THEN coalesce(filing_deadlines.done_at, clock_timestamp()) END, "
    "work_item_id = EXCLUDED.work_item_id, inputs_hash = EXCLUDED.inputs_hash, "
    "computed_at = clock_timestamp() "
    "WHERE filing_deadlines.inputs_hash <> EXCLUDED.inputs_hash RETURNING id"
)
_EXTENSION_FORM: Final = {"1040": "4868", "1041": "7004", "1065": "7004", "1120s": "7004",
                          "1120": "7004", "990": "8868"}  # fmt: skip


async def recompute(tenant_id: UUID) -> int:
    """One firm's return deadlines; answers the rows that changed."""
    from abacus.modules.engagements.api import engagement_retention_facts
    from abacus.modules.identity.api import team_of
    from abacus.modules.tax.api import return_deadlines

    tenant = TenantContext(tenant_id, "system", "practice:filing_deadlines")
    found = await return_deadlines(tenant)
    facts = await engagement_retention_facts(
        tenant, sorted({d.engagement_id for d in found if d.engagement_id}, key=str)
    )
    changed = 0
    for d in found:
        f = facts.get(d.engagement_id) if d.engagement_id else None
        team = [] if d.engagement_id is None else await team_of(tenant_id, d.engagement_id)
        owners = sorted({u for u, r in team if str(r) in ("senior", "staff", "reviewer",
                                                          "manager")}, key=str)  # fmt: skip
        signer = next((u for u, r in team if str(r) == "engagement_partner"), None)
        due = d.extended_due_on if d.extended and d.extended_due_on else d.original_due_on
        ext_form = _EXTENSION_FORM.get(d.form) if d.extended else None
        body = {
            "client": None if f is None else str(f.client_id),
            "office": None if f is None or f.office_id is None else str(f.office_id),
            "orig": str(d.original_due_on), "ext": str(d.extended_due_on), "due": str(due),
            "ext_form": ext_form, "owners": [str(u) for u in owners],
            "signer": None if signer is None else str(signer), "stage": d.stage_code,
            "sets": [str(s) for s in d.reference_set_version_ids],
        }  # fmt: skip
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        try:
            async with uow(tenant) as tx:
                moved = await tx.session.scalar(
                    _UPSERT,
                    {
                        "t": tenant_id, "kind": SOURCE, "ref": str(d.work_item_id),
                        "client": None if f is None else f.client_id,
                        "office": None if f is None else f.office_id, "label": d.label,
                        "sets": list(d.reference_set_version_ids), "orig": d.original_due_on,
                        "ext_form": ext_form, "ext": d.extended_due_on, "due": due,
                        "owners": owners, "signer": signer, "stage": d.stage_code, "done": d.done,
                        "wi": d.work_item_id, "hash": digest,
                    },
                )  # fmt: skip
                if moved is None:
                    raise _Unchanged
                changed += 1
                tx.record("filing_deadline.recomputed", target=Target("filing_deadline", moved))
        except _Unchanged:
            continue
    return changed


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
    "computed_at FROM filing_deadlines WHERE due_on BETWEEN :f AND :t "
    "AND (CAST(:id AS uuid) IS NULL OR id = :id) ORDER BY due_on, filing_label, id"
)


def _row(r: tuple[object, ...]) -> Row:
    return Row(
        cast(UUID, r[0]), str(r[1]), cast(UUID | None, r[2]), str(r[3]), cast(date, r[4]),
        cast(date | None, r[5]), cast(str | None, r[6]), cast(date, r[7]),
        cast(date | None, r[8]), str(r[9]), bool(r[10]), tuple(cast(list[UUID], r[11])),
        cast(UUID | None, r[12]), cast(UUID | None, r[13]), cast(UUID | None, r[14]),
        str(r[15]), tuple(cast(list[UUID], r[16])), cast(datetime, r[17]),
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


async def export(ctx: AuthContext, fmt: str, window_from: date, window_to: date) -> bytes:
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


__all__ = [
    "Row",
    "detail",
    "export",
    "firm_today",
    "ics",
    "ics_text",
    "recompute",
    "recompute_activity",
    "rows",
]
