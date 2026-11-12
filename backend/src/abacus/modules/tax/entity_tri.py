"""An entity return's tax return information (T-05-T22; T-05 §4.2 M3, §7; ADR-167; C19; DEC-4404).

- **TRI register** (`TRI_RECORDS`): the stored values that are TRI (§7216), so Restricted with the
  `tri` flag (ADR-167 §1; "no Confidential TRI"): every workbook cell value and version body of a
  `tax_workbook`, a preparer memo's sections, a planning opportunity's body and a K-1's box
  values. The contracts tag the same fields `Tri` (`workbook_contract`); the partner TIN is
  Restricted with `pii_kind` tin and never TRI-shown (only its last four).
- **Data subjects** (`entity_return_subjects`): an entity return's §7216 subject is the
  partnership, its filing entity for the return's year (the partnership's consent set covers
  the return, its workbook, its memo and its K-1 drafts). A return whose entity or period is
  unknown answers a subject with `None`, which the gateway refuses (fail closed).
- **Retention** (`retain_until`): `tax_workbook` and `preparer_memo` are record types anchored on
  the filing date; the years are the firm's policy or the published floor (content, P-14).
- **Legal holds** (`on_hold`): a return whose engagement an open hold covers keeps every
  workbook and memo version, whatever its retain-until; unknown facts read held.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final
from uuid import UUID

from abacus.ai_gateway import DataSubject
from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import work_item_engagement, work_item_tri_subject
from abacus.modules.evidence.api import RECORD_TYPES, engagement_on_hold, retain_until_for

SERVICE_LINE: Final = "tax"
RETENTION_TYPES: Final = frozenset({"tax_workbook", "preparer_memo"})
# (table, column, the condition that makes a row TRI): every value here is Restricted with `tri`.
TRI_RECORDS: Final[tuple[tuple[str, str, str], ...]] = (
    ("workpaper_cells", "value", "the workpaper's kind is tax_workbook"),
    ("workpaper_cells", "raw", "the workpaper's kind is tax_workbook"),
    ("workpaper_versions", "content", "the workpaper's kind is tax_workbook"),
    ("preparer_memo_versions", "sections", "always"),
    ("planning_opportunities", "body", "always"),
    ("k1_box_lines", "amount", "the package's return is an entity return"),
    ("k1_handoffs", "final_values", "the package's return is an entity return"),
    ("allocation_results", "amount", "always"),
    ("ownership_periods", "profit_pct", "always"),
)


async def entity_return_subjects(
    tenant: TenantContext, return_id: UUID
) -> tuple[DataSubject, ...]:
    """The return's §7216 data subjects: the partnership for the return's year (module
    docstring). An unknown return is one unresolved subject, so a model call fails closed."""
    subject = await work_item_tri_subject(tenant, return_id)
    if subject is None:
        return (DataSubject(None, None),)
    return (subject,)


async def retain_until(
    tenant: TenantContext, record_type: str, filed_at: datetime
) -> datetime | None:
    """When a workbook or memo version of a return filed at `filed_at` may first be released:
    the longer of the firm's policy and the published floor. None while neither is loaded (the
    record is kept)."""
    if record_type not in RETENTION_TYPES or record_type not in RECORD_TYPES:
        raise ValueError(f"not an entity return record type: {record_type!r}")
    return await retain_until_for(tenant, record_type, SERVICE_LINE, filed_at)


async def on_hold(tenant: TenantContext, return_id: UUID) -> bool:
    """Whether a legal hold keeps the return's workbook and memo versions (unknown: held)."""
    engagement = await work_item_engagement(tenant, return_id)
    if engagement is None:
        return True
    return await engagement_on_hold(tenant, engagement)


async def releasable(
    tenant: TenantContext, return_id: UUID, record_type: str, filed_at: datetime, now: datetime
) -> bool:
    """A version may be released only past its retain-until and under no hold (fail closed: no
    policy, no floor, an unknown return or a hold all keep it)."""
    until = await retain_until(tenant, record_type, filed_at)
    if until is None or now < until:
        return False
    return not await on_hold(tenant, return_id)


__all__ = [
    "RETENTION_TYPES",
    "SERVICE_LINE",
    "TRI_RECORDS",
    "entity_return_subjects",
    "on_hold",
    "releasable",
    "retain_until",
]
