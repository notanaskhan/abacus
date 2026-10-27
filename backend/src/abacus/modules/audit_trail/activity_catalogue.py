"""The audit event catalogue v1 (G-02-T08; SPEC-349 §5; DEC-417): what kind of event each audited
is, its marker, and the facts its detail line names.

- `category`: `decision`, `change`, `access`, `run`, `sign_in`, `communication` or `export`.
- `mark`: `ok` a named person's (or, dormant, a named policy's) approval or sign-off, never agent
  output; `no` a reversal or removal; `pl` a neutral event. The projection downgrades `ok` to `pl`
  for any other actor, so no listed approval can name the agent (AC-3, INV-1).
- `facts`: the reference keys the detail line may show (codes, counts and ids, never a value;
  security review M4). Empty means every identifier reference the event carries.

Three sources, in order: the entries below, entries modules register through
`register_activity_kinds` (their `ACTIVITY_KINDS`), and a generic fallback read from the action's
verb. The static check (`tests/unit/audit_trail/test_activity_catalogue.py`) holds every audited
action literal in the codebase to an entry or the reviewed fallback list
(`activity_reviewed.py`), so a new action is a reviewed decision, not an accident.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

Category = Literal["decision", "change", "access", "run", "sign_in", "communication", "export"]
Mark = Literal["ok", "no", "pl"]


@dataclass(frozen=True)
class CatalogueEntry:
    category: Category
    mark: Mark = "pl"
    facts: tuple[str, ...] = ()


def _a(category: Category, mark: Mark = "pl", *facts: str) -> CatalogueEntry:
    return CatalogueEntry(category, mark, facts)


# G-02 §4.7 and the governance events ADM-07 renders first; the rest arrive through the fallback.
CATALOGUE: Final[Mapping[str, CatalogueEntry]] = {
    # Security center (G-02-T14, T18 to T20)
    "security_policy.sign_in_updated": _a("change"),
    "security_policy.sso_enforced": _a("change"),
    "security_policy.idp_mfa_attested": _a("decision", "ok"),
    "security_policy.portal_updated": _a("change"),
    "security_policy.sso_exempt_designated": _a("change"),
    "security_policy.sso_exempt_tested": _a("sign_in"),
    "auth_session.signed_out_by_admin": _a("sign_in", "no"),
    "staff.unlocked": _a("change"),
    "support_access.requests_allowed": _a("change"),
    "support_access.requests_disallowed": _a("change", "no"),
    # G-02-T14 writes the security-center contract's names (security-center.md §5; DEC-529).
    "security_policy.updated": _a("change"),
    "portal_security_policy.updated": _a("change"),
    "sso_exempt_account.designated": _a("change"),
    "sso_exempt_account.cleared": _a("change", "no"),
    "sso_exempt_account.tested": _a("sign_in"),
    "session.signed_out": _a("sign_in", "no"),
    "support_access.updated": _a("change"),
    "incident.timeline_added": _a("change"),
    "incident.decision_recorded": _a("decision"),
    "incident.decided": _a("decision", "ok"),
    "firm_export.schedule_requested": _a("export"),
    "firm_export.schedule_approved": _a("export", "ok"),
    # Q-02-T43 (compliance-kernel §7): the firm export's dual approval, build and links.
    "firm_export.requested": _a("export"),
    "firm_export.approved": _a("export", "ok"),
    "firm_export.declined": _a("export", "no"),
    "firm_export.ready": _a("export"),
    "firm_export.failed": _a("export", "no"),
    "firm_export.expired": _a("export"),
    "firm_export.downloaded": _a("export"),
    "firm_export.streamed": _a("export"),
    "safeguards.updated": _a("change"),
    "safeguards.control_status_changed": _a("change"),
    "safeguards.wisp_pack_prepared": _a("export"),
    # The audit log's own export (G-02-T17)
    "audit_export.requested": _a("export"),
    "audit_export.ready": _a("export"),
    "audit_export.downloaded": _a("export"),
    "audit_export.failed": _a("export", "no"),
    # The security-center contract's names (security-center.md §5) for T18 to T20 (DEC-624)
    "incident.timeline_appended": _a("change"),
    "incident.notification_started": _a("decision", "ok"),
    "incident.reminder_sent": _a("communication", "pl", "day"),
    "firm_export_schedule.updated": _a("change"),
    "firm_export_schedule.approved": _a("decision", "ok"),
    "firm_export_schedule.run_started": _a("export"),
    "firm_export_schedule.run_skipped": _a("export", "no"),
    "firm_export_schedule.approval_lapsed": _a("change", "no"),
    "safeguards_control.updated": _a("change"),
    "wisp_pack.prepared": _a("export"),
    "wisp_pack.ready": _a("export"),
    "wisp_pack.downloaded": _a("export"),
    "wisp_pack.failed": _a("export", "no"),
    "safeguards_controls.imported": _a("change"),
    "safeguards_controls.published": _a("change", "ok"),
    # AI policy (G-02-T23, T24)
    "ai_policy.draft_saved": _a("change"),
    "ai_policy.draft_discarded": _a("change", "no"),
    "ai_policy.publish_requested": _a("decision", "pl", "version_no"),
    "ai_policy.approved": _a("decision", "ok", "version_no"),
    "ai_policy.declined": _a("decision", "no", "version_no"),
    "ai_policy.withdrawn": _a("decision", "no", "version_no"),
    "ai_policy.carried_over": _a("change", "pl", "version_no"),
    "firm_agents.paused": _a("change", "no"),
    "firm_agents.resumed": _a("change"),
    # Walls (G-01) and people
    "wall.created": _a("change", "pl", "user_id", "client_id", "reason", "approver_user_id"),
    "wall.ended": _a("change", "no"),
    # Connections and integrations (A-02-T15, T16): codes and ids only; `client_actor` marks a
    # client person's act, rendered "(client)" (INV-5)
    "write_capability.refused": _a("change", "no", "reason", "shape"),
    "connection.consent_recorded": _a("decision", "ok", "consent_version", "client_actor"),
    "connection.reauthorized": _a("change", "pl", "client_actor"),
    "connection.retry_requested": _a("run", "pl", "sync_run_id", "client_actor"),
    "connection.grant_revoked": _a("change", "no", "result"),  # review M1: the provider's revoke
    "connection.reconnect_requested": _a("change", "pl", "engagement_id"),  # A-02-T23
    # Tie-out checks (A-02-T17)
    "tie_out_check.issue_linked": _a("change", "pl", "issue_id", "version_no"),
    # Open in Excel (A-02-T22): the version, the layer and the file's fingerprint
    "trial_balance.exported": _a("export", "pl", "version_no", "layer_no", "file_sha256"),
    # Proposals and suggestions (P-04-T24, T25; ADR-161): a person's verdict on the agent's
    # change set ("Proposal approved by Samuel Ito"); the agent's proposal is a run's output.
    "proposal.created": _a("run", "pl", "version"),
    "proposal.approved": _a("decision", "ok", "decision", "version"),
    "proposal.approved_with_edits": _a("decision", "ok", "decision", "version", "edits"),
    "proposal.rejected": _a("decision", "no", "decision", "version"),
    "proposal.routed": _a("decision", "pl", "decision", "user_id"),
    "proposal.follow_up_recorded": _a("change", "pl", "decision"),
    "suggestion.created": _a("run", "pl"),
    "suggestion.adopted": _a("decision", "ok", "decision", "version"),
    "suggestion.edited": _a("decision", "ok", "decision", "version"),
    "suggestion.dismissed": _a("decision", "no", "decision", "version"),
    "field.value_recorded": _a("change", "pl", "seq", "citations"),
}

_REGISTERED: dict[str, CatalogueEntry] = {}


def register_activity_kinds(kinds: Mapping[str, CatalogueEntry]) -> None:
    """A module's own entries (`ACTIVITY_KINDS`); an action has one entry, ever."""
    for action, activity in kinds.items():
        known = CATALOGUE.get(action) or _REGISTERED.get(action)
        if known is not None and known != activity:
            raise ValueError(f"audit action {action!r} already has a catalogue entry")
        _REGISTERED[action] = activity


