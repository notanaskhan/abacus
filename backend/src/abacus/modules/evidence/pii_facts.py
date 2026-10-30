"""What P-03's PII scan says about a version, for another module's pre-send check (N-02-T20;
SIG-02's "no SSN visible in the signer packet"; DEC-1178).

`tin_exposure` answers per version, from the current detector's run only: `clear` (every page
scanned and no SSN or ITIN found), `tin_found`, or `unchecked` (no run, or a page that could not
be scanned: a scan before OCR). Unchecked is never read as clear. Kinds and counts only; never a
value or a region.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import func, select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.models import PiiRegion, PiiScanRun
from abacus.modules.evidence.pii import DETECTOR_VERSION

Exposure = Literal["clear", "tin_found", "unchecked"]
_PERSONAL_TINS: Final = ("ssn", "itin")


async def tin_exposure(tenant: TenantContext, version_ids: Sequence[UUID]) -> dict[UUID, Exposure]:
    """Per version: whether a person's TIN is on its pages, as the current scan found."""
    ids = list(dict.fromkeys(version_ids))
    if not ids:
        return {}
    async with tenant_session(tenant) as session:
        runs = {
            r.evidence_version_id: r
            for r in await session.scalars(
                select(PiiScanRun).where(
                    PiiScanRun.evidence_version_id.in_(ids),
                    PiiScanRun.derivation_id.is_(None),
                    PiiScanRun.detector_version == DETECTOR_VERSION,
                )
            )
        }
        counted = await session.execute(
            select(PiiRegion.evidence_version_id, func.count())
            .where(
                PiiRegion.evidence_version_id.in_(ids),
                PiiRegion.derivation_id.is_(None),
                PiiRegion.detector_version == DETECTOR_VERSION,
                PiiRegion.kind.in_(_PERSONAL_TINS),
            )
            .group_by(PiiRegion.evidence_version_id)
        )
        found: dict[UUID | None, int] = {v: int(n) for v, n in counted.all()}
    out: dict[UUID, Exposure] = {}
    for version in ids:
        run = runs.get(version)
        if found.get(version):
            out[version] = "tin_found"
        elif run is None or run.pages_not_scannable:
            out[version] = "unchecked"
        else:
            out[version] = "clear"
    return out
