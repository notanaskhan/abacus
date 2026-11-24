"""Tax's filing-deadline providers (T-08-T20; TASK-8915; SPEC-710 AC-10, AC-12, AC-20; FD-1;
HOME-03; DEC-5917; amber). Registered to platform's slot (`register_filing_deadline_source`);
practice builds the read model and tax never imports practice.

- `tax_return`: one per return with a due date (every form, 1040 to 706 and 990); due on the
  extended date when extended, else the original, with the extension form and its date whenever
  known; done when filed or accepted.
- `extension`: one per `filing_extensions` row (4868, 7004, 8868, 4768, state forms), due on the
  return's original due date (file the extension by); done when filed or accepted.
- `estimate_batch`: one per installment due date and form ("Form 1040-ES Q3 · 2026"); done when
  every installment is paid, scheduled or not required.
- `fiduciary_statement`: Form 8971 for each Form 706, the 706 due date + 30 days; done with the
  706.
- `election_window`: §663(b) for each Form 1041, the 65th day after the year end (the recorded
  window when one is); done once an election, made or not, is recorded.

A Form 706 without stored dates takes the estate due chip (`estate_service.due_chip`: date of
death + 9 months; Form 4768 + 6 months, both rolled), so the Thornbury 706 reads Nov 2, 2026
with Form 4768 to May 3, 2027. Owners are the engagement's preparers and reviewers, the signer
its engagement partner. Metadata only: no TRI, no amount.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import FilingDeadlineFact, FilingDeadlineWindow

DONE: Final = frozenset({"filed", "accepted"})
OWNER_ROLES: Final = frozenset({"senior", "staff", "reviewer", "manager"})
EXTENSION_FORM: Final[dict[str, str]] = {
    "1040": "4868", "1040x": "4868", "1041": "7004", "1065": "7004", "1120s": "7004",
    "1120": "7004", "990": "8868", "706": "4768", "709": "8892",
}  # fmt: skip
FORM_LABEL: Final[dict[str, str]] = {"1120s": "1120-S", "1040x": "1040-X"}
SIXTY_FIVE_DAYS: Final = 65


@dataclass(frozen=True)
class _Scope:
    client_id: UUID | None
    office_id: UUID | None
    owners: tuple[UUID, ...]
    signer: UUID | None


async def _scopes(tenant: TenantContext, engagements: Sequence[UUID]) -> dict[UUID, _Scope]:
    """Client, office, owners and signer per engagement (identity's team; engagements' facts)."""
    from abacus.modules.engagements.api import engagement_retention_facts
    from abacus.modules.identity.api import team_of

    facts = await engagement_retention_facts(tenant, sorted(set(engagements), key=str))
    out: dict[UUID, _Scope] = {}
    for engagement in sorted(set(engagements), key=str):
        team = await team_of(tenant.tenant_id, engagement)
        owners = tuple(sorted({u for u, r in team if str(r) in OWNER_ROLES}, key=str))
        signer = next((u for u, r in team if str(r) == "engagement_partner"), None)
        f = facts.get(engagement)
        out[engagement] = _Scope(
            None if f is None else f.client_id, None if f is None else f.office_id, owners, signer
        )
    return out


def _label(form: str, tax_year: int) -> str:
    return f"Form {FORM_LABEL.get(form, form)} · {tax_year}"


_RETURNS: Final = text(
    "SELECT r.work_item_id, r.engagement_id, r.form, r.tax_year, r.status, r.extended, "
    "r.original_due_on, r.extended_due_on, r.due_rule_version_ids, r.client_entity_id, "
    "p.date_of_death FROM tax_returns r LEFT JOIN estate_profiles p "
    "ON p.client_entity_id = r.client_entity_id AND r.form = '706' "
    "WHERE coalesce(r.on_hold, false) = false "
    "AND (r.original_due_on IS NOT NULL OR p.date_of_death IS NOT NULL) "
    "ORDER BY r.work_item_id"
)


@dataclass(frozen=True)
class _Return:
    work_item_id: UUID
    engagement_id: UUID
    form: str
    tax_year: int
    status: str
    extended: bool
    original_due_on: date
    extended_due_on: date | None
    sets: tuple[UUID, ...]

    @property
    def due_on(self) -> date:
        return (
            self.extended_due_on
            if self.extended and self.extended_due_on
            else self.original_due_on
        )

    @property
    def done(self) -> bool:
        return self.status in DONE


async def _returns(tenant: TenantContext) -> list[_Return]:
    from abacus.modules.tax.estate_service import due_chip

    async with tenant_session(tenant) as session:
        rows = (await session.execute(_RETURNS)).all()
    out: list[_Return] = []
    for r in rows:
        original, extended_to = cast("date | None", r.original_due_on), r.extended_due_on
        if original is None:  # a 706 without stored dates: the estate due chip (AC-14.1)
            chip = await due_chip(int(r.tax_year), cast(date, r.date_of_death), bool(r.extended))
            original, extended_to = chip.due_on, chip.extension_to
        sets: list[UUID] = []
        for raw in cast("list[object]", r.due_rule_version_ids or []):
            try:
                sets.append(UUID(str(raw)))
            except ValueError:
                continue
        out.append(
            _Return(
                cast(UUID, r.work_item_id), cast(UUID, r.engagement_id), str(r.form),
                int(r.tax_year), str(r.status), bool(r.extended), original,
                cast("date | None", extended_to), tuple(sets),
            )
        )  # fmt: skip
    return out


def _in(window: FilingDeadlineWindow, day: date) -> bool:
    return window.start <= day <= window.end


async def return_facts(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
    t = cast(TenantContext, tenant)
    found = [r for r in await _returns(t) if _in(window, r.due_on)]
    scopes = await _scopes(t, [r.engagement_id for r in found])
    return [
        FilingDeadlineFact(
            source_kind="tax_return",
            source_ref=str(r.work_item_id),
            filing_label=_label(r.form, r.tax_year),
            client_id=scopes[r.engagement_id].client_id,
            office_id=scopes[r.engagement_id].office_id,
            service_line="tax",
            original_due_on=r.original_due_on,
            due_on=r.due_on,
            stage_code=r.status,
            owner_user_ids=scopes[r.engagement_id].owners,
            signer_user_id=scopes[r.engagement_id].signer,
            reference_set_version_ids=r.sets,
            rule_key=FORM_LABEL.get(r.form, r.form),  # DF-10's offsets are per form (T-08-T44)
            extension_form=EXTENSION_FORM.get(r.form) if r.extended_due_on else None,
            extended_due_on=r.extended_due_on,
            done=r.done,
            work_item_id=r.work_item_id,
        )
        for r in found
    ]


_EXTENSIONS: Final = text(
    "SELECT id, engagement_id, work_item_id, tax_year, jurisdiction, form, status, "
    "original_due_on, extended_due_on, filed_on, due_rules_version_id FROM filing_extensions "
    "WHERE original_due_on BETWEEN :start AND :end ORDER BY original_due_on, id"
)


async def extension_facts(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
    t = cast(TenantContext, tenant)
    async with tenant_session(t) as session:
        rows = (
            await session.execute(_EXTENSIONS, {"start": window.start, "end": window.end})
        ).all()
    scopes = await _scopes(t, [cast(UUID, r.engagement_id) for r in rows])
    out: list[FilingDeadlineFact] = []
    for r in rows:
        s = scopes[cast(UUID, r.engagement_id)]
        where = "" if str(r.jurisdiction) == "US" else f" ({r.jurisdiction})"
        out.append(
            FilingDeadlineFact(
                source_kind="extension", source_ref=f"extension:{r.id}",
                filing_label=f"Form {r.form} extension · {r.tax_year}{where}",
                client_id=s.client_id, office_id=s.office_id, service_line="tax",
                original_due_on=r.original_due_on, due_on=r.original_due_on,
                stage_code=str(r.status), owner_user_ids=s.owners, signer_user_id=s.signer,
                reference_set_version_ids=() if r.due_rules_version_id is None
                else (cast(UUID, r.due_rules_version_id),),
                extension_form=str(r.form), extension_filed_on=r.filed_on,
                extended_due_on=r.extended_due_on, done=str(r.status) in DONE,
                work_item_id=cast(UUID, r.work_item_id),
            )
        )  # fmt: skip
    return out


_INSTALLMENTS: Final = text(
    "SELECT i.due_on, i.quarter, s.form, s.tax_year, i.status, r.engagement_id, "
    "i.due_rules_version_id FROM estimate_installments i "
    "JOIN estimate_schedules s ON s.id = i.schedule_id "
    "LEFT JOIN tax_returns r ON r.work_item_id = s.basis_tax_return_id "
    "WHERE i.due_on BETWEEN :start AND :end ORDER BY i.due_on, s.form, i.quarter"
)
ESTIMATE_DONE: Final = frozenset({"paid", "scheduled", "not_required"})


async def estimate_facts(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
    """One row a day and form: the firm's batch of installments due ("Form 1040-ES Q3 ·
    2026"), its owners the union of the clients' teams; done when every one is."""
    t = cast(TenantContext, tenant)
    async with tenant_session(t) as session:
        rows = (
            await session.execute(_INSTALLMENTS, {"start": window.start, "end": window.end})
        ).all()
    engagements = [cast(UUID, r.engagement_id) for r in rows if r.engagement_id is not None]
    scopes = await _scopes(t, engagements)
    batches: dict[tuple[date, str, int, int], list[object]] = {}
    for r in rows:
        batches.setdefault((r.due_on, str(r.form), int(r.quarter), int(r.tax_year)), []).append(r)
    out: list[FilingDeadlineFact] = []
    for (due, form, quarter, year), items in sorted(batches.items()):
        owners: set[UUID] = set()
        sets: set[UUID] = set()
        for item in items:
            engagement = getattr(item, "engagement_id", None)
            if engagement is not None:
                owners |= set(scopes[cast(UUID, engagement)].owners)
            rule = getattr(item, "due_rules_version_id", None)
            if rule is not None:
                sets.add(cast(UUID, rule))
        out.append(
            FilingDeadlineFact(
                source_kind="estimate_batch", source_ref=f"estimates:{due}:{form}",
                filing_label=f"Form {form} Q{quarter} · {year}", client_id=None, office_id=None,
                service_line="tax", original_due_on=due, due_on=due, stage_code="installments",
                owner_user_ids=tuple(sorted(owners, key=str)),
                reference_set_version_ids=tuple(sorted(sets, key=str)),
                done=all(str(getattr(i, "status", "")) in ESTIMATE_DONE for i in items),
            )
        )  # fmt: skip
    return out