def registered_kinds() -> dict[str, CatalogueEntry]:
    return {**_REGISTERED, **CATALOGUE}


_OK_VERBS: Final = frozenset(
    {"approved", "signed_off", "accepted", "released", "signed", "published", "confirmed"}
)
_NO_VERBS: Final = frozenset(
    {
        "rejected",
        "declined",
        "revoked",
        "removed",
        "deleted",
        "withdrawn",
        "cancelled",
        "canceled",
        "ended",
        "voided",
        "reversed",
        "returned",
        "disabled",
        "discarded",
        "unlinked",
        "expired",
        "refused",
        "reopened",
        "sent_back",
        "suspended",
        "failed",
    }
)
_DECISION_VERBS: Final = _OK_VERBS | {
    "rejected",
    "declined",
    "decided",
    "waived",
    "concluded",
    "overridden",
}
_SIGN_IN_ENTITIES: Final = frozenset(
    {"auth_session", "staff_session", "portal_session", "sign_in", "mfa", "staff_sign_in"}
)
_COMMUNICATION_ENTITIES: Final = frozenset(
    {"follow_up", "email", "message", "notification", "invitation", "comment", "reminder"}
)
_ACCESS_ENTITIES: Final = frozenset({"pii_reveal", "support_session", "access", "secure_link"})
_RUN_ENTITIES: Final = frozenset({"agent_run", "run", "screening", "upload_review", "retrieval"})


def fallback(action: str) -> CatalogueEntry:
    """The generic entry read from the action's entity and verb."""
    entity, _, verb = action.partition(".")
    mark: Mark = "ok" if verb in _OK_VERBS else "no" if verb in _NO_VERBS else "pl"
    category: Category
    if "export" in entity or "export" in verb or verb == "downloaded":
        category = "export"
    elif entity in _SIGN_IN_ENTITIES or verb in {"signed_in", "signed_out"}:
        category = "sign_in"
    elif entity in _COMMUNICATION_ENTITIES or verb in {"sent", "delivered", "bounced"}:
        category = "communication"
    elif entity in _ACCESS_ENTITIES or verb in {"revealed", "viewed", "accessed", "granted"}:
        category = "access"
    elif entity in _RUN_ENTITIES or entity.endswith("_run"):
        category = "run"
    elif verb in _DECISION_VERBS:
        category = "decision"
    else:
        category = "change"
    return CatalogueEntry(category, mark)


def activity_of(action: str) -> CatalogueEntry:
    """The catalogue's entry, a module's, else the generic fallback."""
    return CATALOGUE.get(action) or _REGISTERED.get(action) or fallback(action)


__all__ = [
    "CATALOGUE",
    "CatalogueEntry",
    "Category",
    "Mark",
    "activity_of",
    "fallback",
    "register_activity_kinds",
    "registered_kinds",
]
