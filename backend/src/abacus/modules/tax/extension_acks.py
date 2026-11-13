"""T-03-T08: extension acknowledgements (red; T-03 §3 F5; TAX-13; DEC-2244).

An imported CCH status report whose rows name an extension form (4868, 7004, 8868, 4768,
IT-370) resolves each row to its `filing_extensions` row by return, jurisdiction and form, in
the importing unit of work: accepted, or rejected with its reject code; `filing.acknowledged`
carries the extension as its target. Extension rows never become return acks (`efile_acks`).
Accrued never transmits an extension and holds no ERO role for one (DEC-49): this only records
what the firm's engine received.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.tax.engine_adapter import Ack

# The report's `federal` is the extension's `US` (filing_extensions.jurisdiction is upper case).
_JURISDICTION: Final = {"federal": "US"}


def jurisdiction_of(report: str) -> str:
    return _JURISDICTION.get(report, report)


async def resolve(
    tx: UnitOfWork, return_id: UUID, engagement_id: UUID | None, acks: Sequence[Ack]
) -> list[UUID]:
    """Each extension ack onto its extension; unmatched rows are left (audited, never guessed)."""
    from abacus.modules.tax.filing import FilingAcknowledged

    resolved: list[UUID] = []
    for ack in (a for a in acks if a.extension):
        found = (
            await tx.session.execute(
                text(
                    "UPDATE filing_extensions SET status = :s, ack_received_at = "
                    "CAST(:at AS timestamptz), reject_code = :rc, row_version = row_version + 1 "
                    "WHERE tax_return_id = :r AND jurisdiction = :j AND form = :f "
                    "RETURNING id"
                ),
                {
                    "s": ack.status,
                    "at": ack.status_at,
                    "rc": ack.reject_code if ack.status == "rejected" else None,
                    "r": return_id,
                    "j": jurisdiction_of(ack.jurisdiction),
                    "f": ack.form,
                },
            )
        ).scalar()
        if found is None:
            tx.record(
                "filing_extension.ack_unmatched",
                target=Target("work_item", return_id),
                # Ref holds ids only: the form and jurisdiction are codes, so the ack's digest.
                after=Ref(
                    ack=hashlib.sha256(f"{ack.form}:{ack.jurisdiction}".encode()).hexdigest()
                ),
            )
            continue
        extension_id = UUID(str(found))
        resolved.append(extension_id)
        tx.record(
            "filing_extension.acknowledged",
            target=Target("work_item", return_id),
            after=Ref(extension=extension_id, accepted=int(ack.status == "accepted")),
        )
        tx.emit(
            FilingAcknowledged(
                return_id=return_id,
                engagement_id=engagement_id,
                status=ack.status,
                jurisdictions=[jurisdiction_of(ack.jurisdiction)],
                extension_id=extension_id,
                reject_code=ack.reject_code if ack.status == "rejected" else None,
            )
        )
    return resolved
