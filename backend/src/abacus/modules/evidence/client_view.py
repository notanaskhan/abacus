"""One request as its client sees it (SPEC-031 AC-4, AC-5, AC-7; TASK-060 D1).

Whether the platform already provided it, which bank accounts' statements are still needed,
and the history of its versions with the reason for every send-back. Every value is computed by
code from the item's evidence, the year-end trial balance and the firm's review decisions
(ADR-050); every word shown is the firm's or a fixed label (ADR-111).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.api import check_facts, get_ref
from abacus.modules.evidence.cross_checks import Account, cash_accounts
from abacus.modules.evidence.extraction import EXTRACTOR_VERSION
from abacus.modules.evidence.processing import year_end_accounts
from abacus.modules.evidence.repository import (
    extraction_for,
    item_versions_with_decisions,
    reason_codes,
)
from abacus.modules.evidence.uploads import ON_BEHALF_SOURCE, item_resource
from abacus.modules.identity.api import AuthContext, authorise, engagement_role_of, names_of
from abacus.modules.requests.api import read_item, read_item_versions

_CLIENT_ROLES = frozenset({"client_admin", "client_contributor"})
_PROVIDED = {"retrieved": "connection", "imported": "export"}
_OUTCOMES = {"accept": "accepted", "send_back": "sent_back", "reject": "not_accepted"}
_NOT_COVERING = frozenset({"send_back", "reject"})


@dataclass(frozen=True)
class Provided:
    source: str  # connection or export
    on: datetime


@dataclass(frozen=True)
class Gap:
    covered: list[str]  # last four digits, or the account's name when it has none (D2)
    needed: list[str]


@dataclass(frozen=True)
class HistoryEntry:
    evidence_version_id: UUID
    added_by: str  # "firm", or "client" with a name
    added_by_name: str
    added_at: datetime
    outcome: str  # in_review, replaced, accepted, sent_back, not_accepted
    reason_label: str | None = None  # send-backs only (SPEC-031 Q4)
    note: str | None = None


@dataclass(frozen=True)
class ClientView:
    provided: Provided | None
    gap: Gap | None
    history: list[HistoryEntry]


def _label(account: Account) -> tuple[str | None, str]:
    digits = re.sub(r"\D", "", account.name)
    return (digits[-4:], digits[-4:]) if len(digits) >= 4 else (None, account.name)


def statement_gap(cash: Sequence[Account], last4s: Sequence[str | None]) -> Gap | None:
    """AC-5: each cash account is covered by a statement with its last four digits. Accounts
    without digits take the statements that match no account, in trial balance order. None
    without cash accounts."""
    if not cash:
        return None
    labels = [_label(a) for a in cash]
    known = {digits for digits, _ in labels if digits is not None}
    spare = sum(1 for d in last4s if d is None or d not in known)
    covered: list[str] = []
    needed: list[str] = []
    for digits, label in labels:
        if digits is not None:
            (covered if digits in last4s else needed).append(label)
        elif spare > 0:
            spare -= 1
            covered.append(label)
        else:
            needed.append(label)
    return Gap(covered, needed)


def _user(actor_id: str) -> UUID | None:
    try:
        return UUID(actor_id)
    except ValueError:
        return None


async def client_view(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> ClientView:
    """For anyone allowed `evidence.read` on the item with its client facts (as its uploads)."""
    engagement = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, item_id)
    await authorise(ctx, "evidence.read", item_resource(item, engagement.resource()))
    async with tenant_session(ctx.tenant) as session:
        rows = await item_versions_with_decisions(
            session, item_id, await read_item_versions(ctx.tenant, item_id)
        )
        labels = dict(
            (code, label) for code, label, _, _ in await reason_codes(session, "send_back")
        )
        last4s: list[str | None] = []
        if item.document_kind == "bank_statement":
            for version, _, decision in rows:
                if version.method != "uploaded":
                    continue
                if decision is not None and decision.decision in _NOT_COVERING:
                    continue
                found = await extraction_for(
                    session, evidence_version_id=version.id, extractor_version=EXTRACTOR_VERSION
                )
                last4s.append(found.account_last4 if found is not None else None)

    provided = None
    if rows and rows[0][0].method in _PROVIDED:
        newest = rows[0][0]
        provided = Provided(_PROVIDED[newest.method], newest.pulled_at or newest.created_at)

    gap = None
    if item.document_kind == "bank_statement":
        facts = await check_facts(ctx.tenant, engagement_id)
        accounts = (
            None
            if facts is None
            else await year_end_accounts(
                ctx.tenant, engagement_id, facts.fiscal_period_end, facts.methodology_version_id
            )
        )
        if facts is not None and accounts is not None:
            cash = cash_accounts(accounts, facts.methodology_version_id is not None)
            gap = statement_gap(cash, last4s)

    uploaders = {
        u
        for version, evidence_item, _ in rows
        if version.method == "uploaded" and (u := _user(evidence_item.created_by_id)) is not None
    }
    roles = {u: await engagement_role_of(ctx.tenant, engagement_id, u) for u in uploaders}
    clients = {u for u, role in roles.items() if role in _CLIENT_ROLES}
    names = await names_of(sorted(clients, key=str))
    history: list[HistoryEntry] = []
    for n, (version, evidence_item, decision) in enumerate(rows):
        uploader = _user(evidence_item.created_by_id) if version.method == "uploaded" else None
        by_client = uploader in clients and version.source != ON_BEHALF_SOURCE
        if decision is None:
            outcome, reason, note = ("in_review" if n == 0 else "replaced"), None, None
        elif decision.decision == "send_back":
            outcome = "sent_back"
            reason = labels.get(decision.reason_code or "")
            note = decision.note
        else:
            outcome, reason, note = _OUTCOMES.get(decision.decision, "in_review"), None, None
        history.append(
            HistoryEntry(
                version.id,
                "client" if by_client else "firm",
                names.get(uploader, "") if by_client and uploader is not None else "",
                version.created_at,
                outcome,
                reason,
                note,
            )
        )
    return ClientView(provided, gap, history)
