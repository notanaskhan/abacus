"""§7216 consent renewals as filing-deadline facts (T-08-T18; TASK-8839; SPEC-710 AC-20; FD-1;
HOME-03; DEC-5841). RED: a reader registered to platform's slot (kind `consent`).

A signed consent whose term ends in the window is one fact: the words "§7216 consent renewal",
the client, the expiry date as the due date, the consent set's creator as owner (requests out for
signature are signatures' envelope facts). A consent superseded by a newer signed one is done.
Metadata only: no consent text, no purpose wording, no TIN, never an amount.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import FilingDeadlineFact, FilingDeadlineWindow

KIND: Final = "consent"
LABEL: Final = "§7216 consent renewal"
_ROWS: Final = text(
    "SELECT c.id, c.client_id, c.status, s.created_by, "
    "(c.expires_at AT TIME ZONE 'America/Chicago')::date AS due_on FROM consents c "
    "LEFT JOIN consent_sets s ON s.tenant_id = c.tenant_id AND s.id = c.consent_set_id "
    "WHERE c.expires_at IS NOT NULL AND c.status IN ('signed', 'superseded') "
    "AND (c.expires_at AT TIME ZONE 'America/Chicago')::date BETWEEN :start AND :end "
    "ORDER BY due_on, c.id"
)


async def consent_deadlines(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
    t = cast(TenantContext, tenant)
    async with tenant_session(t) as session:
        rows = (await session.execute(_ROWS, {"start": window.start, "end": window.end})).all()
    return [
        FilingDeadlineFact(
            source_kind=KIND,
            source_ref=f"consent:{r.id}",
            filing_label=LABEL,
            client_id=UUID(str(r.client_id)),
            office_id=None,
            service_line="tax",
            original_due_on=r.due_on,
            due_on=r.due_on,
            stage_code="renewed" if str(r.status) == "superseded" else "renewal_due",
            owner_user_ids=() if r.created_by is None else (UUID(str(r.created_by)),),
            done=str(r.status) == "superseded",
        )
        for r in rows
    ]


def register() -> None:
    from abacus.modules.platform.api import register_filing_deadline_source

    register_filing_deadline_source(KIND, consent_deadlines)


__all__ = ["KIND", "LABEL", "consent_deadlines", "register"]
