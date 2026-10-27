"""The notification catalogue (SPEC-013 Q1): which events notify whom, about what.

Each kind maps one domain event to its recipients, the engagement it concerns (for walls at read
time) and its subject. Text comes from `TEMPLATES` (identifiers filled in by the SPA, AC-7);
notifications never store text. Recipients are resolved from current memberships and engagement
roles; never an agent or the platform, and a client user only when mentioned in a comment they
may read (SPEC-032; TASK-062 D2: checked by requests when the comment was posted).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, cast
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import (
    engagement_leads,
    engagement_partners,
    firm_admins,
    hidden_clients,
    member_facts,
    partner_members,
    security_admins,
    team_of,
)
from abacus.modules.notifications.kinds import NotificationKind, register_kind

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


async def _added_member(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    added = _uuid(payload, "user_id")
    return [added] if added is not None else []


async def _assignee(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    assignee = _uuid(payload, "assignee_user_id")
    return [assignee] if assignee is not None else []


_STAFF_ROLES = frozenset({"engagement_partner", "manager", "senior", "staff", "reviewer"})


async def _staff_team(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """The engagement's firm team, never its client users (SPEC-020: a client uploaded)."""
    engagement_id = _uuid(payload, "engagement_id")
    if engagement_id is None:
        return []
    team = await team_of(tenant_id, engagement_id)
    return sorted({user for user, role in team if role in _STAFF_ROLES})


