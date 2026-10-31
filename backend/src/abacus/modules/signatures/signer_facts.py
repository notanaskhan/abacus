"""What other modules learn about a client person as a signer (N-02-T24; N-02 §3.4; P-08-T13,
P-08-T17; DEC-1286). Identifiers and counts only.

- **`envelope_signer_mfa`**, identity's MFA floor predicate `envelope_signer`: a person whose
  contact (by `contacts.user_id` or a grant) is a signer on an envelope out for signature must
  pass the second step to sign in, and a session that never did reaches nothing once they are
  (identity re-checks the floor on every request, DEC-277). It reads the firm's rows as the
  floor's system context.
- **`sign_todo`**, POR-02's Sign to-do: how many envelopes on the scope's engagements wait for the
  person's own signature, and the earliest due date. The home has already authorised those
  engagements for `portal_home.read` (`scope_only`); a signer row of someone else never counts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.api import contact_ids_of_user
from abacus.modules.identity.api import AuthContext

OUT_FOR_SIGNATURE: Final = ("sent", "viewed", "partially_signed")
_WAITING: Final = ("pending", "viewed")  # the signer's own status while it is theirs to sign

_SIGNER_OF_OPEN = text(
    "SELECT 1 FROM envelope_signers s JOIN envelopes e ON e.id = s.envelope_id "
    "WHERE s.party_kind = 'contact' AND s.contact_id = ANY(:contacts) "
    "AND e.status = ANY(:open) LIMIT 1"
)
_TODO = text(
    "SELECT count(DISTINCT e.id) AS waiting, min(e.due_on) AS due FROM envelopes e "
    "JOIN envelope_signers s ON s.envelope_id = e.id WHERE s.party_kind = 'contact' "
    "AND s.contact_id = ANY(:contacts) AND s.status = ANY(:waiting) AND e.status = ANY(:open) "
    "AND e.engagement_id = ANY(:engagements)"
)


async def envelope_signer_mfa(tenant: TenantContext, user_id: UUID) -> bool:
    """The `envelope_signer` floor predicate: a signer on an envelope out for signature."""
    contacts = sorted(await contact_ids_of_user(tenant, user_id))
    if not contacts:
        return False
    async with tenant_session(tenant) as session:
        found = await session.execute(
            _SIGNER_OF_OPEN, {"contacts": contacts, "open": list(OUT_FOR_SIGNATURE)}
        )
        return found.first() is not None


@dataclass(frozen=True)
class SignTodo:
    count: int
    due_on: date | None


async def sign_todo(ctx: AuthContext, engagement_ids: Sequence[UUID]) -> SignTodo:
    """The person's envelopes to sign on these (already authorised) engagements."""
    if not engagement_ids:
        return SignTodo(0, None)
    contacts = sorted(await contact_ids_of_user(ctx.tenant, ctx.user_id))
    if not contacts:
        return SignTodo(0, None)
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                _TODO,
                {
                    "contacts": contacts,
                    "waiting": list(_WAITING),
                    "open": list(OUT_FOR_SIGNATURE),
                    "engagements": list(engagement_ids),
                },
            )
        ).one()
    return SignTodo(int(row.waiting), row.due)
