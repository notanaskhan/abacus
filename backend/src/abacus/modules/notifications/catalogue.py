"""The notification catalogue (SPEC-013 Q1): which events notify whom, about what.

Each kind maps one domain event to its recipients, the engagement it concerns (for walls at read
time) and its subject. Text comes from `TEMPLATES` (identifiers filled in by the SPA, AC-7);
notifications never store text. Recipients are resolved from current memberships and engagement
roles; never a client user, an agent or the platform.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.modules.identity.api import engagement_leads, firm_admins, team_of

Recipients = Callable[[UUID, dict[str, object]], Awaitable[list[UUID]]]


def _uuid(payload: dict[str, object], key: str) -> UUID | None:
    value = payload.get(key)
    return UUID(str(value)) if value is not None else None


async def _admins(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    return await firm_admins(tenant_id)


async def _admins_and_leads(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """Firm admins, plus the engagement's partner and managers when it names one."""
    recipients = set(await firm_admins(tenant_id))
    engagement_id = _uuid(payload, "engagement_id")
    if engagement_id is not None:
        recipients |= set(await engagement_leads(tenant_id, engagement_id))
    return sorted(recipients)


async def _team_but_joiner(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    engagement_id, joiner = _uuid(payload, "engagement_id"), _uuid(payload, "user_id")
    if engagement_id is None:
        return []
    return sorted({user for user, _ in await team_of(tenant_id, engagement_id) if user != joiner})


async def _assignee(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    assignee = _uuid(payload, "assignee_user_id")
    return [assignee] if assignee is not None else []


@dataclass(frozen=True)
class Kind:
    kind: str
    recipients: Recipients
    subject_type: str
    subject_key: str | None  # payload key of the subject; None: the firm itself
    engagement_key: str | None = "engagement_id"


CATALOGUE: Final[dict[str, Kind]] = {
    "support_session.requested": Kind(
        "support_session.requested", _admins, "support_session", "session_id", None
    ),
    "support_session.emergency_approved": Kind(
        "support_session.emergency_approved", _admins, "support_session", "session_id", None
    ),
    "budget.soft_crossed": Kind(
        "budget.soft_crossed", _admins_and_leads, "engagement", "engagement_id"
    ),
    "budget.anomaly": Kind("budget.anomaly", _admins_and_leads, "engagement", "engagement_id"),
    "engagement.member_self_joined": Kind(
        "engagement.member_self_joined", _team_but_joiner, "engagement", "engagement_id"
    ),
    "review.assigned": Kind(
        "review.assigned", _assignee, "evidence_version", "evidence_version_id"
    ),
}

# AC-7: fixed English text per kind; placeholders are names the reader can already see.
TEMPLATES: Final[dict[str, str]] = {
    "support_session.requested": "Platform support asked for access to your firm.",
    "support_session.emergency_approved": (
        "Platform support opened emergency access to your firm. Please review it."
    ),
    "budget.soft_crossed": "Model spend passed its soft limit for {subject}.",
    "budget.anomaly": "Unusual model spend on {engagement} in the last hour.",
    "engagement.member_self_joined": "A firm admin joined {engagement} to view its content.",
    "review.assigned": "Evidence on {engagement} was assigned to you for review.",
}
