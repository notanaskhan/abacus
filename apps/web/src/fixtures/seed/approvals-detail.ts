// HOME-02's detail pane in fixture mode (I-01-T17; docs/screens/HOME-02.md, Copy and Figures): the
// C3 answers the detail reads for the gates seed/home.ts lists, keyed to those gates' subjects. The
// §754 decision card as HOME-02a/b draw it (three options, the agent's recommendation on option 2),
// the Ridgeline 1065 section sign-offs at Partner (L4) (c blocked on the M-2 fix, d ready), and
// Samuel Ito's two agent outputs (g, the Feld passive classification). Copy is the handoff's,
// verbatim; ids are stable placeholders. Nothing here decides, signs or approves (INV-1): a write
// answers the frame the artboard shows after the person's act.

import type {
  AgentProposalOut,
  CitationV2Out,
  DecisionCardOut,
  EligibilityCheckOut,
  HumanGateOut,
  LadderLevelOut,
  SignOffEligibilityOut,
  SignOffLadderOut,
  SignOffOut,
  SignOffTargetOut,
  TeamRosterMemberOut,
} from "@abacus/api-client";
import { stableId } from "./prng";
import { RIDGELINE_RETURN, k1 } from "./review";

const user = (slug: string): string => stableId(`user:${slug}`);
const DANIEL = user("daniel-reyes");
const SAMUEL = user("samuel-ito");
const OLIVIA = user("olivia-brandt");
const KEVIN = user("kevin-osei");

/** The subject seed/home.ts gives a persona's n-th gate (1-based, in the handoff's row order). */
export const gateSubject = (persona: string, n: number): string =>
  stableId(`gate-subject:${persona}:${String(n)}`);

const id = (key: string): string => stableId(`home02:${key}`);
const ENGAGEMENT = stableId("engagement:home:ridgeline-property-partners-lp");

// ---- Decision 1: §754 election (a, b) -----------------------------------------------------------

export const DECISION_754 = gateSubject("daniel-reyes", 1);
const TRANSFER = id("evidence:transfer-agreement");
const BASIS = id("evidence:basis");
const LPA = id("evidence:lpa");

export const PROPOSED_754 = "2026-09-11T19:20:00Z";

const cite = (
  key: string,
  n: number,
  title: string,
  version: string,
  loc: string,
): CitationV2Out => ({
  id: id(`citation:${key}`),
  n,
  kind: "document_text",
  title,
  loc,
  quote: null,
  quote_state: "withheld",
  value_text: null,
  match_id: null,
  state: "valid",
  verified: true,
  verification_reason: null,
  created_by: { kind: "agent", label: "Accrued Agent" },
  retrieved_at: PROPOSED_754,
  used_in: 1,
  moved: null,
  allowed_actions: [],
  source: {
    type: "evidence_version",
    id: version,
    evidence_version_id: version,
    page: 1,
    version: "1",
  },
});

const TRANSFER_TITLE =
  "Membership interest transfer agreement — Pell Street Ventures LLC to Pell Street II LLC";

/** The decision card's citations, grouped by source in the detail: 2 + 1 + 1. */
export const DECISION_754_CITATIONS: readonly CitationV2Out[] = [
  cite("transfer-1", 1, TRANSFER_TITLE, TRANSFER, "§2.1 Purchase price"),
  cite("transfer-2", 2, TRANSFER_TITLE, TRANSFER, "§1.1 Transferred interest"),
  cite("basis", 3, "Basis at 12/31/2025 (TXP-08)", BASIS, "Pell Street II LLC"),
  cite("lpa", 4, "Ridgeline LPA · Article 9 Transfers", LPA, "Article 9"),
];

const WHY =
  "Pell Street Ventures LLC sold 5 of its 35 points to Pell Street II LLC on 6/30/2025 for $360,000. The capital transferred was 331,405 (5/35 of Pell Street Ventures' 6/30 capital of 2,319,835, including 1,085 of first-half tax-exempt interest, per Reg. §1.704-1(b)(2)(iv)(l)), so Pell Street II's outside basis exceeds its share of inside basis by 28,595. That difference is a §743(b) adjustment only if the partnership elects under §754 with a timely filed return. The election is irrevocable and applies to every later transfer and distribution, including step-downs.";

