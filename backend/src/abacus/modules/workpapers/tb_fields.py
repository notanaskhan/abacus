"""The trial balance's annotated fields for P-04's field values (A-02-T17; C3
`register_field_owner`; A-02 §4.1: `wp_ref` and `area_override`).

A field key names the field and the line: `wp_ref:<account code>` or
`area_override:<account code>`. The value is the line's current annotation as AUD-06 shows it,
read from the ledger's own records (amounts are never fields: ADR-004, `amount_not_editable`).
For callers authorised on the trial balance's engagement; unknown keys, lines and trial balances
answer None. Annotations are internal working-paper references, never tax return information.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.ledger.api import trial_balance_authors, trial_balance_view
from abacus.modules.review.api import FieldOwner

TARGET: Final = "trial_balance"
FIELDS: Final = frozenset({"wp_ref", "area_override"})
MAX_ACCOUNT: Final = 64


def parse(field_key: str) -> tuple[str, str] | None:
    name, sep, account = field_key.partition(":")
    if not sep or name not in FIELDS or not 1 <= len(account) <= MAX_ACCOUNT:
        return None
    return name, account


async def tb_field_value(
    tenant: TenantContext, tb_id: UUID, field_key: str
) -> dict[str, object] | None:
    parsed = parse(field_key)
    if parsed is None:
        return None
    name, account = parsed
    authors = await trial_balance_authors(tenant, tb_id)
    if authors is None:
        return None
    try:
        view = await trial_balance_view(tenant, authors.engagement_id, tb_id)
    except NotFound:
        return None
    line = next((x for x in view.lines if x.account_code == account), None)
    if line is None:
        return None
    return {"t": "text", "v": line.wp_ref if name == "wp_ref" else line.area}


OWNER: Final = FieldOwner(TARGET, tb_field_value)
