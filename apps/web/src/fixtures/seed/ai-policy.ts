// G-02-T15: the Brightwater Hale AI policy for ADM-04 fixture mode, typed with the AI-policy
// contract v1 (docs/contracts/ai-policy.md). Versions v1 Jan 5, v2 Jan 9, v3 Jan 14, 2026
// (Margaret Okonkwo requests, Daniel Reyes approves: seed/governance.ts, the shared golden); the
// twelve gate rows of chapter 05 §5.2.13; Auto mode on for tax returns and monthly closes only
// (synthetic firm); override tolerance 8% (b and d: 6%); v4 effective Sep 15, 2026 (g).
// Rows carry codes; ADM-04's copy registry (G-02-T25) words them. Synthetic only.
import type {
  PolicyAgentStageOut,
  AiPolicyDiffRowOut,
  AiPolicyDraftOut,
  AiPolicyOut,
  AiPolicySections,
  AiPolicyVersionDetailOut,
  AiPolicyVersionOut,
  CellLockOut,
  GateRowOut,
  ImmediateControlsOut,
  SubProcessorOut,
} from "@abacus/api-client";
import { AI_POLICY_VERSIONS, DANIEL, MARGARET, type PersonRef } from "./governance";
import { stableId } from "./prng";

/** E0: Mon Sep 14, 2026, 9:24 AM CT; g reads the next morning, after v4 took effect. */
export const AI_POLICY_E0 = "2026-09-14T14:24:00Z";
export const AI_POLICY_G = "2026-09-15T14:24:00Z";
const GRACE: PersonRef = {
  user_id: stableId("user:grace-holloway"),
  display_name: "Grace Holloway",
};

export const SECTIONS_V3: AiPolicySections = {
  autonomy: { level: 1 },
  gates: [
    { action_key: "document.classify", policy_acceptance_on: false },
    { action_key: "aje.approve_batch", policy_acceptance_on: false },
  ],
  policy_principal: { on: false },
  auto_mode_defaults: {
    ebp_audit: false,
    fs_audit: false,
    review_compilation: false,
    preparation: false,
    tax_return: true,
    monthly_close: true,
    notice: false,
    advisory: false,
  },
  client_data: {
    require_7216_consent: true,
    consent_template_ref: null,
    disclosure_in_letters: true,
    client_drafts_enabled: false,
  },
  governance: {
    install_role: "manager_plus",
    publish_approver: "methodology_owner",
    override_tolerance_pct: 8,
    accuracy_sample_n: 25,
    trace_retention_years: 7,
  },
};

/** b, d: the one change Margaret makes, "Override tolerance 8% → 6%". */
export const SECTIONS_V4: AiPolicySections = {
  ...SECTIONS_V3,
  governance: { ...SECTIONS_V3.governance, override_tolerance_pct: 6 },
};
export const DIFF_V4: AiPolicyDiffRowOut[] = [
  { path: "governance.override_tolerance_pct", before: "8", after: "6" },
];

const at = (day: string): string => `${day}T15:00:00Z`;

/** v1 to v3, published; each superseded but the last. */
export const VERSIONS: AiPolicyVersionOut[] = AI_POLICY_VERSIONS.map((v, index) => ({
  version_no: v.version,
  state: "published",
  schema_version: 1,
  effective_from: at(v.published_on),
  requested_by: v.requested_by,
  requested_at: at(v.published_on),
  approver: v.approved_by,
  decided_by: v.approved_by,
  decided_at: at(v.published_on),
  carried_over: false,
  superseded: index < AI_POLICY_VERSIONS.length - 1,
}));
export const V3: AiPolicyVersionOut = VERSIONS[VERSIONS.length - 1] as AiPolicyVersionOut;