export const card754: DecisionCardOut = {
  card: {
    id: DECISION_754,
    engagement_id: ENGAGEMENT,
    work_item_id: id("work-item:1065"),
    kind: "section_754",
    version_no: 1,
    status: "awaiting_role",
    reserved_role: "engagement_partner",
    reserved_user_id: DANIEL,
    reserved_user_name: "Daniel Reyes",
    requested_at: PROPOSED_754,
    blocking_count: 1,
    superseded_by_version: null,
    allowed_actions: ["decision.decide", "decision.request_analysis"],
  },
  question: "Recommend a §754 election for the 6/30/2025 transfer?",
  context: [
    {
      key: "work_item",
      label: "Work item",
      value: "2025 Form 1065 · Ridgeline Property Partners, LP",
      citation_id: null,
    },
    {
      key: "due",
      label: "Due",
      value: "Sep 15, 2026 · with the return (Reg. §1.754-1(b))",
      citation_id: null,
    },
  ],
  options: [
    {
      key: "elect_now",
      label: "Recommend electing now",
      detail:
        "Attach the §754 election statement to the TY2025 Form 1065 filed Sep 15 (no partner signature is required since the 2017 amendment of Reg. §1.754-1(b)); Owen Calder approves the election via the portal today. The partnership then records a 28,595 §743(b) adjustment for Pell Street II LLC, allocated to partnership property under §755.",
      figures: { step_up: "28595" },
      recommended: false,
    },
    {
      key: "file_without",
      label: "File without the election; decide in the cost segregation & §754 analysis",
      detail:
        "Basis shows the 28,595 as an explained outside/inside difference, with no §743(b) adjustment. A late election stays available under Reg. §301.9100-2 within 12 months of the extended due date (by Sep 15, 2027), after PRJ-01 models the Elm Street cost segregation.",
      figures: {},
      recommended: true,
    },
    {
      key: "against",
      label: "Recommend against the election",
      detail: "No §743(b) step-up for Pell Street II LLC; no ongoing basis-adjustment tracking.",
      figures: {},
      recommended: false,
    },
  ],
  factors: [],
  citation_ids: DECISION_754_CITATIONS.map((c) => c.id),
  note: null,
  recommendation: {
    suggestion_id: id("suggestion:754"),
    option_key: "file_without",
    reasons: [WHY],
  },
  blocking_refs: [{ type: "return_section", id: gateSubject("daniel-reyes", 8) }],
  decision: null,
  history: [
    {
      version_no: 1,
      event: "proposed",
      actor_kind: "agent",
      actor_user_id: null,
      actor_initials: null,
      at: PROPOSED_754,
      option_key: "file_without",
      changed: null,
      figures: {},
    },
  ],
};

/** b: Daniel decided option 2 at 9:36 AM CT; the card is decided, the gate done. */
export const DECIDED_AT = "2026-09-14T14:36:00Z";
export const card754Decided: DecisionCardOut = {
  ...card754,
  card: { ...card754.card, version_no: 2, status: "decided", allowed_actions: [] },
  // HOME-02b's footer, fixture-only until T-05 (DV-4).
  note: "Waiting on client: §754 decision sent to Owen Calder via the portal (POR-04).",
  decision: {
    id: id("decision:754"),
    option_key: "file_without",
    factors: [],
    rationale: "Decide in the cost segregation & §754 analysis once PRJ-01 has run.",
    seen_card_version: 1,
    decided_by_user_id: DANIEL,
    decided_by_name: "Daniel Reyes",
    decided_at: DECIDED_AT,
  },
  history: [
    ...card754.history,
    {
      version_no: 2,
      event: "decided",
      actor_kind: "human",
      actor_user_id: DANIEL,
      actor_initials: "DR",
      at: DECIDED_AT,
      option_key: "file_without",
      changed: null,
      figures: {},
    },
  ],
};

// ---- Sign-offs: Ridgeline 1065 sections at Partner (L4) (c, d) ---------------------------------

const HASH = `sha256:${"4c".repeat(32)}`;
const STATEMENT = "bh-tax-section-v1";

