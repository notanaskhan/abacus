"""The C16 kind registry (P-01-T06; `docs/contracts/notifications.md`).

Every notification kind registers once: its category (the drawer's tab), glyph, whether it
emails by default, the inline actions its row may offer, and the read-time resolvers for its
facts and its pending state. Owners register their kinds through `notifications.api`; the
catalogue registers the SPEC-013 ones. Fail closed: fan-out drops an unregistered kind (with a
metric), and a row of an unregistered kind resolves no facts and is never pending.

Rules (C16): new codes are snake_case with no dot; the dotted SPEC-013 codes are legacy and
listed. Inline actions come from a closed set, and agent-originated kinds offer none (INV-1).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, get_args
from uuid import UUID

from abacus.kernel.db import TenantContext

Category = Literal["approval", "mention", "client_activity", "run", "deadline", "system", "other"]
InlineAction = Literal["accept_document", "return_document", "open_sign_off"]
Fact = str | int | bool | None
INLINE_ACTIONS: Final = frozenset(get_args(InlineAction))
UNDOTTED: Final = re.compile(r"[a-z][a-z_]*")
LEGACY_DOTTED: Final = frozenset(
    {
        "support_session.requested",
        "support_session.emergency_approved",
        "budget.soft_crossed",
        "budget.anomaly",
        "engagement.member_self_joined",
        "engagement_member.added",
        "connection.created",
        "connection.revoked",
        "independence.requested",
        "reminders.drafted",
        "agent.digest",
        # SPEC-305 (TASK-306): dotted when they landed; legacy under C16.
        "materiality.proposed",
        "risk.approval_requested",
        "finding.severity_proposed",
    }
)
AGENT_KINDS: Final = frozenset(
    {
        "run_finished",
        "run_needs_input",
        "proposal_routed",
        "trigger_run_finished",
        "template_update_available",
        "reminders.drafted",
        "agent.digest",
    }
)


@dataclass(frozen=True)
class Row:
    """What a resolver may read: identifiers and codes only (rows never store text)."""

    id: UUID
    kind: str
    engagement_id: UUID | None
    subject_type: str
    subject_id: UUID
    created_at: datetime


FactsResolver = Callable[[TenantContext, Row], Awaitable[dict[str, Fact]]]
PendingResolver = Callable[[TenantContext, UUID, Row], Awaitable[bool]]


@dataclass(frozen=True)
class NotificationKind:
    code: str
    category: Category
    glyph: str
    email_default: bool = False
    inline_actions: tuple[InlineAction, ...] = ()
    facts: FactsResolver | None = None
    pending: PendingResolver | None = None


_KINDS: dict[str, NotificationKind] = {}


def _same(a: NotificationKind, b: NotificationKind) -> bool:
    """The same registration, even from a module executed twice (a reloaded `api.py`)."""

    def name(f: object) -> object:
        return (
            None
            if f is None
            else (getattr(f, "__module__", None), getattr(f, "__qualname__", None))
        )

    return (a.code, a.category, a.glyph, a.email_default, a.inline_actions) == (
        b.code,
        b.category,
        b.glyph,
        b.email_default,
        b.inline_actions,
    ) and (name(a.facts), name(a.pending)) == (name(b.facts), name(b.pending))


def register_kind(kind: NotificationKind) -> None:
    """Register a kind once; anything breaking a C16 rule fails at startup."""
    if not UNDOTTED.fullmatch(kind.code) and kind.code not in LEGACY_DOTTED:
        raise ValueError(f"notification kind {kind.code!r}: new codes are undotted (C16)")
    if not set(kind.inline_actions) <= INLINE_ACTIONS:
        raise ValueError(f"notification kind {kind.code!r}: unknown inline action")
    if kind.inline_actions and kind.code in AGENT_KINDS:
        raise ValueError(f"notification kind {kind.code!r}: agent rows offer no inline action")
    known = _KINDS.get(kind.code)
    if known is not None and not _same(known, kind):
        raise ValueError(f"notification kind {kind.code!r} is already registered")
    _KINDS[kind.code] = kind


def kind_of(code: str) -> NotificationKind | None:
    return _KINDS.get(code)


def registered() -> tuple[str, ...]:
    return tuple(sorted(_KINDS))
