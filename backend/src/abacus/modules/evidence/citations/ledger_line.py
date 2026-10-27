"""The `ledger_line` citable: a line of an immutable ledger snapshot (A-02-T22; TASK-1470; P-48,
ADR-144, ADR-166 §2; C4 §3.1). PROTECTED.

Registered from evidence (evidence → ledger is an existing edge), so `ledger` stays
dependency-free. Locator `{ledger_snapshot_id, account_code}`; the match id is
`led:<snapshot>:<account>` and `source_version` the snapshot id.

- The verifier authorises `trial_balance.read` on the anchor's engagement before it reads
  anything (no engagement, a wall, a role, an agent: `source_not_visible`), so it is never an
  oracle across engagements. A snapshot that isn't of that engagement's client entity is
  `source_not_found`, exactly as if it didn't exist; so is an account the snapshot lacks
  (`cell_not_found`, the line's own reason, only once the snapshot is known to be the
  engagement's).
- A claimed value must equal the line as the trial balance shows it: its net (debit - credit)
  or the side it sits on. A claimed quote must be in the account name, contiguously, compared
  space- and case-folded. A claim with neither still verifies that the line exists.
- Display renders "Trial balance" and `<code> · <name>` by code (INV-2), and only for a snapshot
  of the citation's engagement's entity.
- **Moved** (`on_trial_balance_version_created`, a consumer of `trial_balance.version_created`): a
  re-version that adopts another snapshot supersedes its predecessor's, so every citation to the
  older snapshot made on that trial balance's engagement gets a `moved` event naming the new one
  (`ledger_snapshot:<id>`), once per cause (P-03-T12's detector). Citations another engagement of
  the entity made stay put: its trial balance did not move (security review M). The snapshot
  itself is never touched (ADR-004).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, transaction_context
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import UnitOfWork
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import entity_of, get_ref
from abacus.modules.evidence.citations.matching import Reason, amount
from abacus.modules.evidence.citations.registry import (
    Anchor,
    CitationClaim,
    Display,
    Verdict,
    register_citable,
    unverifiable,
)
from abacus.modules.identity.api import Actor, Forbidden, authorise
from abacus.modules.ledger.api import CitedLine, snapshot_line, superseded_snapshot

VERIFIER_VERSION: Final = "v1"
SOURCE: Final = "ledger_snapshot"
READ: Final = "trial_balance.read"
_ZERO: Final = Decimal("0.00")


class LedgerLineLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ledger_snapshot_id: Annotated[UUID, classified("internal")]
    account_code: Annotated[str, Field(min_length=1, max_length=100), classified("confidential")]


def ledger_match_id(snapshot_id: UUID, account_code: str) -> str:
    """`led:<snapshot>:<account>` (C4 §3.1)."""
    return f"led:{snapshot_id}:{account_code}"


def _folded(text: str) -> str:
    return " ".join(text.split()).casefold()


def line_reason(line: CitedLine, quote: str | None, value: str | None) -> Reason | None:
    """The claim checked against the line (pure): the value against its net or its side, the
    quote against the account name."""
    if value is not None:
        found = amount(value)
        net = line.debit - line.credit
        shown = {net} | {side for side in (line.debit, line.credit) if side != _ZERO}
        if found is None or found not in shown:
            return "value_mismatch"
    if quote is not None:
        wanted = _folded(quote)
        if not wanted or wanted not in _folded(line.account_name):
            return "quote_not_found"
    return None


async def _visible(actor: Actor, anchor: Anchor) -> UUID | None:
    """The anchor's engagement's entity when the actor may read its trial balance, else None
    (checked before any snapshot is read)."""
    if anchor.engagement_id is None:
        return None
    try:
        ref = await get_ref(actor, anchor.engagement_id)
        await authorise(actor, READ, ref.resource())
    except (NotFound, Forbidden):
        return None
    return ref.client_entity_id


async def verify_ledger_line(
    tx: UnitOfWork, actor: Actor, claim: CitationClaim, anchor: Anchor
) -> Verdict:
    try:
        locator = LedgerLineLocator.model_validate(dict(claim.locator))
    except ValidationError:
        return unverifiable(claim)
    kept = locator.model_dump(mode="json")
    source = (SOURCE, locator.ledger_snapshot_id)
    entity = await _visible(actor, anchor)
    if entity is None:
        return Verdict("source_not_visible", *source, kept)
    found = await snapshot_line(tx.session, locator.ledger_snapshot_id, locator.account_code)
    if found is None or found[0] != entity:
        return Verdict("source_not_found", *source, kept)
    version = str(locator.ledger_snapshot_id)
    line = found[1]
    if line is None:
        return Verdict("cell_not_found", *source, kept, version)
    reason = line_reason(line, claim.quote, claim.value)
    if reason is not None:
        return Verdict(reason, *source, kept, version)
    quoted = _folded(claim.quote) if claim.quote is not None else None
    return Verdict(
        None,
        *source,
        kept,
        version,
        ledger_match_id(line.snapshot_id, line.account_code),
        hashlib.sha256(quoted.encode()).digest() if quoted else None,
        f"{amount(claim.value)}" if claim.value is not None else None,
    )


async def display_ledger_line(
    session: AsyncSession, locator: Mapping[str, object], engagement_id: UUID | None
) -> Display:
    """ "Trial balance" · `<code> · <name>`, only for a snapshot of the citation's engagement's
    entity; otherwise the kind's name alone."""
    hidden = Display("Trial balance", "")
    try:
        snapshot_id = UUID(str(locator.get("ledger_snapshot_id")))
    except ValueError:
        return hidden
    code = locator.get("account_code")
    if engagement_id is None or not isinstance(code, str):
        return hidden
    tenant = await transaction_context(session)
    entity = await entity_of(tenant, engagement_id)
    found = await snapshot_line(session, snapshot_id, code)
    if entity is None or found is None or found[0] != entity or found[1] is None:
        return hidden
    return Display("Trial balance", f"{code} · {found[1].account_name}")


register_citable("ledger_line", verify_ledger_line, display_ledger_line, version=VERIFIER_VERSION)


# --- Moved: a re-version supersedes its predecessor's snapshot -----------------------------------


def snapshot_cause(snapshot_id: UUID) -> str:
    return f"{SOURCE}:{snapshot_id}"


async def on_trial_balance_version_created(event: OutboxEvent) -> None:
    """Citations to the snapshot a new version replaced move to its snapshot (idempotent on the
    cause; a redelivery writes nothing)."""
    from abacus.modules.evidence.citations.moved import detect_moved  # moved imports the service

    tenant = TenantContext(event.tenant_id, "system", "evidence.citations_moved")
    tb_id = UUID(str(event.payload["trial_balance_id"]))
    version_no = int(str(event.payload["version_no"]))
    found = await superseded_snapshot(tenant, tb_id, version_no)
    if found is None:
        return
    await detect_moved(
        event.tenant_id,
        SOURCE,
        snapshot_cause(found.new),
        [found.old],
        engagement_id=found.engagement_id,
    )


__all__ = [
    "VERIFIER_VERSION",
    "LedgerLineLocator",
    "display_ledger_line",
    "ledger_match_id",
    "line_reason",
    "on_trial_balance_version_created",
    "snapshot_cause",
    "verify_ledger_line",
]
