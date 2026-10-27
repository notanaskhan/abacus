"""GENERATED from docs/architecture/ai-policy-defaults.yaml. Do not edit.
Regenerate: python -m abacus_tools.codegen.ai_policy_defaults
"""

from __future__ import annotations

import json
from typing import Final, cast

_DOCUMENT: Final[dict[str, object]] = json.loads(
    r"""
{
  "gates": [
    {
      "actions": [
        "evidence.accept"
      ],
      "approver_roles": [
        "engagement_partner",
        "manager",
        "senior",
        "staff"
      ],
      "approver_rule": "staff_or_above_approve_document",
      "attest": "never",
      "gate_key": "classify_file_document",
      "log_action": "evidence.accepted",
      "policy_acceptance_available": true,
      "row": 1,
      "where_shown": [
        "SHL-10",
        "SHL-11",
        "AUD-03"
      ]
    },
    {
      "actions": [
        "sign_off.prepare"
      ],
      "approver_roles": [
        "manager",
        "senior",
        "staff"
      ],
      "approver_rule": "preparer_adopts_l1",
      "attest": "never",
      "gate_key": "adopt_draft",
      "log_action": "sign_off.created",
      "row": 2,
      "where_shown": [
        "SHL-12",
        "TAX-09",
        "CLS-07"
      ]
    },
    {
      "actions": [
        "checkpoint.approve"
      ],
      "approver_roles": [
        "engagement_partner",
        "manager",
        "senior"
      ],
      "approver_rule": "preparer_or_reviewer",
      "attest": "never",
      "gate_key": "change_after_draft",
      "log_action": "checkpoint.approved",
      "row": 3,
      "where_shown": [
        "SHL-09"
      ]
    },
    {
      "actions": [
        "issue.resolve"
      ],
      "approver_roles": [
        "engagement_partner",
        "manager",
        "senior",
        "staff"
      ],
      "approver_rule": "assignee",
      "attest": "never",
      "gate_key": "resolve_issue",
      "log_action": "issue.resolved",
      "row": 4,
      "where_shown": [
        "SHL-13"
      ]
    },
    {
      "actions": [
        "adjustment.approve"
      ],
      "approver_roles": [
        "engagement_partner",
        "manager"
      ],
      "approver_rule": "named_human_one_batch",
      "attest": "never_held_for_client",
      "gate_key": "aje_within_threshold",
      "log_action": "adjustment.approved",
      "policy_acceptance_available": true,
      "row": 5,
      "where_shown": [
        "CLS-07",
        "AUD-14"
      ]
    },
    {
      "actions": [
        "adjustment.approve"
      ],
      "approver_roles": [
        "engagement_partner",
        "manager"
      ],
      "approver_rule": "manager_or_partner",
      "attest": "never",
      "gate_key": "aje_above_threshold",
      "log_action": "adjustment.approved",
      "row": 6,
      "where_shown": [
        "CLS-07",
        "AUD-14"
      ]
    },
    {
      "actions": [],
      "approver_roles": [],
      "approver_rule": "senior_with_approved_batch",
      "attest": "posting_disabled",
      "gate_key": "post_batch_to_gl",
      "log_action": "write_capability.executed",
      "row": 7,
      "where_shown": [
        "CLS-07"
      ]
    },
    {
      "actions": [],
      "approver_roles": [],
      "approver_rule": "reviewer_after_final_approval",
      "gate_key": "export_return_to_engine",
      "log_action": "write_capability.executed",
      "row": 8,
      "where_shown": [
        "TAX-09"
      ]
    },
    {
      "actions": [
        "follow_up.send"
      ],
      "approver_roles": [
        "client_service",
        "engagement_partner",
        "manager",
        "senior",
        "staff"
      ],
      "approver_rule": "staff_or_firm_admin_templates",
      "attest": "never",
      "gate_key": "send_client_message",
      "log_action": "message.sent",
      "row": 9,
      "where_shown": [
        "SHL-04",
        "POR-20"
      ]
    },
    {
      "actions": [],
      "approver_roles": [],
      "approver_rule": "manager_or_partner",
      "gate_key": "send_notice_response",
      "log_action": "notice.response_sent",
      "row": 10,
      "where_shown": [
        "NOT-03"
      ]
    },
    {
      "actions": [
        "materiality.decide",
        "risk.approve",
        "finding.conclude_severity"
      ],
      "approver_roles": [
        "engagement_partner"
      ],
      "approver_rule": "engagement_partner_decision_card",
      "attest": "never",
      "gate_key": "partner_decisions",
      "log_action": "decision.decided",
      "row": 11,
      "where_shown": [
        "SHL-11",
        "AUD-07"
      ]
    },
    {
      "actions": [
        "methodology.approve"
      ],
      "approver_roles": [
        "quality_partner"
      ],
      "approver_rule": "methodology_owner_publishes",
      "gate_key": "agent_instructions_change",
      "log_action": "methodology.approved",
      "row": 12,
      "where_shown": [
        "KNW-02",
        "WRK-03"
      ]
    }
  ],
  "locks": [
    "policy_principal.on",
    "gates.*.policy_acceptance_on",
    "client_data.require_7216_consent"
  ],
  "schema_version": 1,
  "sections": {
    "auto_mode_defaults": {
      "advisory": false,
      "ebp_audit": false,
      "fs_audit": false,
      "monthly_close": true,
      "notice": false,
      "preparation": false,
      "review_compilation": false,
      "tax_return": true
    },
    "autonomy": {
      "level": 1
    },
    "client_data": {
      "client_drafts_enabled": false,
      "consent_template_ref": null,
      "disclosure_in_letters": true,
      "require_7216_consent": true
    },
    "gates": [],
    "governance": {
      "accuracy_sample_n": 25,
      "install_role": "manager_plus",
      "override_tolerance_pct": 8,
      "publish_approver": "methodology_owner",
      "trace_retention_years": 7
    },
    "policy_principal": {
      "on": false
    }
  },
  "stricter": {
    "auto_mode_defaults.advisory": "lower",
    "auto_mode_defaults.ebp_audit": "lower",
    "auto_mode_defaults.fs_audit": "lower",
    "auto_mode_defaults.monthly_close": "lower",
    "auto_mode_defaults.notice": "lower",
    "auto_mode_defaults.preparation": "lower",
    "auto_mode_defaults.review_compilation": "lower",
    "auto_mode_defaults.tax_return": "lower",
    "client_data.client_drafts_enabled": "lower",
    "client_data.disclosure_in_letters": "higher",
    "governance.accuracy_sample_n": "higher",
    "governance.override_tolerance_pct": "lower",
    "governance.trace_retention_years": "higher"
  }
}
"""
)
SCHEMA_VERSION: Final = cast(int, _DOCUMENT["schema_version"])
SECTIONS: Final = cast(dict[str, object], _DOCUMENT["sections"])
LOCKS: Final = tuple(cast(list[str], _DOCUMENT["locks"]))
STRICTER: Final = cast(dict[str, str], _DOCUMENT["stricter"])
GATES: Final = tuple(cast(list[dict[str, object]], _DOCUMENT["gates"]))
