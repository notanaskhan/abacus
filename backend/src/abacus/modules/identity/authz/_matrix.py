"""GENERATED from docs/architecture/permission-matrix.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.permission_matrix
"""

ROLES: tuple[str, ...] = (
    "firm_admin",
    "practice_leader",
    "quality_partner",
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
    "client_admin",
    "client_contributor",
    "agent",
    "system",
)

ACTIONS: dict[str, dict[str, str]] = {
    "firm.manage_users": {
        "firm_admin": "allow",
        "mfa_recent": "required",
    },
    "firm.manage_settings": {
        "firm_admin": "allow",
        "mfa_recent": "required",
    },
    "budget.read": {
        "firm_admin": "allow",
        "practice_leader": "allow",
    },
    "budget.manage": {
        "firm_admin": "allow",
        "mfa_recent": "required",
    },
    "methodology.manage": {
        "firm_admin": "allow",
        "practice_leader": "allow",
        "mfa_recent": "required",
    },
    "methodology.read": {
        "firm_admin": "allow",
        "practice_leader": "allow",
        "engagement_partner": "allow",
        "manager": "allow",
    },
    "knowledge.manage": {
        "firm_admin": "allow",
        "practice_leader": "allow",
        "mfa_recent": "required",
    },
    "knowledge.read": {
        "firm_admin": "allow",
        "practice_leader": "allow",
        "quality_partner": "allow",
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "staff": "allow",
        "reviewer": "allow",
    },
    "autonomy_policy.update": {
        "firm_admin": "allow",
        "mfa_recent": "required",
    },
    "wall.create": {
        "firm_admin": "allow",
        "mfa_recent": "required",
    },
    "wall.remove": {
        "firm_admin": "allow",
        "mfa_recent": "required",
    },
    "wall.list": {
        "firm_admin": "allow",
        "mfa_recent": "required",
    },
    "legal_hold.place": {
        "firm_admin": "allow",
        "mfa_recent": "required",
    },
    "legal_hold.lift": {
        "firm_admin": "allow",
        "mfa_recent": "required",
    },
    "engagement.create": {
        "firm_admin": "allow",
        "practice_leader": "allow",
    },
    "engagement.apply_methodology": {
        "engagement_partner": "allow",
        "manager": "allow",
    },
    "engagement.read_metadata": {
        "firm_admin": "allow",
        "practice_leader": "in_scope",
        "quality_partner": "allow",
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "staff": "allow",
        "reviewer": "allow",
    },
    "engagement.read": {
        "practice_leader": "in_scope",
        "quality_partner": "in_scope",
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "staff": "allow",
        "reviewer": "allow",
        "client_admin": "client_visible_only",
        "client_contributor": "client_visible_only",
    },
    "engagement.self_join": {
        "firm_admin": "allow",
        "notify": "engagement_team",
    },
    "engagement.update": {
        "engagement_partner": "allow",
        "manager": "allow",
    },
    "engagement.member_add": {
        "engagement_partner": "allow",
        "manager": "allow",
    },
    "engagement.member_remove": {
        "engagement_partner": "allow",
        "manager": "allow",
    },
    "engagement.archive": {
        "engagement_partner": "allow",
    },
    "request_item.read": {
        "practice_leader": "in_scope",
        "quality_partner": "in_scope",
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "staff": "allow",
        "reviewer": "allow",
        "client_admin": "client_visible_only",
        "client_contributor": "assigned_only",
        "agent": "task_scope",
    },
    "request_item.create": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
    },
    "request_item.update": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
    },
    "request_item.assign": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "client_admin": "allow",
    },
    "request_item.waive": {
        "engagement_partner": "allow",
        "manager": "allow",
        "requires": "reason",
    },
    "request_item.mark_ready": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "staff": "allow",
    },
    "evidence.read": {
        "practice_leader": "in_scope",
        "quality_partner": "in_scope",
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "staff": "allow",
        "reviewer": "allow",
        "client_admin": "client_visible_only",
        "client_contributor": "assigned_only",
        "agent": "task_scope",
    },
    "evidence.upload": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "staff": "allow",
        "client_admin": "allow",
        "client_contributor": "assigned_only",
        "system": "allow",
    },
    "evidence.accept": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "firm_setting(seniors_can_accept)",
        "agent": "deny",
    },
    "evidence.reject": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "firm_setting(seniors_can_accept)",
        "agent": "deny",
    },
    "evidence.void": {
        "engagement_partner": "allow",
        "manager": "allow",
        "requires": "reason",
    },
    "fulfilment.propose": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "staff": "allow",
        "agent": "task_scope",
        "system": "allow",
    },
    "fulfilment.confirm": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "agent": "deny",
    },
    "review.read": {
        "practice_leader": "in_scope",
        "quality_partner": "in_scope",
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "staff": "allow",
        "reviewer": "allow",
        "agent": "deny",
    },
    "review.take": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "firm_setting(seniors_can_accept)",
        "agent": "deny",
    },
    "review.assign": {
        "engagement_partner": "allow",
        "manager": "allow",
        "agent": "deny",
    },
    "screening.run": {
        "system": "allow",
        "agent": "task_scope",
    },
    "suggestion.create": {
        "agent": "task_scope",
    },
    "suggestion.resolve": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "agent": "deny",
    },
    "message.send": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "agent": "deny",
        "system": "deny",
    },
    "connection.create": {
        "client_admin": "allow",
    },
    "connection.revoke": {
        "client_admin": "allow",
        "engagement_partner": "allow",
        "manager": "allow",
    },
    "connection.pull": {
        "system": "allow",
    },
    "connection.read_log": {
        "client_admin": "allow",
        "engagement_partner": "allow",
        "manager": "allow",
    },
    "follow_up.draft": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "staff": "allow",
        "agent": "task_scope",
    },
    "follow_up.send": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
        "agent": "firm_setting(autonomy_policy)",
    },
    "sample_set.create": {
        "engagement_partner": "allow",
        "manager": "allow",
        "senior": "allow",
    },
    "support_match.run": {
        "system": "allow",
        "agent": "task_scope",
    },
    "audit_event.read": {
        "engagement_partner": "allow",
        "manager": "allow",
        "quality_partner": "in_scope",
        "firm_admin": "allow",
    },
    "export.create": {
        "engagement_partner": "allow",
        "manager": "allow",
        "mfa_recent": "required",
    },
}
