"""Which audit events a reader may see: walls and roles apply to the trail (SPEC-002 AC-5,
ADR-026; DEC-121).

An event's target is a type and an id. A target that belongs to an engagement (the engagement
itself, its request items, evidence, procedures, findings, comments and so on) is shown only to
someone who may see that engagement; a target of a client or client entity, or a connection or
ledger snapshot, or a row a module places on a client (firm intake, an envelope), only to someone
who may see one of the client's engagements. Each module says which engagement owns the kinds of
target it owns, through its `api.py`. Firm-level events (the
firm, staff, knowledge, methodology, support sessions, walls and the like) stay visible.

Fails closed: a target type nobody here knows, an id that is not a UUID, or an id whose owner
cannot be found is hidden. Follow-up (DEC-121): an `engagement_id` on audit events makes this
exact and cheap, and this module goes away.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from typing import Final
from uuid import UUID

from abacus.kernel import audit_owners
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import AuditRow
from abacus.modules.engagements import api as engagements
from abacus.modules.identity import api as identity
from abacus.modules.identity.api import AuthContext

Owners = Callable[[TenantContext, str, Sequence[UUID]], Awaitable[dict[UUID, UUID]]]
Engagements = Callable[
    [TenantContext, str, Sequence[UUID]], Awaitable[dict[UUID, frozenset[UUID]]]
]
VisibleAmong = Callable[[AuthContext, Sequence[UUID]], Awaitable[set[UUID]]]

# About the firm, not a client: visible to everyone who may read the trail.
FIRM_LEVEL: Final = frozenset(
    {
        "firm",
        "user",
        "staff_invitation",
        "support_session",
        "methodology_version",
        "methodology_import",  # K-01-T18: a firm's methodology upload
        "methodology_source_file",  # K-01-T18: its stored files
        "grouping_set_version",  # the firm's chart groupings (SPEC-316), shared by engagements
        "knowledge_document",
        "feature_flag",
        "retention",
        "event",
        "usage_record",  # an id with no engagement on it; the follow-up makes it exact
        "auth_session",  # P-01-T09: a person's sign-in session spans the firm's engagements
        "legal_hold",  # Q-02-T29: a hold may cover a client or a tax year, not one engagement
        "engagement_draft",  # P-07-T16: a person's draft, before any engagement exists
        "security_incident",  # Q-02-T33: the firm's incident register (no client or engagement)
        "office",  # G-01-T08: firm structure, a filter only (DEC-30)
        "team",  # G-01-T08: teams and groups, and their rosters
        "secure_link",  # P-08-T21: a portal email's link, for one contact (no engagement)
        "firm_integration",  # A-02-T12: a firm's install of a catalogue app and its secret
        "email_template",  # R-01-T19: a firm's template key, its drafts and versions
        "follow_up_policy",  # R-01-T24: the firm's follow-up policy (one per firm)
        "sending_domain",  # R-01-T27: the firm's sender domain (no client or engagement)
        "agent_stage",  # Q-02-T06 (ED-120): a firm's agent stage row, set by platform staff
        "security_policy",  # G-02-T14: the firm's sign-in policy, exempt account, support switch
        "portal_security_policy",  # G-02-T14: the firm's portal session length
        "audit_export",  # G-02-T17: a person's export of the firm's log (a filter, no client)
        "firm_export_schedule",  # G-02-T19: the firm's monthly export schedule
        "safeguards_program",  # G-02-T20: the firm's safeguards record
        "safeguards_control",  # G-02-T20: one Pub 4557 control's status
        "wisp_pack",  # G-02-T20: an Export WISP pack job
        "ai_policy",  # G-02-T24: the firm's AI policy, its drafts and versions (one per firm)
        # Q-04-T007: an operator's pilot enrolment; its work item ref keeps it from walled readers
        "pilot_enrolment",
        "reference_set_version",  # K-02-T12: a platform rules table took effect (no client)
        "questionnaire_template",  # T-02-T16: the firm's organizer template and its versions
        "consent_export",  # T-01-T16: a person's export of the consent registry (a filter)
        "envelope_policy",  # N-02: the firm's envelope fallback policy (the firm is its id)
        "methodology_step",  # K-01-T18: a step of a firm methodology version (no engagement)
    }
)
# Kinds whose rows may belong to no engagement (a notification about the firm): then firm-level.
# P-04-T10: an approval grant belongs to its decision's engagement, or to the firm.
OPTIONAL_OWNER: Final = frozenset({"notification", "approval_grant"})

# The modules register what they own (`kernel.audit_owners`), read when asked so that a module
# loaded later is still seen; a kind nobody registered is unknown and hidden.
WALLS: Final = "ethical_wall"  # firm-level, but its refs name a client and a person
HiddenWalls = Callable[[AuthContext, Sequence[UUID]], Awaitable[set[UUID]]]
_hidden_walls: HiddenWalls = identity.audit_hidden_walls
_engagements_of: Engagements = engagements.audit_engagements
_visible_among: VisibleAmong = engagements.visible_among


def _engagement_owners() -> dict[str, Owners]:
    return audit_owners.engagement_owners()


def _entity_owners() -> dict[str, Owners]:
    return audit_owners.entity_owners()


def _client_owners() -> dict[str, Owners]:
    return audit_owners.client_owners()


def known_kinds() -> frozenset[str]:
    """Every target type the explorer can place, firm-level or engagement-owned."""
    return (
        FIRM_LEVEL
        | frozenset(_engagement_owners())
        | frozenset(_entity_owners())
        | frozenset(_client_owners())
        | engagements.AUDIT_KINDS
        | {WALLS}
    )


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


async def _owning_engagements(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, frozenset[UUID]] | None:
    """The engagements each id belongs to, or None for a kind nobody here knows."""
    if kind in engagements.AUDIT_KINDS:
        return await _engagements_of(tenant, kind, ids)
    if kind in (by_engagement := _engagement_owners()):
        owned = await by_engagement[kind](tenant, kind, ids)
        return {target: frozenset({engagement}) for target, engagement in owned.items()}
    if kind in (by_entity := _entity_owners()):
        entities = await by_entity[kind](tenant, kind, ids)
        of_entity = await _engagements_of(tenant, "client_entity", sorted(set(entities.values())))
        return {target: of_entity.get(entity, frozenset()) for target, entity in entities.items()}
    if kind in (by_client := _client_owners()):
        clients = await by_client[kind](tenant, kind, ids)
        of_client = await _engagements_of(tenant, "client", sorted(set(clients.values())))
        return {target: of_client.get(client, frozenset()) for target, client in clients.items()}
    return None


async def readable(ctx: AuthContext, rows: Sequence[AuditRow]) -> list[AuditRow]:
    """The rows the reader may see, in order."""
    wanted: dict[str, set[UUID]] = defaultdict(set)
    for row in rows:
        target = _uuid(row.target_id)
        if row.target_type not in FIRM_LEVEL and row.target_type != WALLS and target is not None:
            wanted[row.target_type].add(target)
    walls = {t for row in rows if row.target_type == WALLS and (t := _uuid(row.target_id))}
    hidden = await _hidden_walls(ctx, sorted(walls, key=str)) if walls else set[UUID]()
    placed: dict[tuple[str, UUID], frozenset[UUID]] = {}
    for kind, ids in wanted.items():
        found = await _owning_engagements(ctx.tenant, kind, sorted(ids, key=str))
        if found is not None:
            placed |= {(kind, target): owned for target, owned in found.items()}
    seen = await _visible_among(
        ctx, sorted({e for owned in placed.values() for e in owned}, key=str)
    )
    shown: list[AuditRow] = []
    for row in rows:
        if row.target_type in FIRM_LEVEL:
            shown.append(row)
            continue
        target = _uuid(row.target_id)
        if row.target_type == WALLS:
            if target is not None and target not in hidden:
                shown.append(row)
            continue
        owned = placed.get((row.target_type, target)) if target is not None else None
        if owned is None:  # unplaced: only a kind that may have no engagement stays visible
            if row.target_type in OPTIONAL_OWNER and target is not None:
                shown.append(row)
        elif owned & seen:
            shown.append(row)
    return shown