/** "Awaiting approval · Daniel Reyes": v4 requested by Margaret, effective Sep 15, 2026. */
export const V4_AWAITING: AiPolicyVersionOut = {
  version_no: 4,
  state: "awaiting_approval",
  schema_version: 1,
  effective_from: "2026-09-15T05:00:00Z",
  requested_by: MARGARET,
  requested_at: AI_POLICY_E0,
  approver: DANIEL,
  decided_by: null,
  decided_at: null,
  carried_over: false,
  superseded: false,
};
/** g: Daniel approved; v4 is effective from Sep 15. */
export const V4_PUBLISHED: AiPolicyVersionOut = {
  ...V4_AWAITING,
  state: "published",
  decided_by: DANIEL,
  decided_at: "2026-09-14T14:31:00Z",
};

/** The diff of each version against the one before (j). v1 has none. The handoff's v2 and v3
 * diff lines are not in the repository, so they stay empty here rather than invented; G-02-T25
 * copies them from the ADM-04 handoff spec (DEC-532). */
export const VERSION_DIFFS: Record<number, AiPolicyDiffRowOut[]> = {
  1: [],
  2: [],
  3: [],
  4: DIFF_V4,
};

const gate = (
  row: number,
  gateKey: string,
  approverRule: string,
  extra: Partial<GateRowOut> = {},
): GateRowOut => ({
  row,
  gate_key: gateKey,
  action_keys: [],
  approver_rule: approverRule,
  default_approver_roles: [],
  policy_acceptance_available: false,
  policy_acceptance_on: false,
  policy_acceptance_locked: true,
  acceptance_policy_ref: null,
  attest: null,
  where_shown: [],
  log_action: `gate.${gateKey}`,
  ...extra,
});

/** Fieldset A: chapter 05 §5.2.13's twelve rows; rows 1 and 5 offer policy acceptance, Off and
 * locked (ADR-187). Row 5's popover lists where the gate appears (i). */
export const GATES: GateRowOut[] = [
  gate(1, "classify_document", "staff_plus", {
    policy_acceptance_available: true,
    acceptance_policy_ref: "BH document confidence v1",
    attest: "never",
  }),
  gate(2, "draft_work", "preparer_adopts", { attest: "never" }),
  gate(3, "change_after_draft", "preparer_or_reviewer", { attest: "never" }),
  gate(4, "resolve_issue", "assignee", { attest: "never" }),
  gate(5, "aje_within_threshold", "named_human_one_batch", {
    action_keys: ["aje.approve_batch"],
    policy_acceptance_available: true,
    acceptance_policy_ref: "BH AJE thresholds v2",
    attest: "never_held_for_client",
    where_shown: ["SHL-10", "SHL-11", "SHL-12", "CLS-07", "TAX-09"],
  }),
  gate(6, "aje_above_threshold", "manager_or_partner", { attest: "never" }),
  gate(7, "post_batch", "senior_with_approved_batch", { attest: "posting_disabled" }),
  gate(8, "export_return", "reviewer_after_final_approval"),
  gate(9, "send_client_message", "staff_or_firm_admin", { attest: "never" }),
  gate(10, "send_notice_response", "manager_or_partner"),
  gate(11, "decision_card", "engagement_partner", { attest: "never" }),
  gate(12, "change_firm_agent", "methodology_owner"),
];

const lock = (path: string, reason: CellLockOut["reason"]): CellLockOut => ({ path, reason });
/** Locked cells on the synthetic firm (h): the dormant principal, the platform floors. */
export const LOCKS: CellLockOut[] = [
  lock("policy_principal.on", "policy_principal_dormant"),
  lock("gates.document.classify.policy_acceptance_on", "policy_principal_dormant"),
  lock("gates.aje.approve_batch.policy_acceptance_on", "policy_principal_dormant"),
  lock("client_data.require_7216_consent", "platform_floor"),
  lock("client_data.client_drafts_enabled", "platform_floor"),
  lock("governance.trace_retention_years", "platform_floor"),
];
/** e: Hannah Leclerc is not a partner, so every band is locked. */
export const NOT_A_PARTNER: CellLockOut[] = [
  ...LOCKS,
  ...["autonomy", "gates", "auto_mode_defaults", "client_data", "governance"].map((path) =>
    lock(path, "not_a_partner"),
  ),
];

