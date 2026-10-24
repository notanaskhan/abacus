"""GENERATED from docs/architecture/role-templates.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.role_templates
"""

TEMPLATES: dict[str, dict[str, object]] = {
    "partner": {
        "levels": [
            "partner",
        ],
        "firm_role": None,
        "roles": [
            "firm_partner",
            "engagement_partner",
            "practice_leader",
            "quality_partner",
        ],
    },
    "manager": {
        "levels": [
            "manager",
        ],
        "firm_role": None,
        "roles": [
            "manager",
        ],
    },
    "tax_reviewer": {
        "levels": [
            "manager",
            "senior",
        ],
        "firm_role": None,
        "roles": [
            "manager",
            "senior",
        ],
    },
    "senior": {
        "levels": [
            "senior",
        ],
        "firm_role": None,
        "roles": [
            "senior",
        ],
    },
    "staff": {
        "levels": [
            "staff",
            "seasonal",
        ],
        "firm_role": None,
        "roles": [
            "staff",
        ],
    },
    "tax_preparer": {
        "levels": [
            "staff",
            "seasonal",
        ],
        "firm_role": None,
        "roles": [
            "staff",
        ],
    },
    "firm_admin": {
        "levels": [
            "admin",
        ],
        "firm_role": "firm_admin",
        "roles": [
            "firm_admin",
            "client_service",
        ],
    },
    "it_security": {
        "levels": [
            "admin",
        ],
        "firm_role": "security_admin",
        "roles": [
            "security_admin",
        ],
    },
}

