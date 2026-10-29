// KNW-04 Firm standards & thresholds: every string verbatim from the handoff (spec.md and the nine
// artboards; docs/screens/KNW-04.md "Copy"). K-02-T13.
import type { IconName } from "@abacus/ui";

export type Section =
  | "review_checklists"
  | "review_levels"
  | "return_approval"
  | "aje_thresholds"
  | "variance_thresholds"
  | "materiality_ranges"
  | "document_confidence"
  | "ssars_cas";

export type StandardKind =
  | "review_checklist"
  | "review_levels"
  | "return_approval_policy"
  | "ssars_cas_settings"
  | "aje_thresholds"
  | "variance_thresholds"
  | "materiality_ranges"
  | "document_confidence";

export const SECTIONS: readonly {
  id: Section;
  label: string;
  icon: IconName;
  kind: StandardKind;
}[] = [
  {
    id: "review_checklists",
    label: "Review checklists",
    icon: "list-checks",
    kind: "review_checklist",
  },
  { id: "review_levels", label: "Review levels", icon: "layers", kind: "review_levels" },
  {
    id: "return_approval",
    label: "Return approval",
    icon: "signature",
    kind: "return_approval_policy",
  },
  { id: "aje_thresholds", label: "AJE thresholds", icon: "scale", kind: "aje_thresholds" },
  {
    id: "variance_thresholds",
    label: "Variance thresholds",
    icon: "chart-column",
    kind: "variance_thresholds",
  },
  // The handoff draws lucide Target; the icon set has none yet, so the nearest glyph stands in
  // (KNW-04 deviation D4).
  {
    id: "materiality_ranges",
    label: "Materiality ranges",
    icon: "circle-dot",
    kind: "materiality_ranges",
  },
  {
    id: "document_confidence",
    label: "Document confidence",
    icon: "file-search",
    kind: "document_confidence",
  },
  { id: "ssars_cas", label: "SSARS & CAS", icon: "book-open", kind: "ssars_cas_settings" },
];

