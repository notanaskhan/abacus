"""C18's `proposed_entry` kind (R-02-T11; R-02 §3.1; SPEC-646 AC-4 to AC-7; DEC-3009). PROTECTED
(red).

The provider the portal's approvals service composes for POR-08 e: an entry is before the client
once its send was delivered (a `sent_to_client` decision row, A-06-T10, and the held grant
consumed); it is waiting while the entry is `approved`, and decided once the client accepts
(`client_approved`) or declines (`client_declined`).

`apply_client_decision(tx, entry_id, decision, context)` is the one write: inside the approvals
service's unit of work, one insert-only, human-only `proposed_entry_decisions` row with channel
`portal`, principal `client_user` and the client's grant; the entry's status; the owners' hooks
(A-06's misstatements read Booked or Uncorrected); `proposed_entry.client_decided`; and an audit
row naming the client contact, grant and MFA time. Only C18's service calls it
(CLIENT-DECISION-001). Nothing is posted to a client ledger (ADR-040, AC-10).

The client sees the entry's ref, description, amount and lines; never the threshold result, the
policy, the review state or who proposed it (AC-7).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import RowMapping, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork
from abacus.modules.adjustments.decisions import ClientDecision as EntryDecisionWord
from abacus.modules.adjustments.decisions import EntriesMoved, EntryClientDecided, decision_hooks
from abacus.modules.adjustments.entries import TARGET
from abacus.modules.engagements.api import (
    ApprovalFacts,
    ApprovalItem,
    ApprovalLine,
    ClientApprovalState,
    ClientDecision,
    ClientDecisionContext,
)

# A sent entry, waiting or decided, on a scope (its work item or its engagement).
_SENT = (
    "SELECT e.id, e.engagement_id, e.work_item_id, e.ref, e.description, e.amount, e.status, "
    "e.version, e.is_attest_client, e.misstatement_id FROM proposed_entries e "
    "WHERE EXISTS (SELECT 1 FROM proposed_entry_decisions d WHERE d.entry_id = e.id "
    "AND d.decision = 'sent_to_client') "
    "AND e.status IN ('approved', 'client_approved', 'client_declined')"
)
# Constant SQL only: the two filters append fixed text to `_SENT`; values are bound parameters.
_ON_SCOPE_SQL = _SENT + " AND (e.work_item_id = :scope OR e.engagement_id = :scope) ORDER BY e.ref"
_ONE_SQL = _SENT + " AND e.id = :id"
_ON_SCOPE = text(_ON_SCOPE_SQL)
_ONE = text(_ONE_SQL)
_LINES = text(
    "SELECT entry_id, line_no, account_code, account_name, debit, credit "
    "FROM proposed_entry_lines WHERE entry_id = ANY(:ids) ORDER BY entry_id, line_no"
).bindparams(bindparam("ids", type_=ARRAY(PgUUID(as_uuid=True))))
_CLIENT_DECISION = text(
    "SELECT DISTINCT ON (entry_id) entry_id, decision, reason_code, created_at "
    "FROM proposed_entry_decisions WHERE entry_id = ANY(:ids) AND channel = 'portal' "
    "AND decision IN ('client_accepted', 'client_declined') ORDER BY entry_id, created_at DESC"
).bindparams(bindparam("ids", type_=ARRAY(PgUUID(as_uuid=True))))
_STATE: Final[dict[str, ClientApprovalState]] = {
    "approved": "waiting",
    "client_approved": "accepted",
    "client_declined": "declined",
}
_WORD: Final = {"accept": "client_accepted", "decline": "client_declined"}
_STATUS: Final = {"client_accepted": "client_approved", "client_declined": "client_declined"}


def seen_hash(
    entry_id: UUID,
    version: int,
    amount: Decimal,
    description: str | None,
    lines: Sequence[ApprovalLine],
) -> str:
    """What the client saw (AC-4): the entry's version, amount, words and lines."""
    body = {
        "id": str(entry_id),
        "version": version,
        "amount": f"{amount:.2f}",
        "description": description or "",
        "lines": [
            [line.account, f"{line.debit or 0:.2f}", f"{line.credit or 0:.2f}"] for line in lines
        ],
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def _label(code: str, name: str | None) -> str:
    return f"{code} {name}" if name else code


Row = RowMapping


async def _items(tenant: TenantContext, rows: Sequence[Row]) -> list[ApprovalItem]:
    ids = [cast(UUID, r["id"]) for r in rows]
    if not ids:
        return []
    async with tenant_session(tenant) as session:
        lines: dict[UUID, list[ApprovalLine]] = {}
        for line in (await session.execute(_LINES, {"ids": ids})).all():
            lines.setdefault(line.entry_id, []).append(
                ApprovalLine(
                    _label(line.account_code, line.account_name),
                    line.debit if line.debit else None,
                    line.credit if line.credit else None,
                )
            )
        decided = {
            d.entry_id: d for d in (await session.execute(_CLIENT_DECISION, {"ids": ids})).all()
        }
    out: list[ApprovalItem] = []
    for r in rows:
        entry_id = cast(UUID, r["id"])
        entry_lines = lines.get(entry_id, [])
        d = decided.get(entry_id)
        amount = cast(Decimal, r["amount"])
        description = cast(str | None, r["description"])
        ref = str(r["ref"])
        out.append(
            ApprovalItem(
                kind="proposed_entry",
                item_id=entry_id,
                scope_kind="work_item",
                scope_id=cast(UUID, r["work_item_id"]),
                sent_to_client=True,
                title=f"{ref} · {description}" if description else ref,
                state=_STATE[str(r["status"])],
                seen_hash=seen_hash(
                    entry_id, cast(int, r["version"]), amount, description, entry_lines
                ),
                amount=amount,
                lines=tuple(entry_lines),
                decided_at=None if d is None else d.created_at,
                reason_code=None if d is None or d.reason_code is None else "other",
            )
        )
    return out


class ProposedEntryApprovals:
    """C18's `proposed_entry` provider (registered from `adjustments.api`)."""

    async def items(self, tenant: TenantContext, scope_id: UUID) -> Sequence[ApprovalItem]:
        async with tenant_session(tenant) as session:
            rows = (await session.execute(_ON_SCOPE, {"scope": scope_id})).mappings().all()
        return await _items(tenant, rows)

    async def item(self, tenant: TenantContext, item_id: UUID) -> ApprovalItem | None:
        async with tenant_session(tenant) as session:
            row = (await session.execute(_ONE, {"id": item_id})).mappings().first()
        if row is None:
            return None
        found = await _items(tenant, [row])
        return found[0] if found else None

    async def decide(
        self,
        tx: UnitOfWork,
        item_id: UUID,
        decision: ClientDecision,
        context: ClientDecisionContext,
    ) -> ApprovalItem:
        return await apply_client_decision(tx, item_id, decision, context)

    async def facts(self, tenant: TenantContext, item_id: UUID) -> ApprovalFacts:
        async with tenant_session(tenant) as session:
            row = (await session.execute(_ONE, {"id": item_id})).first()
        if row is None:
            raise NotFound(TARGET)
        return ApprovalFacts(bool(row.is_attest_client), row.work_item_id)


async def apply_client_decision(
    tx: UnitOfWork, entry_id: UUID, decision: ClientDecision, context: ClientDecisionContext
) -> ApprovalItem:
    """The client's accept or decline (module docstring), in the caller's unit of work."""
    word = _WORD.get(decision.decision)
    if word is None:
        raise EntriesMoved(facts={"status": "decision"})
    row = (
        (
            await tx.session.execute(
                text(
                    "SELECT id, tenant_id, engagement_id, work_item_id, status, version, "
                    "misstatement_id FROM proposed_entries WHERE id = :id FOR UPDATE"
                ),
                {"id": entry_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise NotFound(TARGET)
    if row["status"] != "approved":
        raise EntriesMoved(facts={"status": str(row["status"])})
    tenant_id = cast(UUID, row["tenant_id"])
    sealed = (
        None
        if decision.note is None
        else await seal(tenant_id, decision.note.encode(), "adjustments.note")
    )
    await tx.session.execute(
        text(
            "INSERT INTO proposed_entry_decisions (tenant_id, engagement_id, work_item_id, "
            "entry_id, decision, actor_principal, client_grant_id, channel, reason_code, "
            "note_sealed, seen_version) VALUES (:t, :e, :w, :id, :d, 'client_user', :g, "
            "'portal', :r, :n, :v)"
        ),
        {
            "t": tenant_id,
            "e": row["engagement_id"],
            "w": row["work_item_id"],
            "id": entry_id,
            "d": word,
            "g": context.grant_id,
            "r": decision.reason_code,
            "n": sealed,
            "v": row["version"],
        },
    )
    await tx.session.execute(
        text("UPDATE proposed_entries SET status = :s, version = version + 1 WHERE id = :id"),
        {"s": _STATUS[word], "id": entry_id},
    )
    for hook in decision_hooks():
        await hook(tx, entry_id, row["misstatement_id"], cast(EntryDecisionWord, word))
    tx.emit(
        EntryClientDecided(
            entry_id=entry_id,
            engagement_id=row["engagement_id"],
            work_item_id=row["work_item_id"],
            decision=word,
        )
    )
    tx.record(
        # The decision is the action ("proposed_entry.client_accepted" or "...client_declined"):
        # references carry identifiers only; the basis and second-factor time are on the row.
        f"proposed_entry.{word}",
        target=Target(TARGET, entry_id),
        after=Ref(
            contact=context.contact_id,
            grant=context.grant_id,
            session=context.session_id,
        ),
        scope=Scope(engagement_id=row["engagement_id"], work_item_id=row["work_item_id"]),
    )
    state: ClientApprovalState = "accepted" if word == "client_accepted" else "declined"
    return ApprovalItem(
        kind="proposed_entry",
        item_id=entry_id,
        scope_kind="work_item",
        scope_id=row["work_item_id"],
        sent_to_client=True,
        title="",
        state=state,
        seen_hash="",
    )
