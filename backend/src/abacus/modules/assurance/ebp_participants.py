"""A-05-T18: census PII, sealed on import and revealed one field at a time (A-05 §4.10; DEC-1858;
DEC-2067). PROTECTED (red).

A participant's SSN and date of birth are never stored or shown in the clear:

- **Sealing** (`seal_pii`, called by the census import, A-05-T19): each value sealed through
  `kernel.crypto` under the firm's key, bound to the participant's import and key and to the
  field, so a sealed value copied to another row never opens; a fingerprint (HMAC under the
  firm's fingerprint key) lets code compare census to HR without opening either; an SSN keeps its
  last four for the mask.
- **Masks**: every surface reads the mask token ("•••-••-4417", "••/••/••••"); agents get tokens
  only (ADR-064), never a sealed value.
- **Reveal** (`reveal`): one field for 30 seconds, through evidence's `reveal_field` (a person,
  `pii.reveal`: onshore and fresh MFA; agents, portal principals and third parties refused;
  twenty an hour; `pii.revealed` audited without the value; `no-store`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.evidence.api import RevealedField, reveal_field
from abacus.modules.identity.api import AuthContext
from abacus.modules.organisations.api import fingerprint_tin

Field = Literal["ssn", "dob"]
DOB_MASK: Final = "••/••/••••"


@dataclass(frozen=True)
class SealedPii:
    ssn_sealed: bytes | None
    ssn_fp: str | None
    ssn_last4: str | None
    dob_sealed: bytes | None
    dob_fp: str | None


def binding(import_id: UUID, participant_key: str, field: Field) -> str:
    """The AAD a participant's field is sealed under: it opens only as this field of this row."""
    return f"ebp_participant:{import_id}:{participant_key}:{field}"


def ssn_mask(last4: str | None) -> str | None:
    return None if last4 is None else f"•••-••-{last4}"


async def seal_pii(
    tenant_id: UUID, import_id: UUID, participant_key: str, ssn: str | None, dob: date | None
) -> SealedPii:
    digits = None if ssn is None else "".join(c for c in ssn if c.isdigit())
    if digits is not None and len(digits) != 9:
        raise ValueError("an SSN has nine digits")
    ssn_sealed = (
        None
        if digits is None
        else await seal(tenant_id, digits.encode(), binding(import_id, participant_key, "ssn"))
    )
    dob_text = None if dob is None else dob.isoformat()
    dob_sealed = (
        None
        if dob_text is None
        else await seal(tenant_id, dob_text.encode(), binding(import_id, participant_key, "dob"))
    )
    return SealedPii(
        ssn_sealed,
        None if digits is None else fingerprint_tin(tenant_id, digits).hex(),
        None if digits is None else digits[-4:],
        dob_sealed,
        None if dob_text is None else fingerprint_tin(tenant_id, f"dob:{dob_text}").hex(),
    )


def dob_fingerprint(tenant_id: UUID, dob: date) -> str:
    """Code compares an HR record's date of birth to the census by this, never by opening it."""
    return fingerprint_tin(tenant_id, f"dob:{dob.isoformat()}").hex()


async def reveal(
    ctx: AuthContext, work_item_id: UUID, participant_id: UUID, field: Field, reason: str | None
) -> RevealedField:
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT engagement_id, import_id, participant_key, ssn_sealed, dob_sealed "
                    "FROM ebp_participants WHERE id = :id AND work_item_id = :w"
                ),
                {"id": participant_id, "w": work_item_id},
            )
        ).first()
    if row is None:
        raise NotFound("ebp_participant")
    sealed = row.ssn_sealed if field == "ssn" else row.dob_sealed
    if sealed is None:
        raise NotFound("ebp_participant_field")

    async def opened() -> str:
        value = await open_sealed(
            ctx.tenant_id, bytes(sealed), binding(row.import_id, row.participant_key, field)
        )
        return value.decode()

    return await reveal_field(
        ctx,
        row.engagement_id,
        f"ebp_participant:{participant_id}:{field}",
        "ssn" if field == "ssn" else "date_of_birth",
        opened,
        context_ref=None if reason is None else reason[:120],
    )