async def _leads(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """The engagement's partner and managers (SPEC-020: a client connected or disconnected)."""
    engagement_id = _uuid(payload, "engagement_id")
    return [] if engagement_id is None else await engagement_leads(tenant_id, engagement_id)


async def _mentioned(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """SPEC-032 AC-5: the people mentioned in a comment, firm or client."""
    raw = payload.get("mentioned_user_ids")
    if not isinstance(raw, list):
        return []
    return sorted({UUID(str(u)) for u in cast(list[object], raw)})


async def _partners(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """SPEC-305 (TASK-306): the engagement partner, who alone decides; never about their own
    proposal (TASK-307)."""
    engagement_id, by = _uuid(payload, "engagement_id"), _uuid(payload, "by_user")
    if engagement_id is None:
        return []
    return [u for u in await engagement_partners(tenant_id, engagement_id) if u != by]


def _uuids(payload: dict[str, object], key: str) -> list[UUID]:
    raw = payload.get(key)
    return [UUID(str(u)) for u in cast(list[object], raw)] if isinstance(raw, list) else []


async def _hold_notify(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """Q-02-T29 (Q-02 §4.8): the hold's notify list and the partners of the engagements in scope;
    firm staff only, and nobody walled from the held client. Never the person who placed it."""
    people = set(_uuids(payload, "notify_user_ids"))
    for engagement_id in _uuids(payload, "engagement_ids"):
        people |= set(await engagement_partners(tenant_id, engagement_id))
    by = _uuid(payload, "by_user")
    if by is not None:
        people.discard(by)
    tenant = TenantContext(tenant_id, "system", "notifications")
    client = _uuid(payload, "client_id")
    out: list[UUID] = []
    for user in sorted(people):
        member = await member_facts(tenant, user)
        if member is None or member.client:
            continue
        if client is not None and await hidden_clients(tenant, user, [client]):
            continue
        out.append(user)
    return out


async def _request_owner(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """R-01-T13 (INV-5): the request's firm owner, else the engagement's partner and managers;
    never a client or the third party."""
    owner = _uuid(payload, "owner_user_id")
    if owner is not None:
        member = await member_facts(TenantContext(tenant_id, "system", "notifications"), owner)
        if member is not None and not member.client:
            return [owner]
    return await _leads(tenant_id, payload)


async def _incident_recorded(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """Q-02-T33 (Q-02 §4.8): the firm's QI and partner-level members; never the recorder."""
    people = set(await security_admins(tenant_id)) | set(await partner_members(tenant_id))
    by = _uuid(payload, "by_user")
    if by is not None:
        people.discard(by)
    return sorted(people)


async def _incident_from_accrued(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """Q-02-T33 (RB-27): the firm's QI and firm admins, about an Accrued incident."""
    return sorted(set(await security_admins(tenant_id)) | set(await firm_admins(tenant_id)))


async def _wall_approver(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """G-01-T09 (AC8.2): the partner a new wall names to approve it (none named: nobody)."""
    approver = _uuid(payload, "approver_user_id")
    return [approver] if approver is not None else []


async def _wall_creator(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    creator = _uuid(payload, "created_by")
    return [creator] if creator is not None else []


async def _signer(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """P-04-T19: the person whose sign-off went stale."""
    signer = _uuid(payload, "signed_by")
    return [signer] if signer is not None else []


async def _export_requester(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """A-01-T22: the person who asked for the export, and only them (walls applied at fan-out
    and again at read time)."""
    requester = _uuid(payload, "requested_by")
    return [requester] if requester is not None else []


@dataclass(frozen=True)
class Kind:
    kind: str  # the stored code; new codes are undotted (C16); the key is the event type
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
    "engagement_member.added": Kind(
        "engagement_member.added", _added_member, "engagement", "engagement_id"
    ),
    "review.assigned": Kind(
        "review_assigned", _assignee, "evidence_version", "evidence_version_id"
    ),
    "evidence.uploaded": Kind(
        "client_uploaded", _staff_team, "evidence_version", "evidence_version_id"
    ),
    "connection.created": Kind("connection.created", _leads, "connection", "connection_id"),
    "connection.revoked": Kind("connection.revoked", _leads, "connection", "connection_id"),
    # SPEC-025 (TASK-044): the person who joined is asked to confirm their independence.
    "independence.requested": Kind(
        "independence.requested", _added_member, "engagement", "engagement_id"
    ),
    # SPEC-027 (TASK-051): the engagement agent's drafted reminders (Advise) and daily digest.
    "reminders.drafted": Kind("reminders.drafted", _leads, "engagement", "engagement_id"),
    # P-06-T14: the same, under its C16 code (events from before the rename keep the legacy one).
    "follow_up.drafted": Kind("follow_up_drafted", _leads, "engagement", "engagement_id"),
    "agent.digest": Kind("agent.digest", _leads, "engagement", "engagement_id"),
    # SPEC-032 (TASK-062): a person mentioned in a comment, on the request it's about.
    "comment.mentioned": Kind("mention", _mentioned, "request_item", "request_item_id"),
    # SPEC-305 (TASK-306): decisions reserved to the engagement partner.
    "materiality.proposed": Kind("materiality.proposed", _partners, "engagement", "engagement_id"),
    "risk.approval_requested": Kind("risk.approval_requested", _partners, "risk", "risk_id"),
    "finding.severity_proposed": Kind(
        "finding.severity_proposed", _partners, "finding", "finding_id"
    ),
    # Q-02-T29: a legal hold was placed (the evidence module's `legal_hold.placed`).
    "legal_hold.placed": Kind("legal_hold_placed", _hold_notify, "legal_hold", "hold_id"),
    # Q-02-T33: the incident register (the platform module's events; firm-level).
    "incident.recorded": Kind(
        "incident_recorded", _incident_recorded, "security_incident", "incident_id", None
    ),
    "incident.propagated": Kind(
        "incident_from_accrued", _incident_from_accrued, "security_incident", "incident_id", None
    ),
    # G-01-T09 (DEC-73): a wall's named partner is asked to approve it; its creator is told.
    "wall.created": Kind(
        "wall_approval_requested", _wall_approver, "ethical_wall", "wall_id", None
    ),
    "wall.approved": Kind("wall_approved", _wall_creator, "ethical_wall", "wall_id", None),
    # G-01-T13 (AC4.5): firm admins, seven days or fewer before seasonal access ends.
    "membership.access_ending": Kind("seasonal_access_ending", _admins, "firm", None, None),
    # R-01-T09: a client's portal drop the code rule could not sort waits for a person.
    "portal.drop_unsorted": Kind("portal_drop_unsorted", _leads, "inbox_file", "inbox_file_id"),
    # R-01-T13: a third party uploaded to a request delegated to them (POR-14).
    "third_party.uploaded": Kind(
        "third_party_uploaded", _request_owner, "request_item", "request_item_id"
    ),
    # P-04-T19 (SHL-12 e): the work a person signed changed after their sign-off.
    "sign_off.went_stale": Kind("sign_off_stale", _signer, "sign_off", "sign_off_id"),
    # A-01-T22 (A-01 §4.7): the requester's binder export is ready, or its build failed.
    "engagement_export.ready": Kind(
        "export_ready", _export_requester, "engagement_export", "export_id"
    ),
    "engagement_export.failed": Kind(
        "export_failed", _export_requester, "engagement_export", "export_id"
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
    "engagement_member.added": "You were added to {engagement}.",
    "review.assigned": "Evidence on {engagement} was assigned to you for review.",
    "evidence.uploaded": "The client uploaded a file on {engagement}.",
    "connection.created": "The client connected their accounting system on {engagement}.",
    "connection.revoked": "The accounting system connection on {engagement} was ended.",
    "independence.requested": "Confirm your independence for {engagement}.",
    "reminders.drafted": "Overdue reminders on {engagement} are waiting for you to send.",
    "follow_up.drafted": "Follow-ups on {engagement} are waiting for you to send.",
    "agent.digest": "Items are overdue on {engagement}: see its activity for today's reminders.",
    "comment.mentioned": "You were mentioned in a comment on {engagement}.",
    "materiality.proposed": "Materiality on {engagement} is waiting for your decision.",
    "risk.approval_requested": "A risk on {engagement} is waiting for your approval.",
    "finding.severity_proposed": "A deficiency on {engagement} is waiting for you to conclude.",
    "legal_hold.placed": "A legal hold was placed on {subject}.",
    "incident.recorded": "A security incident was recorded: {subject}.",
    "incident.propagated": "Accrued reported a security incident affecting your firm: {subject}.",
    "wall.created": "An ethical wall is waiting for your approval.",
    "wall.approved": "The ethical wall you added was approved.",
    "membership.access_ending": "Seasonal access ends within seven days for some of your people.",
    "portal.drop_unsorted": "A client sent a file for your team to sort on {engagement}.",
    "third_party.uploaded": "A third party uploaded a file to a request on {engagement}.",
    "sign_off.went_stale": "Work you signed off on {engagement} changed after sign-off.",
    "engagement_export.ready": "Your binder export for {engagement} is ready to download.",
    "engagement_export.failed": "Your binder export for {engagement} could not be built.",
}


# P-01-T06 (C16): the SPEC-013 kinds in the kind registry, with their tabs and glyphs. Their
# owners add facts and pending resolvers through `notifications.api` as their screens need them.
_REGISTERED: Final[tuple[NotificationKind, ...]] = (
    NotificationKind("support_session.requested", "system", "LifeBuoy"),
    NotificationKind("support_session.emergency_approved", "system", "LifeBuoy"),
    NotificationKind("budget.soft_crossed", "system", "Gauge"),
    NotificationKind("budget.anomaly", "system", "Gauge"),
    NotificationKind("engagement.member_self_joined", "other", "UserPlus"),
    NotificationKind("engagement_member.added", "other", "UserPlus"),
    NotificationKind("review_assigned", "approval", "ClipboardCheck"),
    NotificationKind(
        "client_uploaded",
        "client_activity",
        "Upload",
        inline_actions=("accept_document", "return_document"),
    ),
    NotificationKind("connection.created", "client_activity", "Plug"),
    NotificationKind("connection.revoked", "client_activity", "Plug"),
    NotificationKind("independence.requested", "approval", "ShieldCheck"),
    NotificationKind("reminders.drafted", "approval", "Send"),
    NotificationKind("follow_up_drafted", "approval", "Send"),  # P-06-T14 (C16)
    # P-06-T14: a follow-up a person sent; its email is the follow-up itself (communications
    # sends it from the Reminder or Return template), so no catalogue event fans it out.
    NotificationKind("follow_up_sent", "client_activity", "Send"),
    NotificationKind("agent.digest", "run", "Sparkles"),
    NotificationKind("mention", "mention", "AtSign", email_default=True),
    NotificationKind("materiality.proposed", "approval", "Scale"),
    NotificationKind("risk.approval_requested", "approval", "TriangleAlert"),
    NotificationKind("finding.severity_proposed", "approval", "Flag"),
    # Q-02-T30 (Q-02 §4.8): the compliance kernel's kinds. Email text is database rows, loaded
    # through the admin import; none is committed.
    NotificationKind("ai_client_data_changed", "system", "ShieldCheck"),
    NotificationKind("legal_hold_placed", "system", "Lock"),
    NotificationKind("incident_recorded", "system", "ShieldAlert"),
    NotificationKind("incident_from_accrued", "system", "ShieldAlert", email_default=True),
    NotificationKind("firm_export_approval_requested", "approval", "Download"),
    NotificationKind("firm_export_ready", "system", "Download"),
    # G-01-T09: the wall approval (actionable from ADM-03's drawer) and its outcome.
    NotificationKind("wall_approval_requested", "approval", "ShieldCheck", email_default=True),
    NotificationKind("wall_approved", "system", "ShieldCheck"),
    NotificationKind("seasonal_access_ending", "system", "UserMinus"),  # G-01-T13
    NotificationKind("portal_drop_unsorted", "client_activity", "Inbox"),  # R-01-T09
    NotificationKind("third_party_uploaded", "client_activity", "Upload"),  # R-01-T13
    NotificationKind("sign_off_stale", "approval", "ClipboardCheck"),  # P-04-T19
    # G-02-T02 (G-02 section 4.8): firm governance v1. Email text is database rows (C16), loaded
    # as content (G-02-T07); their owners add facts and pending resolvers with their tasks.
    NotificationKind(
        "ai_policy_approval_requested", "approval", "ShieldCheck", email_default=True
    ),
    NotificationKind("ai_policy_published", "system", "ShieldCheck"),
    NotificationKind("incident_decision_requested", "approval", "ShieldAlert", email_default=True),
    NotificationKind(
        "incident_deadline_approaching", "deadline", "ShieldAlert", email_default=True
    ),
    NotificationKind("audit_export_ready", "system", "Download"),
    NotificationKind("security_policy_changed", "system", "Lock"),
    # A-01-T22 (A-01 §4.7): in-app; an email, when a person turns it on, deep-links to the
    # export sheet (`notification.export_ready`, imported content), never to a download.
    NotificationKind("export_ready", "system", "Download"),
    NotificationKind("export_failed", "system", "Download"),
)
for _kind in _REGISTERED:
    register_kind(_kind)