export const COPY = {
  title: "Firm standards & thresholds",
  back: "Knowledge",
  navTitle: "Standards",
  group: "Standards",
  newVersion: "New version…",
  apply: "Apply to returns…",
  version: (n: number) => `v${String(n)}`,
  published: (date: string, name: string) => `Published ${date} · ${name}`,
  publishedOwner: (name: string) => `Published · owner ${name}`,
  owner: (name: string) => `Owner ${name}`,
  loading: "Loading standards",
  error: "Standards could not be loaded.",
  retry: "Try again",
  flagLabel: "Firm standards",
  checklists: {
    title: "Review checklists",
    meta: (year: number) => `TY${String(year)} · select one to apply`,
    head: ["Checklist", "Checks", "Version", "Applied to", "Owner"],
    returns: (n: number) => `${String(n)} ${n === 1 ? "return" : "returns"}`,
    total: "Total",
    totalReturns: (n: number, year: number) => `${String(n)} TY${String(year)} returns`,
    draftRow: (name: string, n: number, year: number | null) =>
      `${name} v${String(n)}${year === null ? "" : ` (TY${String(year)})`}`,
    draft: "Draft",
    card: "Firm standards",
    openRun: "Open the run",
    plannedRun: "Opens TAX-14 · firm standards run",
    passed: "Passed",
    exceptions: (n: string) => `${n} exceptions`,
    running: (of: string) => `Running… ${of}`,
  },
  levels: {
    head: ["Tier", "Sign-offs", "Applies when"],
    tier: (n: number, name: string) => `Tier ${String(n)} · ${name}`,
    names: { L1: "Preparer", L2: "Reviewer", L3: "Manager", L4: "Partner", L5: "EQR" } as const,
    secondPartner: "second-partner review",
    helper:
      "The tier sets the sign-offs a return needs before final approval under BH-TAX-02 (Return approval).",
  },
  approval: {
    rule: "Rule",
    appliesTo: "Applies to",
    export: "Export",
    rules: {
      signing_partner_final_approval:
        "The signing partner gives final approval on returns he or she signs",
    } as Record<string, string>,
    exports: {
      after_final_approval: "Only after final approval, by the approving reviewer",
    } as Record<string, string>,
    helper: "Accrued Agent prepares and cites; final approval is always a named partner.",
  },
  aje: {
    head: ["Account class", "Within threshold up to", "Approved by"],
    reviewRequired: "Review required",
    alwaysHeld: "Always held",
    approver: {
      senior_or_above: "Senior or above",
      manager_or_partner: "Manager or partner",
      partner: "Partner",
    } as const,
    batch: ", as one batch",
    helper:
      "Within-threshold entries still need a named person; they are approved together as one batch under this policy version.",
    policyTitle: "Policy acceptance",
    policyToggle: (name: string) =>
      `Let the policy accept within-threshold entries without a person (logged as ‘Policy: ${name}’)`,
    policyHelper: "Managed in Firm settings › AI policy. Never applies to attest clients.",
    examplesTitle: (v: number) => `How v${String(v)} sorted the August 2026 closes`,
    examplesHead: ["Entry", "Amount", "Result"],
    within: (detail: string) => `Within threshold · ${detail}`,
    held: (detail: string) => `Review required · ${detail}`,
    totalWithin: (n: number, sum: string, who: string) =>
      `${String(n)} within threshold · ${sum} · approved as one batch by ${who}`,
    totalHeld: (n: number, sum: string, who: string) =>
      `${String(n)} held · ${sum} · approved by ${who}`,
    openAjes: "Open Copperleaf AJEs",
    plannedAjes: "Opens CLS-06 · close review",
  },
  variance: {
    head: ["Used in", "Change", "Amount", "Flagged when"],
    contexts: {
      close_flux: "Close flux",
      ssars_review_analytics: "SSARS review analytics",
      tax_two_year: "Tax two-year comparison",
    } as Record<string, string>,
    both: "Both must be exceeded",
    example: "Example",
  },
  materiality: {
    head: ["Applies to", "Benchmark", "Range"],
    performance: "Performance materiality",
    clearlyTrivial: "Clearly trivial",
    ofMateriality: "Materiality",
    reserved: "Decisions are reserved to the engagement partner.",
    engagements: "Engagements",
    engagementsHead: ["Engagement", "Materiality", "Performance", "Clearly trivial", "Status"],
    decided: "Decided",
    blocked: "Blocked on a partner decision",
    waiting: (name: string) => `Waiting on ${name}`,
    plannedAud07: "Opens AUD-07 · materiality decision",
  },
  confidence: {
    hold: "Hold for staff",
    holdValue: (pct: string) => `Below ${pct}% confidence`,
    auto: "Auto-accept",
    autoValue: (pct: string) => `Above ${pct}% confidence · off`,
    autoToggle: (pct: string) => `Auto-accept documents above ${pct}% without a person`,
    autoHelper:
      "Off as a policy principle: a person accepts every document. Managed in Firm settings › AI policy.",
    example: "Example",
  },
  ssars: {
    title: "SSARS & CAS",
    toggle: "Early-adopt SSARS 27 for CAS monthly statements",
    helper:
      "Off: periods ending before Dec 15, 2026 are prepared under AR-C 70 with “No assurance is provided” on each page. Periods ending on or after Dec 15, 2026 are CAS by-products with no SSARS report or legend.",
    frameworks: {
      ar_c_70_preparation: "AR-C 70 preparation",
      cas_by_product: "CAS by-product",
    } as Record<string, string>,
  },
  versions: "Versions",
  timeline: (state: "published" | "superseded" | "draft", current: boolean) =>
    state === "published"
      ? current
        ? "Published (current)"
        : "Published"
      : state === "draft"
        ? "Draft"
        : "Superseded",
  examplesEmpty: "No examples yet",
  examplesEmptyBody: "Examples appear here once the work that applies this standard is recorded.",
  plannedAdm04: "Opens ADM-04 · AI policy",
} as const;
