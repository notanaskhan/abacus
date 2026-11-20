// K-03-T08 (TASK-8852): the TV-1 fixture slice for KNW-06, KNW-07, SHL-22 and SHT-03, typed by the
// templates v2 contract (C22). BH Audit Methodology · FS, Thu Oct 1, 2026. Figures follow the
// handoffs and blueprint §9.9: 35 → 38 steps, 12 → 14 sheets, requests 41 + 6 by rule; the change
// list Added 3 + Changed 5 + Removed 0 = 8; rollout 6 live · 3 Update now · 0 On rollover · 3 Hold.
import type {
  ChangeListOut,
  TemplateCheckListOut,
  RolloutOut,
  ScopingPreviewOut,
  ScopingRulesOut,
  TemplateLinkOut,
  TemplateUpdateOut,
  EngagementTemplateVersionOut,
  UsedByListOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const TEMPLATE_ID = stableId("template:bh-audit-fs");
export const FS_V5 = stableId("template-version:fs-v5");
export const FS_V6 = stableId("template-version:fs-v6");
export const HARLOW = stableId("engagement:a28-harlow-pike");
export const GRANITE = stableId("engagement:a2-granite-peak");
const MARGARET = { user_id: stableId("user:margaret-okonkwo"), name: "Margaret Okonkwo" };

const RAIL_V6 = {
  program_steps: 38,
  sheets: 14,
  forms: 6,
  requests: 41,
  requests_by_rule: 6,
  triggers: 2,
  report_templates: 3,
  skills: 5,
  scoping_rules: 6,
};
const RAIL_V5 = {
  program_steps: 35,
  sheets: 12,
  forms: 6,
  requests: 41,
  requests_by_rule: 0,
  triggers: 2,
  report_templates: 3,
  skills: 5,
  scoping_rules: 0,
};

export function version(
  which: "v5" | "v6",
  status: EngagementTemplateVersionOut["status"],
): EngagementTemplateVersionOut {
  const v6 = which === "v6";
  return {
    version_id: v6 ? FS_V6 : FS_V5,
    template_id: TEMPLATE_ID,
    seq: v6 ? 6 : 5,
    label: v6 ? "FS v6" : "FS v5",
    status,
    retired: false,
    effective_from: v6 ? (status === "published" ? "2026-10-01" : null) : "2026-01-01",
    based_on_version_id: v6 ? FS_V5 : null,
    rail: v6 ? RAIL_V6 : RAIL_V5,
    used_by: v6 ? 0 : 6,
    draft_etag: status === "draft" ? 14 : null,
    published_by: status === "published" ? MARGARET : null,
    published_at: status === "published" ? "2026-10-01T09:38:00-05:00" : null,
    allowed_actions: status === "draft" ? ["edit", "publish"] : ["deprecate", "rollout"],
  };
}

export const CHECKS_FAILING: TemplateCheckListOut = {
  items: [
    {
      code: "required_column_without_source",
      severity: "error",
      component: "sheets",
      item_ref: "Group scoping · Component",
      fix_link: null,
    },
    {
      code: "rule_reads_absent_field",
      severity: "error",
      component: "scoping_rules",
      item_ref: "Rule 4",
      fix_link: null,
    },
    {
      code: "skill_draft",
      severity: "warning",
      component: "skills",
      item_ref: "BH-SK-430 v2",
      fix_link: null,
    },
  ],
  errors: 2,
  warnings: 1,
};

const CHANGE_ROWS: readonly [
  ChangeListOut["items"][number]["kind"],
  ChangeListOut["items"][number]["component"],
  string,
][] = [
  ["added", "program", "BH-FS-700 Group scoping & component materiality"],
  ["added", "program", "BH-FS-710 Component auditor instructions & communications"],
  ["added", "program", "BH-FS-720 Consolidation & eliminations"],
  ["changed", "program", "BH-FS-430 Search for unrecorded liabilities"],
  ["changed", "request_list", "Request list"],
  ["changed", "report_templates", "Planning memo template"],
  ["changed", "triggers", "Trigger defaults"],
  ["changed", "forms", "Materiality form"],
];

export const CHANGES: ChangeListOut = {
  items: CHANGE_ROWS.map(([kind, component, label], i) => ({
    change_key: `c${String(i + 1)}`,
    kind,
    component,
    item_ref: label,
    label,
  })),
  added: 3,
  changed: 5,
  removed: 0,
};

export function rollout(status: RolloutOut["status"] = "not_started"): RolloutOut {
  const rows: RolloutOut["rows"] = [
    ["A28 Harlow & Pike", "update_now", null],
    ["A18 Larimer", "update_now", null],
    ["A21 Halcyon", "update_now", null],
    ["A2 Granite Peak", "hold", "Planning approved Sep 14; adopt at the FY2027 roll-forward"],
    ["A19 Sable Creek", "hold", "Fieldwork underway; adopt at roll-forward"],
    ["A22 Oakline", "hold", "Report date Oct 9; adopt at roll-forward"],
  ].map(([label, action, reason]) => ({
    engagement_id: stableId(`engagement:${String(label)}`),
    label: String(label),
    suggested_action: action as "update_now" | "hold",
    action: action as "update_now" | "hold",
    reason: reason ?? null,
    eligible: true,
  }));
  return {
    status,
    rows,
    live: 6,
    update_now: 3,
    on_rollover: 0,
    hold: 3,
    updated: status === "in_progress" ? 1 : 0,
  };
}

export const USED_BY: UsedByListOut = {
  items: [
    ["A28 Harlow & Pike", "Planning"],
    ["A18 Larimer", "Planning"],
    ["A21 Halcyon", "Planning"],
    ["A2 Granite Peak", "Fieldwork"],
    ["A19 Sable Creek", "Fieldwork"],
    ["A22 Oakline", "Completion"],
    ["A20 Meridian", "Archived"],
  ].map(([label, phase]) => ({
    engagement_id: stableId(`engagement:${String(label)}`),
    label: String(label),
    phase: String(phase),
  })),
  total: 7,
};

export function scopingRules(count = 6, conflict = false): ScopingRulesOut {
  const rule = (n: number, then: "show" | "hide" | "add_requests", target: string) => ({
    rule_id: stableId(`scoping-rule:${String(n)}`),
    position: n,
    when: [
      {
        source: n === 7 ? "assertion" : "planning_form.group_audit",
        operator: "equals",
        value: n === 7 ? "valuation.rmm=high" : "yes",
      },
    ],
    then,
    targets: [target],
  });
  const base = [
    rule(1, "show", "BH-FS-700"),
    rule(2, "show", "BH-FS-720"),
    rule(3, "show", "BH-FS-710"),
    rule(4, "hide", "single-entity materiality"),
    rule(5, "add_requests", "6 group requests"),
    rule(6, "show", "Component tracker"),
  ].slice(0, count);
  return { items: conflict ? [...base, rule(7, "hide", "BH-FS-720")] : base, etag: 3 };
}

export function scopingPreview(as: "harlow" | "granite"): ScopingPreviewOut {
  const rows = [1, 2, 3, 4, 5, 6].map((n) => ({
    rule_id: stableId(`scoping-rule:${String(n)}`),
    result: as === "granite" ? (n === 6 ? "shows" : "no_change") : n === 4 ? "hides" : "shows",
  })) as ScopingPreviewOut["rows"];
  return as === "granite"
    ? { rows, shows_steps: 0, shows_sheets: 1, hides: 0, adds_requests: 0 }
    : { rows, shows_steps: 3, shows_sheets: 2, hides: 1, adds_requests: 6 };
}

export function link(state: TemplateLinkOut["state"], engagement = HARLOW): TemplateLinkOut {
  return {
    engagement_id: engagement,
    template_id: TEMPLATE_ID,
    version_id: state === "updated" ? FS_V6 : FS_V5,
    version_label: state === "updated" ? "FS v6" : "FS v5",
    state,
    available_version_id: state === "update_available" ? FS_V6 : null,
    available_label: state === "update_available" ? "FS v6" : null,
    held_reason:
      state === "held" ? "Planning approved Sep 14; adopt at the FY2027 roll-forward" : null,
    updated_by: state === "updated" ? "Omar Haddad" : null,
    updated_at: state === "updated" ? "2026-10-01T10:21:00-05:00" : null,
    allowed_actions:
      state === "update_available" ? ["apply", "hold"] : state === "held" ? ["release"] : [],
  };
}

export function update(status: TemplateUpdateOut["status"], applied = 0): TemplateUpdateOut {
  return {
    update_id: status === "dry_run" ? null : stableId("template-update:harlow"),
    to_version_id: FS_V6,
    status,
    changes: CHANGES.items.map((c, i) => ({
      change_key: c.change_key,
      kind: c.kind,
      label: c.label,
      effect_here: c.kind === "added" ? "New and empty" : "Your work is kept",
      status: i < applied ? "applied" : "pending",
    })),
    added: 3,
    changed: 5,
    removed: 0,
    applied,
    workflow_id: status === "dry_run" ? null : "template_update:harlow:fs-v6",
  };
}