const signed = (
  target: SignOffTargetOut,
  level: SignOffOut["level"],
  who: string,
  name: string,
  initials: string,
  at: string,
): SignOffOut => ({
  id: id(`signoff:${target.target_id}:${level}`),
  target_type: target.target_type,
  target_id: target.target_id,
  kind: "ladder",
  level,
  signer_user_id: who,
  signer_name: name,
  initials,
  signed_at: at,
  content_hash: target.content_hash,
  version_no: target.version_no,
  statement_version: STATEMENT,
  adopted_run_id: null,
  adopted_run_number: null,
  stale: false,
});

const sectionLadder = (target: SignOffTargetOut): LadderLevelOut[] => [
  {
    level: "L1_preparer",
    required: true,
    expected_signer_user_id: OLIVIA,
    expected_signer_name: "Olivia Brandt",
    latest: signed(target, "L1_preparer", OLIVIA, "Olivia Brandt", "OB", "2026-09-10T21:00:00Z"),
  },
  {
    level: "L2_reviewer",
    required: true,
    expected_signer_user_id: SAMUEL,
    expected_signer_name: "Samuel Ito",
    latest: signed(target, "L2_reviewer", SAMUEL, "Samuel Ito", "SI", "2026-09-11T20:10:00Z"),
  },
  {
    level: "L3_manager",
    required: false,
    expected_signer_user_id: null,
    expected_signer_name: null,
    latest: null,
  },
  {
    level: "L4_partner",
    required: true,
    expected_signer_user_id: DANIEL,
    expected_signer_name: "Daniel Reyes",
    latest: null,
  },
];

const PASSING: EligibilityCheckOut[] = [
  { code: "open_review_notes", result: "pass", facts: { count: 0 }, refs: [] },
  { code: "segregation", result: "pass", facts: { preparer: "Olivia Brandt" }, refs: [] },
];

/** The M-2 fix Samuel Ito reviews (his gate 5); Capital Accounts waits on it. */
export const M2_FIX = gateSubject("samuel-ito", 5);

export interface SectionFrame {
  /** The gate's n in Daniel's queue. */
  n: number;
  ladder: SignOffLadderOut;
  eligibility: SignOffEligibilityOut;
}

function section(
  n: number,
  label: string,
  version: number,
  failing: EligibilityCheckOut | null,
): SectionFrame {
  const target: SignOffTargetOut = {
    target_type: "return_section",
    target_id: gateSubject("daniel-reyes", n),
    label,
    context_label: "Ridgeline 2025 Form 1065",
    version_no: version,
    content_hash: HASH,
    cell_count: 0,
    citation_count: 0,
  };
  const levels = sectionLadder(target);
  return {
    n,
    ladder: { target, levels, allowed_actions: ["sign_off.sign"] },
    eligibility: {
      target,
      level: "L4_partner",
      levels_allowed: ["L4_partner"],
      ladder: levels,
      checks: failing === null ? PASSING : [...PASSING, failing],
      eligible: failing === null,
      statement: {
        version: STATEMENT,
        text: "I reviewed this section. It is sufficient and appropriate, and its conclusions are supported.",
      },
    },
  };
}

/** c: the open M-2 proposal blocks Capital Accounts (identifier facts plus the fix's words). */
const M2_BLOCK: EligibilityCheckOut = {
  code: "open_issues",
  result: "fail",
  facts: {
    check: "M-2 ties",
    off: "6,200",
    fix: "add tax-exempt interest 6,200 as other increase",
    awaits: "Samuel Ito",
  },
  refs: [{ type: "agent_proposal", id: M2_FIX }],
};
/** Basis waits on decision 1 (gate G4 over the §754 card). */
const DECISION_BLOCK: EligibilityCheckOut = {
  code: "gate_g4",
  result: "fail",
  facts: { awaiting: "Daniel Reyes" },
  refs: [{ type: "decision_card", id: DECISION_754 }],
};

export const SECTIONS: readonly SectionFrame[] = [
  section(4, "Summary & preparer memo", 2, null),
  section(5, "Financials (TB → TTB)", 2, null),
  section(6, "Schedule K", 2, null),
  section(7, "Capital Accounts", 3, M2_BLOCK),
  section(8, "Basis", 2, DECISION_BLOCK),
  section(9, "States & PTET", 2, null),
];