const stage = (
  agentKey: string,
  s: PolicyAgentStageOut["stage"],
  since: string,
): PolicyAgentStageOut => ({
  agent_key: agentKey,
  stage: s,
  since,
});
/** The band: the client-data opt-in on since Jun 1 (Grace Holloway), Evidence screening and
 * Upload review in Shadow until the founders promote them, no firm pause. */
export const IMMEDIATE: ImmediateControlsOut = {
  client_data_opt_in: {
    on: true,
    changed_at: "2026-06-01T14:00:00Z",
    changed_by: GRACE,
    register_version: null,
  },
  agent_stages: [
    stage("evidence_screening", "shadow", "2026-06-01T14:00:00Z"),
    stage("upload_review", "shadow", "2026-06-01T14:00:00Z"),
  ],
  firm_pause: { paused: false, paused_at: null, paused_by: null },
};

/** Fieldset D, generated from the provider-terms register (DF-16): one route, Bedrock. */
export const SUB_PROCESSORS: SubProcessorOut[] = [
  {
    name: "Amazon Web Services (Bedrock)",
    purpose: "model_inference",
    region: "US",
    trains_on_data: false,
    retention_days: null,
  },
];

export const ACTIONS_MARGARET = ["ai_policy.read", "ai_policy.draft", "ai_policy.publish"];
export const ACTIONS_DANIEL = ["ai_policy.read", "ai_policy.approve"];
export const ACTIONS_READ = ["ai_policy.read"];
export const ACTIONS_GRACE = ["ai_policy.read", "firm_agents.pause"];

export function draftOf(sections: AiPolicySections, base = 3): AiPolicyDraftOut {
  const differs = sections !== SECTIONS_V3;
  return {
    base_version_no: base,
    sections,
    differs,
    diff: differs ? DIFF_V4 : [],
    version: differs ? 1 : 0,
    updated_at: differs ? AI_POLICY_E0 : null,
    updated_by: differs ? MARGARET : null,
  };
}

export type AiPolicyView =
  | "a" // clean draft, Save as v4… disabled
  | "b" // Unsaved changes: 8% → 6%
  | "awaiting" // v4 waits for Daniel Reyes
  | "g" // v4 effective Sep 15
  | "read_only" // Hannah Leclerc
  | "band" // Grace Holloway: the immediate controls
  | "real_firm"; // a non-synthetic firm: Auto mode off and locked

export function policyOf(view: AiPolicyView, actions: string[]): AiPolicyOut {
  const effective = view === "g" ? V4_PUBLISHED : V3;
  const sections = view === "g" ? SECTIONS_V4 : SECTIONS_V3;
  const realFirm = view === "real_firm";
  return {
    effective,
    sections,
    pending: view === "awaiting" ? V4_AWAITING : null,
    scheduled: null,
    draft: view === "b" ? draftOf(SECTIONS_V4) : draftOf(sections, effective.version_no),
    gates: GATES,
    locks: [
      ...(view === "read_only" ? NOT_A_PARTNER : LOCKS),
      ...(realFirm
        ? Object.keys(SECTIONS_V3.auto_mode_defaults).map((key) =>
            lock(`auto_mode_defaults.${key}`, "real_firm_season_1"),
          )
        : []),
    ],
    immediate: IMMEDIATE,
    sub_processors: SUB_PROCESSORS,
    // The register (docs/operations/provider-terms.yaml) has no entry yet: no model is named.
    model_family: null,
    real_firm: realFirm,
    actions,
  };
}

export function versionDetail(versionNo: number): AiPolicyVersionDetailOut | null {
  const version =
    versionNo === 4 ? V4_PUBLISHED : VERSIONS.find((v) => v.version_no === versionNo);
  if (version === undefined) return null;
  return {
    ...version,
    sections: versionNo === 4 ? SECTIONS_V4 : SECTIONS_V3,
    diff: VERSION_DIFFS[versionNo] ?? [],
  };
}