GRID: tuple[dict[str, object], ...] = (
    {
        "key": "users_roles_offices",
        "label": "Users, roles, offices",
        "actions": [
            "firm.manage_users",
            "security_role.assign",
        ],
        "cells": {
            "partner": "deny",
            "manager": "deny",
            "tax_reviewer": "deny",
            "senior": "deny",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "allow",
            "it_security": "conditional",
        },
        "conditions": {
            "it_security": "security roles",
        },
    },
    {
        "key": "security_and_audit_log",
        "label": "SSO/MFA, API keys, MCP, audit log",
        "actions": [],
        "cells": {
            "partner": "conditional",
            "manager": "deny",
            "tax_reviewer": "deny",
            "senior": "deny",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "conditional",
            "it_security": "allow",
        },
        "conditions": {
            "partner": "read log",
            "firm_admin": "read log",
        },
    },
    {
        "key": "methodology_publish",
        "label": "Methodology / standards / threshold policy publish",
        "actions": [],
        "cells": {
            "partner": "allow",
            "manager": "delegated",
            "tax_reviewer": "deny",
            "senior": "deny",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {
            "partner": "QM owner",
        },
    },
    {
        "key": "create_client_engagement",
        "label": "Create client / engagement",
        "actions": [],
        "cells": {
            "partner": "allow",
            "manager": "allow",
            "tax_reviewer": "deny",
            "senior": "conditional",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "allow",
            "it_security": "deny",
        },
        "conditions": {},
    },
    {
        "key": "run_agents",
        "label": "Run / schedule agents",
        "actions": [],
        "cells": {
            "partner": "allow",
            "manager": "allow",
            "tax_reviewer": "allow",
            "senior": "allow",
            "staff": "conditional",
            "tax_preparer": "allow",
            "firm_admin": "conditional",
            "it_security": "deny",
        },
        "conditions": {
            "firm_admin": "firm-ops agents + Client Service request agents",
        },
    },
    {
        "key": "approve_source_document",
        "label": "Approve source document",
        "actions": [
            "evidence.accept",
        ],
        "cells": {
            "partner": "allow",
            "manager": "allow",
            "tax_reviewer": "allow",
            "senior": "allow",
            "staff": "allow",
            "tax_preparer": "allow",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {},
    },
    {
        "key": "adopt_agent_work",
        "label": "Adopt agent work (L1 preparer)",
        "actions": [
            "trial_balance.adopt",
            "entry_assessment.adopt",
        ],
        "cells": {
            "partner": "allow",
            "manager": "allow",
            "tax_reviewer": "allow",
            "senior": "allow",
            "staff": "allow",
            "tax_preparer": "allow",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {},
    },
    {
        "key": "reviewer_sign_off",
        "label": "Reviewer sign-off L2/L3",
        "actions": [
            "sign_off.review",
        ],
        "cells": {
            "partner": "allow",
            "manager": "allow",
            "tax_reviewer": "allow",
            "senior": "conditional",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {
            "senior": "staff work only",
        },
    },
    {
        "key": "partner_sign_off",
        "label": "Partner sign-off L4",
        "actions": [
            "sign_off.partner",
        ],
        "cells": {
            "partner": "allow",
            "manager": "deny",
            "tax_reviewer": "deny",
            "senior": "deny",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {},
    },
    {
        "key": "materiality_risk_opinion",
        "label": "Materiality, significant risks, deficiency severity, opinion",
        "actions": [
            "materiality.decide",
            "risk.approve",
        ],
        "cells": {
            "partner": "allow",
            "manager": "delegated",
            "tax_reviewer": "deny",
            "senior": "delegated",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {},
    },
    {
        "key": "final_return_approval",
        "label": "Final return approval",
        "actions": [],
        "cells": {
            "partner": "allow",
            "manager": "conditional",
            "tax_reviewer": "conditional",
            "senior": "deny",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {
            "partner": "signer",
            "manager": "if delegated (BH-TAX-02)",
            "tax_reviewer": "if delegated",
        },
    },
    {
        "key": "export_to_tax_engine",
        "label": "Export to tax engine",
        "actions": [],
        "cells": {
            "partner": "allow",
            "manager": "allow",
            "tax_reviewer": "allow",
            "senior": "deny",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {
            "tax_reviewer": "after approval",
        },
    },
    {
        "key": "approve_aje",
        "label": "Approve AJE within / above threshold",
        "actions": [],
        "cells": {
            "partner": "allow",
            "manager": "conditional",
            "tax_reviewer": "deny",
            "senior": "conditional",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {
            "manager": "within threshold; above with a condition",
            "senior": "within (batch)",
        },
    },
    {
        "key": "post_to_gl",
        "label": "Post to GL",
        "actions": [],
        "cells": {
            "partner": "allow",
            "manager": "allow",
            "tax_reviewer": "deny",
            "senior": "conditional",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {
            "senior": "approved batch",
        },
    },
    {
        "key": "release_audit_report",
        "label": "Release audit report",
        "actions": [
            "report.release",
        ],
        "cells": {
            "partner": "allow",
            "manager": "deny",
            "tax_reviewer": "deny",
            "senior": "deny",
            "staff": "deny",
            "tax_preparer": "deny",
            "firm_admin": "deny",
            "it_security": "deny",
        },
        "conditions": {
            "partner": "EP only",
        },
    },
    {
        "key": "reveal_tin",
        "label": "Reveal masked TIN/SSN (logged)",
        "actions": [
            "tin.reveal",
        ],
        "cells": {
            "partner": "allow",
            "manager": "allow",
            "tax_reviewer": "allow",
            "senior": "conditional",
            "staff": "conditional",
            "tax_preparer": "conditional",
            "firm_admin": "deny",
            "it_security": "conditional",
        },
        "conditions": {},
    },
)

AGENT_LABEL = "Accrued Agent \u00b7 non-human"
AGENT_NEVER: tuple[str, ...] = (
    "approve_source_document",
    "adopt_agent_work",
    "reviewer_sign_off",
    "partner_sign_off",
    "materiality_risk_opinion",
    "final_return_approval",
    "export_to_tax_engine",
    "approve_aje",
    "post_to_gl",
    "release_audit_report",
    "reveal_tin",
)