// ---- g: Samuel Ito's agent outputs -------------------------------------------------------------

/** The Feld passive classification (Samuel's gate 6), as HOME-02g draws it. */
export const FELD_PROPOSAL = gateSubject("samuel-ito", 6);
export const feldProposal: AgentProposalOut = {
  ...k1,
  ref: FELD_PROPOSAL,
  title: "Classify the Ridgeline K-1 as passive on the Feld return?",
  context_label: "2025 Form 1040 · Jonah & Claire Feld",
  reasoning:
    "Prior-year treatment and the current K-1 support passive activity classification. The proposed change updates the return while preserving the existing treatment elsewhere.",
  proposed_at: "2026-09-14T14:18:00Z",
  evidence: [
    { evidence_version_id: id("evidence:k1"), label: "2025 Schedule K-1", citation_count: 2 },
  ],
  allowed_actions: ["proposal.approve", "proposal.reject"],
};

/** The Capital Accounts fix (Samuel's gate 5): the M-2 change c's "Open proposal" opens. */
export const m2Proposal: AgentProposalOut = {
  ...k1,
  ref: M2_FIX,
  title: "Capital Accounts fix — Ridgeline 2025 Form 1065",
  context_label: "2025 Form 1065 · Ridgeline Property Partners, LP",
  reasoning:
    "Add tax-exempt interest 6,200 (Schedule K, box 18A) as an other increase on Schedule M-2. The rollforward then ties to Schedule L at 6,866,200.",
  rows: [],
  totals: [],
  change_count: 1,
  evidence: [
    {
      evidence_version_id: id("evidence:schedule-k"),
      label: "2025 Schedule K · box 18A",
      citation_count: 1,
    },
  ],
  allowed_actions: ["proposal.approve", "proposal.reject"],
};

// ---- The gates' detail facts ------------------------------------------------------------------

/** What the owner's resolver adds to a row for the detail: reserved role, proposer, subject type,
 * level and actions. The queue rows stay seed/home.ts's; this only enriches them. */
export function withDetailFacts(persona: string, gates: readonly HumanGateOut[]): HumanGateOut[] {
  return gates.map((g, i) => {
    const n = i + 1;
    if (persona === "daniel-reyes" && n === 1) {
      return {
        ...g,
        overlay: "decision_card",
        proposed_by: { run_id: id("run:754"), initiator_user_id: OLIVIA, at: PROPOSED_754 },
        allowed_actions: ["human_gate.snooze", "human_gate.reassign"],
      };
    }
    if (g.kind === "sign_off_request" && persona === "daniel-reyes") {
      return {
        ...g,
        subject: { type: "return_section", id: g.subject.id },
        role: "L4_partner",
        bulk_eligible: !g.blocked,
      };
    }
    if (g.kind === "final_approval") {
      return { ...g, subject: { type: "tax_return", id: RIDGELINE_RETURN }, role: "L4_partner" };
    }
    if (g.kind === "proposal") {
      return {
        ...g,
        role: "L3_manager",
        proposed_by: {
          run_id: id(`run:${g.subject.id}`),
          initiator_user_id: n === 6 ? KEVIN : OLIVIA,
          at: "2026-09-14T14:18:00Z",
        },
        ...(n === 5
          ? { title: "Capital Accounts fix — Ridgeline 2025 Form 1065", context: "Agent output" }
          : {}),
        ...(n === 6
          ? {
              title: "Passive activity classification — Jonah & Claire Feld",
              context: "Agent output",
            }
          : {}),
      };
    }
    return g;
  });
}

/** The engagement team the detail names people from (the C1 roster read in fixture mode). */
export const DETAIL_TEAM: readonly TeamRosterMemberOut[] = [
  { user_id: DANIEL, display_name: "Daniel Reyes", role: "engagement_partner" },
  { user_id: SAMUEL, display_name: "Samuel Ito", role: "manager" },
  { user_id: OLIVIA, display_name: "Olivia Brandt", role: "senior" },
  { user_id: KEVIN, display_name: "Kevin Osei", role: "staff" },
];
