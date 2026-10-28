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
from abacus.kernel.subject_states import subject_state
from abacus.modules.identity.api import (
    engagement_leads,
    engagement_partners,
    firm_admins,
    hidden_clients,
    member_facts,
    partner_members,
    quality_partners,
    security_admins,
    team_of,
)
from abacus.modules.notifications.kinds import Fact, NotificationKind, Row, kind_of, register_kind

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


async def _listed(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """P-04-T21, T23: the people the owner named (a note's assignee or the target's preparers; a
    card's reserved person or role holders), never the person who acted."""
    by = _uuid(payload, "by_user")
    return sorted({u for u in _uuids(payload, "recipient_user_ids") if u != by})


async def _signer(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """P-04-T19: the person whose sign-off went stale."""
    signer = _uuid(payload, "signed_by")
    return [signer] if signer is not None else []


async def _named_partner(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """P-07-T47: the partner asked for the acceptance risk review, never the asker."""
    partner, by = _uuid(payload, "partner_id"), _uuid(payload, "by_user")
    return [partner] if partner is not None and partner != by else []


async def _reassigned_to(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """I-01-T07: the person a gate was moved to, never the mover."""
    to, by = _uuid(payload, "to_user_id"), _uuid(payload, "by_user")
    return [to] if to is not None and to != by else []


async def _quality_reviewers(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """K-01-T06: the firm's quality partners, who approve methodology, never the submitter."""
    by = _uuid(payload, "by_user")
    return [u for u in await quality_partners(tenant_id) if u != by]


async def _member(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """P-07-T47: the member a reminder is about."""
    member = _uuid(payload, "user_id")
    return [member] if member is not None else []


async def _export_requester(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """A-01-T22: the person who asked for the export, and only them (walls applied at fan-out
    and again at read time)."""
    requester = _uuid(payload, "requested_by")
    return [requester] if requester is not None else []


async def _second_decider(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """G-02-T18 (AC-22): the person the first decider named, and only them."""
    named = _uuid(payload, "waiting_for_user_id")
    return [named] if named is not None else []


async def _qi_and_partners(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """G-02-T18 (AC-23): the firm's QI and its partner-level members, on days 20, 25 and 29."""
    return sorted(set(await security_admins(tenant_id)) | set(await partner_members(tenant_id)))


async def _approver(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """P-04-T26 (SHL-10 d): the person a proposal was routed to, never the person who routed it."""
    approver, by = _uuid(payload, "approver_user_id"), _uuid(payload, "by_user")
    return [approver] if approver is not None and approver != by else []


async def _import_reviewers(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """P-04-T26 (SHL-16 import variant): an engine import's checkpoint waits on the return's
    reviewers the owner named; any other checkpoint notifies nobody."""
    if payload.get("author_kind") != "import":
        return []
    return await _listed(tenant_id, payload)


# P-04-T26 (C16): the review grammar's kinds read their facts and pending state from the
# subject's owner at read time (`kernel.subject_states`); facts never depend on the reader.
_NOBODY: Final = UUID(int=0)


async def _subject_facts(tenant: TenantContext, row: Row) -> dict[str, Fact]:
    return dict((await subject_state(tenant, _NOBODY, row.subject_type, row.subject_id)).facts)


async def _subject_pending(tenant: TenantContext, user_id: UUID, row: Row) -> bool:
    return (await subject_state(tenant, user_id, row.subject_type, row.subject_id)).pending


async def _firm_export_approver(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """Q-02-T43 (DEC-72): the person a firm export names to approve it, never its requester."""
    approver, requester = _uuid(payload, "approver_user_id"), _uuid(payload, "requested_by")
    return [approver] if approver is not None and approver != requester else []


async def _firm_export_parties(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    """Q-02-T43: the requester and the approver, the only two who may make a link."""
    people = {_uuid(payload, "requested_by"), _uuid(payload, "approver_user_id")}
    return sorted(p for p in people if p is not None)


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
    # A-02-T25: the daily health pass found a grant problem, or a grant ends within 7 days.
    "connection.needs_reauth": Kind(
        "connection_needs_reauth", _admins_and_leads, "connection", "connection_id"
    ),
    "connection.reauth_due": Kind(
        "connection_reauth_due", _admins_and_leads, "connection", "connection_id"
    ),
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
    # G-02-T24 (DEC-712): an AI policy version awaits the named partner (firm-level, not C13).
    "ai_policy.publish_requested": Kind(
        "ai_policy_approval_requested", _assignee, "ai_policy", None, None
    ),
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
    # R-01-T24 (DEC-564): the follow-up policy's maximum was reached for a binder's recipient.
    "follow_up.limit_reached": Kind("follow_up_limit_reached", _leads, "binder", "binder_id"),
    # R-01-T13: a third party uploaded to a request delegated to them (POR-14).
    "third_party.uploaded": Kind(
        "third_party_uploaded", _request_owner, "request_item", "request_item_id"
    ),
    # P-04-T19 (SHL-12 e): the work a person signed changed after their sign-off.
    "sign_off.went_stale": Kind("sign_off_stale", _signer, "sign_off", "sign_off_id"),
    # P-04-T21: a note was raised; its assignee (or the target's preparers) is told.
    "review_note.raised": Kind("review_note_raised", _listed, "reviewable_note", "note_id"),
    # P-04-T23: a card waits on its reserved person; "Notify" mentions them (SHL-11 b).
    "decision_card.raised": Kind("decision_assigned", _listed, "decision_card", "card_id"),
    "decision_card.notify_requested": Kind("mention", _assignee, "decision_card", "card_id"),
    # P-04-T26: a proposal routed to a named approver (SHL-10 d), by a person or by the firm's
    # threshold policy when the agent proposed; a person asked to sign off a target (SHL-12); an
    # issue assigned (SHL-15, its service P-04-T30); an engine import's checkpoint waiting on the
    # return's reviewers (SHL-16, P-04-T32). The last three fan out once their producers land.
    "proposal.routed": Kind("proposal_routed", _approver, "proposal", "proposal_id"),
    "sign_off.requested": Kind("sign_off_requested", _listed, "reviewable", "target_id"),
    "issue.assigned": Kind("issue_assigned", _assignee, "issue", "issue_id"),
    "checkpoint.created": Kind(
        "import_pending_approval", _import_reviewers, "checkpoint", "checkpoint_id"
    ),
    # P-07-T47 (P-07 §4.8): acceptance, risk review, independence and team approval.
    "acceptance.sent_to_partner": Kind(
        "acceptance_awaiting_partner", _partners, "acceptance_record", "record_id"
    ),
    "acceptance.review_requested": Kind(
        "risk_partner_review_requested", _named_partner, "acceptance_record", "record_id"
    ),
    "independence.reminded": Kind("independence_reminder", _member, "engagement", "engagement_id"),
    "human_gate.reassigned": Kind(
        "gate_reassigned", _reassigned_to, "engagement", "engagement_id"
    ),
    "methodology.review_requested": Kind(
        "methodology_review_requested",
        _quality_reviewers,
        "methodology_version",
        "version_id",
        None,
    ),
    "independence.conclusion_due": Kind(
        "independence_conclusion_due", _partners, "engagement", "engagement_id"
    ),
    "team.change_proposed": Kind(
        "team_change_awaiting_approval", _partners, "engagement", "engagement_id"
    ),
    # A-01-T22 (A-01 §4.7): the requester's binder export is ready, or its build failed.
    "engagement_export.ready": Kind(
        "export_ready", _export_requester, "engagement_export", "export_id"
    ),
    "engagement_export.failed": Kind(
        "export_failed", _export_requester, "engagement_export", "export_id"
    ),
    # G-02-T17: the requester's audit-log export is ready (firm-level).
    "audit_export.ready": Kind(
        "audit_export_ready", _export_requester, "audit_export", "export_id", None
    ),
    # G-02-T18: the incident register's two-person decision and its FTC clock (firm-level).
    "incident.decision_requested": Kind(
        "incident_decision_requested", _second_decider, "security_incident", "incident_id", None
    ),
    "incident.deadline_approaching": Kind(
        "incident_deadline_approaching",
        _qi_and_partners,
        "security_incident",
        "incident_id",
        None,
    ),
    # Q-02-T43 (compliance-kernel §7): the named approver is asked; both people are told when the
    # archive is ready. Firm-level.
    "firm_export.requested": Kind(
        "firm_export_approval_requested", _firm_export_approver, "firm_export", "export_id", None
    ),
    "firm_export.ready": Kind(
        "firm_export_ready", _firm_export_parties, "firm_export", "export_id", None
    ),
}


# AC-7: fixed English text per kind; placeholders are names the reader can already see.
def register_kind_source(
    code: str,
    event: str,
    recipients: Recipients,
    subject: tuple[str, str | None],
    *,
    engagement_key: str | None = "engagement_id",
) -> None:
    """C16 §3 (ED-015): a later epic adds a producing event to an existing kind, e.g. P-05's
    `mention.created` for `mention`. `subject` is the subject's type and its payload key (None:
    the firm itself). The kind must already exist and the event must produce nothing yet, so a
    source never re-routes another kind's event; both fail at startup."""
    known = kind_of(code) is not None or any(k.kind == code for k in CATALOGUE.values())
    if not known:
        raise ValueError(f"notification kind {code!r} is not registered")
    if event in CATALOGUE:
        raise ValueError(f"event {event!r} already produces {CATALOGUE[event].kind!r}")
    subject_type, subject_key = subject
    CATALOGUE[event] = Kind(code, recipients, subject_type, subject_key, engagement_key)


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
    "connection.needs_reauth": "The client needs to sign in to their accounting system again.",
    "connection.reauth_due": "The client's accounting system sign-in ends within 7 days.",
    "independence.requested": "Confirm your independence for {engagement}.",
    "reminders.drafted": "Overdue reminders on {engagement} are waiting for you to send.",
    "follow_up.drafted": "Follow-ups on {engagement} are waiting for you to send.",
    "agent.digest": "Items are overdue on {engagement}: see its activity for today's reminders.",
    "comment.mentioned": "You were mentioned in a comment on {engagement}.",
    "materiality.proposed": "Materiality on {engagement} is waiting for your decision.",
    "risk.approval_requested": "A risk on {engagement} is waiting for your approval.",
    "finding.severity_proposed": "A deficiency on {engagement} is waiting for you to conclude.",
    "legal_hold.placed": "A legal hold was placed on {subject}.",
    "ai_policy.publish_requested": "A new AI policy version is waiting for your approval.",
    "incident.recorded": "A security incident was recorded: {subject}.",
    "incident.propagated": "Accrued reported a security incident affecting your firm: {subject}.",
    "wall.created": "An ethical wall is waiting for your approval.",
    "wall.approved": "The ethical wall you added was approved.",
    "membership.access_ending": "Seasonal access ends within seven days for some of your people.",
    "portal.drop_unsorted": "A client sent a file for your team to sort on {engagement}.",
    "follow_up.limit_reached": (
        "The last reminder on {engagement} went out; nothing more will go automatically."
    ),
    "third_party.uploaded": "A third party uploaded a file to a request on {engagement}.",
    "sign_off.went_stale": "Work you signed off on {engagement} changed after sign-off.",
    "review_note.raised": "A review note on {engagement} is waiting for you.",
    "decision_card.raised": "A decision on {engagement} is waiting for you.",
    "decision_card.notify_requested": "A decision on {engagement} is waiting for you.",
    "proposal.routed": "A proposal on {engagement} was sent to you for approval.",
    "sign_off.requested": "Work on {engagement} is waiting for your sign-off.",
    "issue.assigned": "An issue on {engagement} was assigned to you.",
    "checkpoint.created": "An import on {engagement} is waiting for your approval.",
    "acceptance.sent_to_partner": "An acceptance on {engagement} is waiting for your decision.",
    "acceptance.review_requested": (
        "You were asked for a risk review of an acceptance on {engagement}."
    ),
    "independence.reminded": "Reminder: confirm your independence for {engagement}.",
    "human_gate.reassigned": "Something on {engagement} was reassigned to you.",
    "methodology.review_requested": "A methodology version is waiting for your review.",
    "independence.conclusion_due": (
        "Every member confirmed independence on {engagement}: it is ready for your conclusion."
    ),
    "team.change_proposed": "The team on {engagement} changed and is waiting for your approval.",
    "engagement_export.ready": "Your binder export for {engagement} is ready to download.",
    "engagement_export.failed": "Your binder export for {engagement} could not be built.",
    "audit_export.ready": "Your audit log export is ready to download.",
    "incident.decision_requested": "A security incident decision is waiting for you: {subject}.",
    "incident.deadline_approaching": (
        "A security incident's FTC notice date is approaching: {subject}."
    ),
    "firm_export.requested": "A firm data export is waiting for your approval.",
    "firm_export.ready": "The firm data export is ready to download for 7 days.",
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
    # A-02 §4.8 (A-02-T23): a connection that needs its client to sign in again (produced by the
    # daily health tick, A-02-T25), and the firm's reconnect request, whose client email is the
    # Reconnect request template itself (communications sends it; notification email is staff
    # only, INV-4), so no catalogue event fans it out, as `follow_up_sent`.
    NotificationKind("connection_needs_reauth", "client_activity", "Plug"),
    NotificationKind("connection_reauth_due", "client_activity", "Plug"),  # A-02-T25
    NotificationKind("connection_reconnect_requested", "client_activity", "Plug"),
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
    NotificationKind(
        "ai_policy_approval_requested", "approval", "ShieldCheck", email_default=True
    ),
    NotificationKind("incident_recorded", "system", "ShieldAlert"),
    NotificationKind("incident_from_accrued", "system", "ShieldAlert", email_default=True),
    NotificationKind("firm_export_approval_requested", "approval", "Download"),
    NotificationKind("firm_export_ready", "system", "Download"),
    # G-01-T09: the wall approval (actionable from ADM-03's drawer) and its outcome.
    NotificationKind("wall_approval_requested", "approval", "ShieldCheck", email_default=True),
    NotificationKind("wall_approved", "system", "ShieldCheck"),
    NotificationKind("seasonal_access_ending", "system", "UserMinus"),  # G-01-T13
    NotificationKind("portal_drop_unsorted", "client_activity", "Inbox"),  # R-01-T09
    NotificationKind("follow_up_limit_reached", "client_activity", "Send"),  # R-01-T24
    NotificationKind("third_party_uploaded", "client_activity", "Upload"),  # R-01-T13
    # P-04-T19, T21, T23, T26: the review grammar's seven kinds (C16 Approvals), their facts and
    # pending state read from the subject's owner at read time. Email text is database content
    # (`notification.<kind>`, imported), never committed.
    NotificationKind(
        "sign_off_stale",
        "approval",
        "ClipboardCheck",
        facts=_subject_facts,
        pending=_subject_pending,
    ),
    NotificationKind(
        "review_note_raised",
        "approval",
        "MessageSquare",
        facts=_subject_facts,
        pending=_subject_pending,
    ),
    NotificationKind(
        "decision_assigned", "approval", "Scale", facts=_subject_facts, pending=_subject_pending
    ),
    NotificationKind(
        "sign_off_requested",
        "approval",
        "ClipboardCheck",
        facts=_subject_facts,
        pending=_subject_pending,
    ),
    NotificationKind(
        "proposal_routed", "approval", "Sparkles", facts=_subject_facts, pending=_subject_pending
    ),
    NotificationKind(
        "issue_assigned", "approval", "Flag", facts=_subject_facts, pending=_subject_pending
    ),
    NotificationKind(
        "import_pending_approval",
        "approval",
        "Download",
        facts=_subject_facts,
        pending=_subject_pending,
    ),
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
    # P-07-T47 (P-07 §4.8): email text is `notification.<kind>` content (staff import). The
    # independence reminder emails by default: it is the staff reminder a person sends.
    NotificationKind("acceptance_awaiting_partner", "approval", "Scale"),
    NotificationKind("risk_partner_review_requested", "approval", "TriangleAlert"),
    NotificationKind("independence_reminder", "approval", "ShieldCheck", email_default=True),
    NotificationKind("independence_conclusion_due", "approval", "ShieldCheck"),
    NotificationKind("team_change_awaiting_approval", "approval", "UserPlus"),
    # I-01-T07: a gate moved to you; K-01-T06: a methodology version waits for your review.
    NotificationKind("gate_reassigned", "approval", "UserPlus"),
    NotificationKind("methodology_review_requested", "approval", "Scale"),
    # Day 12 of a 14-day client invitation, to the firm admins; registered for the drawer and
    # preferences now, produced once an expiry pass exists (P-07 §4.5 has no schedule; DEC-540).
    NotificationKind("invitation_expiring", "deadline", "Clock"),
    # A-01-T22 (A-01 §4.7): in-app; an email, when a person turns it on, deep-links to the
    # export sheet (`notification.export_ready`, imported content), never to a download.
    NotificationKind("export_ready", "system", "Download"),
    NotificationKind("export_failed", "system", "Download"),
)
for _kind in _REGISTERED:
    register_kind(_kind)