async def fiduciary_statement_facts(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
    """Form 8971 (and its Schedules A): 30 days after the 706 is due (§6035(a)(3))."""
    t = cast(TenantContext, tenant)
    found = [r for r in await _returns(t) if r.form == "706"]
    found = [r for r in found if _in(window, r.due_on + timedelta(days=30))]
    scopes = await _scopes(t, [r.engagement_id for r in found])
    return [
        FilingDeadlineFact(
            source_kind="fiduciary_statement",
            source_ref=f"form_8971:{r.work_item_id}",
            filing_label=f"Form 8971 · {r.tax_year}",
            client_id=scopes[r.engagement_id].client_id,
            office_id=scopes[r.engagement_id].office_id,
            service_line="tax",
            original_due_on=r.due_on + timedelta(days=30),
            due_on=r.due_on + timedelta(days=30),
            stage_code=r.status,
            owner_user_ids=scopes[r.engagement_id].owners,
            signer_user_id=scopes[r.engagement_id].signer,
            done=r.done,
            work_item_id=r.work_item_id,
        )
        for r in found
    ]


_TRUSTS: Final = text(
    "SELECT r.work_item_id, r.engagement_id, r.tax_year, r.client_entity_id, "
    "(SELECT e.window_end FROM sixty_five_day_elections e WHERE e.client_entity_id = "
    " r.client_entity_id AND e.tax_year = r.tax_year ORDER BY e.seq DESC LIMIT 1) AS window_end, "
    "(SELECT e.status FROM sixty_five_day_elections e WHERE e.client_entity_id = "
    " r.client_entity_id AND e.tax_year = r.tax_year ORDER BY e.seq DESC LIMIT 1) AS decided "
    "FROM tax_returns r WHERE r.form = '1041' ORDER BY r.work_item_id"
)


def sixty_five_day_end(tax_year: int) -> date:
    """§663(b)(2): the 65th day after the close of the (calendar) tax year."""
    return date(tax_year, 12, 31) + timedelta(days=SIXTY_FIVE_DAYS)


async def election_window_facts(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
    t = cast(TenantContext, tenant)
    async with tenant_session(t) as session:
        rows = (await session.execute(_TRUSTS)).all()
    dated = [
        (r, cast("date | None", r.window_end) or sixty_five_day_end(int(r.tax_year))) for r in rows
    ]
    dated = [(r, d) for r, d in dated if _in(window, d)]
    scopes = await _scopes(t, [cast(UUID, r.engagement_id) for r, _ in dated])
    return [
        FilingDeadlineFact(
            source_kind="election_window",
            source_ref=f"election_65_day:{r.work_item_id}",
            filing_label=f"§663(b) 65-day election · {r.tax_year}",
            client_id=scopes[cast(UUID, r.engagement_id)].client_id,
            office_id=scopes[cast(UUID, r.engagement_id)].office_id,
            service_line="tax",
            original_due_on=d,
            due_on=d,
            stage_code="decided" if r.decided is not None else "open",
            owner_user_ids=scopes[cast(UUID, r.engagement_id)].owners,
            signer_user_id=scopes[cast(UUID, r.engagement_id)].signer,
            done=r.decided is not None,
            work_item_id=cast(UUID, r.work_item_id),
        )
        for r, d in dated
    ]


def register() -> None:
    from abacus.modules.platform.api import register_filing_deadline_source

    register_filing_deadline_source("tax_return", return_facts)
    register_filing_deadline_source("extension", extension_facts)
    register_filing_deadline_source("estimate_batch", estimate_facts)
    register_filing_deadline_source("fiduciary_statement", fiduciary_statement_facts)
    register_filing_deadline_source("election_window", election_window_facts)


__all__ = [
    "EXTENSION_FORM",
    "election_window_facts",
    "estimate_facts",
    "extension_facts",
    "fiduciary_statement_facts",
    "register",
    "return_facts",
    "sixty_five_day_end",
]
