"""Envelope due dates as filing-deadline facts (T-08-T18; TASK-8839; SPEC-710 AC-20; FD-1; HOME-03;
DEC-5841). RED: a reader registered to platform's slot (`register_filing_deadline_source`, kind
`envelope`); practice builds the read model and never imports signatures.

Each envelope out for signature (sent, viewed or partially signed) with a due date in the window
is one fact: the purpose's words (Engagement letter, Form 8879-F, …), the client, the due date,
the sender as owner and the signer of record when it is a firm user; a completed envelope is done.
Metadata only: no document content, no title, no message, never an amount. Letters, §7216 consent
envelopes and 8879s all arrive here; organisations' kind `consent` is the consents' own renewal
dates (a signed consent expiring), a different deadline.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import FilingDeadlineFact, FilingDeadlineWindow

KIND: Final = "envelope"
LABELS: Final[dict[str, str]] = {
    "engagement_letter": "Engagement letter",
    "consent_7216": "§7216 consent",
    "form_8879": "Form 8879",
    "form_8879_pe": "Form 8879-PE",
    "form_8879_f": "Form 8879-F",
    "form_2848": "Form 2848",
    "form_8821": "Form 8821",
    "rep_letter": "Representation letter",
    "governance_letter": "Governance letter",
    "notice_response": "Notice response",
    "confirmation_authorization": "Confirmation authorization",
    "system_description_approval": "System description approval",
    "other": "Signature request",
}
TAX_PURPOSES: Final = frozenset(
    {"consent_7216", "form_8879", "form_8879_pe", "form_8879_f", "form_2848", "form_8821"}
)
OPEN: Final = ("sent", "viewed", "partially_signed", "completed")
_ROWS: Final = text(
    "SELECT e.id, e.purpose, e.client_id, e.engagement_id, e.work_item_id, e.due_on, e.status, "
    "e.sent_by FROM envelopes e WHERE e.due_on BETWEEN :start AND :end "
    "AND e.status = ANY(:open) ORDER BY e.due_on, e.id"
)


async def envelope_deadlines(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
    from abacus.modules.engagements.api import service_line_of

    t = cast(TenantContext, tenant)
    async with tenant_session(t) as session:
        rows = (
            await session.execute(
                _ROWS, {"start": window.start, "end": window.end, "open": list(OPEN)}
            )
        ).all()
    out: list[FilingDeadlineFact] = []
    for r in rows:
        purpose = str(r.purpose)
        line = "tax" if purpose in TAX_PURPOSES else None
        if line is None and r.engagement_id is not None:
            line = await service_line_of(t, UUID(str(r.engagement_id)))
        out.append(
            FilingDeadlineFact(
                source_kind=KIND,
                source_ref=f"envelope:{r.id}",
                filing_label=LABELS.get(purpose, LABELS["other"]),
                client_id=UUID(str(r.client_id)),
                office_id=None,
                service_line=line if line in ("tax", "audit", "cas", "advisory") else "advisory",
                original_due_on=r.due_on,
                due_on=r.due_on,
                stage_code="signed" if str(r.status) == "completed" else "awaiting_signature",
                owner_user_ids=() if r.sent_by is None else (UUID(str(r.sent_by)),),
                done=str(r.status) == "completed",
                work_item_id=None if r.work_item_id is None else UUID(str(r.work_item_id)),
            )
        )
    return out


def register() -> None:
    from abacus.modules.platform.api import register_filing_deadline_source

    register_filing_deadline_source(KIND, envelope_deadlines)


__all__ = ["KIND", "LABELS", "envelope_deadlines", "register"]
