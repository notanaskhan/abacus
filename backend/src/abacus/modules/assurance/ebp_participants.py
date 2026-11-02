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

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
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


_SOURCE_MASKED: Final = re.compile(r"^[Xx•*]{3}-?[Xx•*]{2}-?([0-9]{4})$")


def source_masked_last4(ssn: str) -> str | None:
    """The last four of an SSN the client's file already masks ("XXX-XX-4417"), else None."""
    m = _SOURCE_MASKED.match(ssn.strip())
    return None if m is None else m.group(1)


async def seal_pii(
    tenant_id: UUID, import_id: UUID, participant_key: str, ssn: str | None, dob: date | None
) -> SealedPii:
    """A full SSN is sealed as nine digits. One the client's file already masks is sealed as the
    file gave it, its fingerprint marked `masked:` so it never matches a full SSN's (DEC-2068)."""
    masked = None if ssn is None else source_masked_last4(ssn)
    if ssn is None:
        ssn_text = None
    elif masked is not None:
        ssn_text = f"XXX-XX-{masked}"
    else:
        ssn_text = "".join(c for c in ssn if c.isdigit())
        if len(ssn_text) != 9:
            raise ValueError("an SSN has nine digits")
    ssn_sealed = (
        None
        if ssn_text is None
        else await seal(tenant_id, ssn_text.encode(), binding(import_id, participant_key, "ssn"))
    )
    dob_text = None if dob is None else dob.isoformat()
    dob_sealed = (
        None
        if dob_text is None
        else await seal(tenant_id, dob_text.encode(), binding(import_id, participant_key, "dob"))
    )
    fp_input = None if ssn_text is None else (ssn_text if masked is None else f"masked:{masked}")
    return SealedPii(
        ssn_sealed,
        None if fp_input is None else fingerprint_tin(tenant_id, fp_input).hex(),
        None if ssn_text is None else ssn_text[-4:],
        dob_sealed,
        None if dob_text is None else fingerprint_tin(tenant_id, f"dob:{dob_text}").hex(),
    )


def dob_fingerprint(tenant_id: UUID, dob: date) -> str:
    """Code compares an HR record's date of birth to the census by this, never by opening it."""
    return fingerprint_tin(tenant_id, f"dob:{dob.isoformat()}").hex()


@dataclass(frozen=True)
class ParticipantRow:
    id: UUID
    participant_key: str
    name: str
    ssn_last4: str | None
    status: str
    compensation: Decimal | None


_LIST = text(
    "SELECT p.id, p.participant_key, p.name, p.ssn_last4, p.status, p.compensation "
    "FROM ebp_participants p WHERE p.work_item_id = :w AND p.import_id = ("
    "SELECT i.id FROM ebp_source_imports i WHERE i.work_item_id = :w AND i.kind = 'census' "
    "AND i.status = 'imported' ORDER BY i.created_at DESC LIMIT 1) "
    "AND (CAST(:q AS text) IS NULL OR p.name ILIKE :like OR p.participant_key ILIKE :like) "
    "ORDER BY p.participant_key"
)


async def participants_of(
    ctx: AuthContext, work_item_id: UUID, q: str | None, limit: int = 500
) -> tuple[list[ParticipantRow], int]:
    """The latest imported census's participants, masked fields only (never a sealed value)."""
    like = None if q is None else "%" + q.replace("\\", "").replace("%", "").replace("_", "") + "%"
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_LIST, {"w": work_item_id, "q": q, "like": like})).all()
    found = [
        ParticipantRow(r.id, r.participant_key, r.name, r.ssn_last4, r.status, r.compensation)
        for r in rows
    ]
    return found[:limit], len(found)


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
