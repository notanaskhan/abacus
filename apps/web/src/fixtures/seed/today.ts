// I-02-T03 (TASK-7612; SPEC-654; docs/contracts/today.md): the Today brief's E0 fixtures on the
// stub's shapes, one per state that reads them: SHL-23 1 (Daniel), 2 (the Ridgeline drill-in),
// 3 (a question accepted), 4 (Margaret), 5 (Margaret, Tue Dec 1, Late · 1: a fixture until A-09),
// 6 (quiet day), 7 (building); HOME-05 a–f reuse them (a, b, c, e: Daniel; d: Margaret; f: the
// `by_engagement` layout). Words and figures are the handoff's (SHL-23 and HOME-05 spec.md, DF-25).
// Counts equal HOME-01's: Daniel 3 + 6 + 2 = 11, Margaret 2 + 0 + 2 = 4 (I-COUNT). Model prose
// appears only as verified `AgentBlocks` `p` parts on why lines and summaries (INV-2).
import type {
  SessionSnapshotOut,
  Card,
  CountCell,
  DrillVm,
  GateRow,
  Group,
  HistoryPage,
  TodayQuestionAcceptedOut,
  TodayVm,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const TODAY_CLOCK = "2026-09-14T09:24:00-05:00";
export const TODAY_DEC1_CLOCK = "2026-12-01T08:30:00-06:00";
const BUILT = "2026-09-14T14:24:00Z";

const p = (text: string) => [
  { version: 1, parts: [{ kind: "p", segments: [{ kind: "text", text }] }] },
];
const gate = (key: string) => stableId(`human-gate:${key}`);
const cell = (kind: CountCell["kind"], count: number): CountCell => ({
  kind,
  count,
  href: kind === "overdue" ? "/home/approvals?due=overdue" : `/home/approvals?band=${kind}`,
});
const due = (on: string, days: number, tone: "red_tint" | "amber" | "neutral" = "red_tint") => ({
  due_on: on,
  days,
  tone,
});

// --- Daniel Reyes, Mon Sep 14, 9:24 AM (SHL-23 1, HOME-05 a) -------------------------------------

const RIDGELINE_ENG = stableId("engagement:ridgeline-2025-1065");
const RIDGELINE_WI = stableId("work-item:ridgeline-2025-1065");

/** A seed row that must exist (the arrays are literal; a missing index is a seed bug). */
function row(rows: readonly GateRow[], i: number): GateRow {
  const found = rows[i];
  if (found === undefined) throw new Error(`seed row ${String(i)} is missing`);
  return found;
}

export const DANIEL_ROWS: GateRow[] = [
  {
    gate_id: gate("ridgeline-754"),
    kind: "decision",
    title: "§754 election — Ridgeline Property Partners, LP",
    due: due("2026-09-15", 1),
    state: null,
    deep_link: `/home/approvals?band=decision&ov=decision:${gate("ridgeline-754")}`,
    context_line: "Reserved to you, due with the return.",
    why_blocks: p(
      "Reserved to you, due with the return. I recommend filing without the election and deciding in the cost segregation & §754 analysis. Deciding also unblocks Basis.",
    ),
    folded: 1,
    highlight_refs: [gate("ridgeline-754")],
  },
  {
    gate_id: gate("ridgeline-capital-accounts"),
    kind: "sign_off",
    title: "Ridgeline 2025 Form 1065 · Capital Accounts",
    due: null,
    state: "blocked",
    deep_link: `/home/approvals?band=sign_off&select=${gate("ridgeline-capital-accounts")}`,
    context_line: "M-2 ties · off 6,200 · awaiting Samuel Ito",
    why_blocks: p(
      "M-2 ties · off 6,200. The fix (add tax-exempt interest 6,200 as other increase) is proposed and awaits Samuel Ito; your sign-off waits on it.",
    ),
    folded: 0,
    highlight_refs: [gate("ridgeline-capital-accounts")],
  },
  {
    gate_id: gate("ridgeline-final-approval"),
    kind: "approval_send",
    title: "Final approval & export — Ridgeline 2025 Form 1065 (BH-TAX-02)",
    due: due("2026-09-15", 1),
    state: null,
    deep_link: `/home/approvals?band=approval_send&ov=signoff:return:${RIDGELINE_WI}:final`,
    context_line: "Unlocks after the 6 sign-offs",
    why_blocks: p("Unlocks after the 6 sign-offs → export to CCH Axcess → release 5 K-1s."),
    folded: 0,
    highlight_refs: [gate("ridgeline-final-approval")],
  },
];

const DANIEL_GROUPS: Group[] = [
  {
    key: "high_risk",
    count: 1,
    items: [
      {
        ref_id: RIDGELINE_WI,
        title: "Ridgeline K-1 release — Sep 15",
        detail: "The Feld and Shah 1040s wait on the final K-1s.",
        detail_blocks: p("The Feld and Shah 1040s wait on the final K-1s."),
        pills: ["due_tomorrow", "blocked_on_decision"],
        deep_link: `/tax-returns/${RIDGELINE_WI}`,
        assignable: true,
      },
    ],
  },
  { key: "late", count: 0, summary: "Nothing is late." },
  {
    key: "due_tomorrow",
    count: 9,
    summary:
      "§754 decision · 6 Ridgeline sign-offs · final approval & export · Harborview 8879-PE",
  },
  {
    key: "ready_for_signoff",
    count: 4,
    summary: "Summary & preparer memo · Financials (TB → TTB) · Schedule K · States & PTET",
    href: "/home/approvals?band=sign_off&select=4,5,6,9",
  },
];

function danielCards(): Card[] {
  return [
    {
      engagement_id: RIDGELINE_ENG,
      work_item_id: RIDGELINE_WI,
      label: "Ridgeline Property Partners, LP · 2025 Form 1065",
      rows: DANIEL_ROWS,
      more: 5,
      briefing_id: stableId("daily-briefing:ridgeline:daniel:2026-09-14"),
      briefing_status: "ready",
    },
  ];
}

export function danielToday(): TodayVm {
  return {
    brief_date: "2026-09-14",
    brief_id: stableId("daily-briefing:user:daniel:2026-09-14"),
    first_name: "Daniel",
    items: 11,
    engagements: 4,
    cells: [
      cell("decision", 3),
      cell("sign_off", 6),
      cell("approval_send", 2),
      cell("overdue", 0),
    ],
    lead_facts: [
      {
        key: "lead.due_tomorrow",
        values: { due: 9, total: 11, date: "2026-09-15", top: 8, top_client: "Ridgeline" },
        refs: [],
      },
      {
        key: "lead.blocked_signoffs",
        values: {
          blocked: 2,
          total: 6,
          first: "Capital Accounts",
          first_cause: "the M-2 fix",
          second: "Basis",
          second_cause: "your §754 decision",
        },
        refs: [gate("ridgeline-capital-accounts"), gate("ridgeline-basis")],
      },
    ],
    layout: "focus",
    needs_you_first: DANIEL_ROWS,
    cards: danielCards(),
    groups: DANIEL_GROUPS,
    availability: { narrative: true, ask: true },
    status: "ready",
    needs_build: false,
    built_at: BUILT,
    building_counts: { items: 11, deadlines: 4, runs: 3 },
  };
}

/** The code fact paragraph SHL-23 1 must read (§3.2), for the frontend's copy test. */
export const DANIEL_PARAGRAPH =
  "9 of your 11 items are due tomorrow, Sep 15; 8 of them are Ridgeline. Two of the six sign-offs are blocked: Capital Accounts on the M-2 fix and Basis on your §754 decision.";

/** SHL-23 2 / HOME-05 b: the Ridgeline drill-in (title and to-do wording per HOME-05 b, DF-25). */
export function ridgelineDrill(): DrillVm {
  return {
    work_item_id: RIDGELINE_WI,
    title: "Ridgeline Property Partners, LP · 2025 Form 1065",
    summary_blocks: p(
      "The 5 K-1s release after your final approval tomorrow. Samuel Ito has reviewed four of the six sections; two still need work before you can sign them.",
    ),
    blockers: [
      {
        ...row(DANIEL_ROWS, 1),
        state: "fix_proposed",
        why_blocks: p(
          "M-2 off 6,200: tax-exempt interest belongs in capital as an other increase. Waiting on Samuel Ito.",
        ),
      },
      {
        gate_id: gate("ridgeline-basis"),
        kind: "sign_off",
        title: "Ridgeline 2025 Form 1065 · Basis",
        due: null,
        state: "blocked_on_decision",
        deep_link: `/home/approvals?band=sign_off&select=${gate("ridgeline-basis")}`,
        context_line: "Pell Street II off 28,595 · needs your §754 decision",
        why_blocks: p(
          "Pell Street II off 28,595 — §743(b) placeholder, needs your §754 decision.",
        ),
        folded: 0,
        highlight_refs: [gate("ridgeline-basis")],
      },
    ],
    downstream: [
      {
        work_item_id: stableId("work-item:feld-2025-1040"),
        title: "Feld 2025 Form 1040",
        state_line: "Draft K-1 · pre-release",
        deep_link: `/tax-returns/${stableId("work-item:feld-2025-1040")}`,
      },
      {
        work_item_id: stableId("work-item:shah-2025-1040"),
        title: "Shah 2025 Form 1040",
        state_line: "Preparing · Waiting on K-1",
        deep_link: `/tax-returns/${stableId("work-item:shah-2025-1040")}`,
      },
    ],
    prefills: [
      {
        gate_id: gate("ridgeline-capital-accounts"),
        assignee_user_id: stableId("user:samuel-ito"),
        assignee_name: "Samuel Ito",
        title: "Approve the M-2 fix — Ridgeline Capital Accounts",
        due_on: "2026-09-15",
        anchor_label: "Ridgeline 2025 Form 1065 · Capital Accounts",
        anchor_ref: `human_gate:${gate("ridgeline-capital-accounts")}`,
      },
    ],
    not_assignable: [{ gate_id: gate("ridgeline-basis"), reason: "reserved_to_you" }],
    open_href: `/tax-returns/${RIDGELINE_WI}/review`,
    select_refs: [gate("ridgeline-capital-accounts"), gate("ridgeline-basis")],
  };
}

/** SHL-23 3: the question is accepted; the answer is the Today session's items (W-02). */
export const QUESTION_ACCEPTED: TodayQuestionAcceptedOut = {
  session_id: stableId("session:today:daniel:2026-09-14"),
  item_id: stableId("session-item:today:daniel:q1"),
};

// --- Margaret Okonkwo, Mon Sep 14, 9:24 AM (SHL-23 4, HOME-05 d) --------------------------------

const NORTHWIND_ENG = stableId("engagement:northwind-401k-py2025");
const GRANITE_ENG = stableId("engagement:granite-peak-fy2026");

export const MARGARET_ROWS: GateRow[] = [
  {
    gate_id: gate("northwind-materiality"),
    kind: "decision",
    title: "Planning materiality — Northwind Robotics 401(k) Plan, PY2025",
    due: null,
    state: "blocked_on_decision",
    deep_link: `/home/approvals?band=decision&ov=decision:${gate("northwind-materiality")}`,
    context_line: "Blocking 3 workpapers",
    why_blocks: p(
      "v1 proposed on unadjusted net assets $16,812,400: 1.0% = $168,100 or 1.5% = $252,200 (I recommend 1.5%); blocking 3 workpapers",
    ),
    folded: 0,
    highlight_refs: [gate("northwind-materiality")],
  },
  {
    gate_id: gate("granite-materiality"),
    kind: "decision",
    title: "Planning materiality — Granite Peak Outdoor Supply, Inc., FY2026",
    due: null,
    state: "blocked_on_decision",
    deep_link: `/home/approvals?band=decision&ov=decision:${gate("granite-materiality")}`,
    context_line: "$155,000 proposed",
    why_blocks: p(
      "$155,000 proposed (5% of pre-tax income $3,100,000) · PM $116,250 · CT $7,750.",
    ),
    folded: 0,
    highlight_refs: [gate("granite-materiality")],
  },
  {
    gate_id: gate("granite-e14"),
    kind: "signature",
    title: "Countersign E14 — Granite Peak engagement letter",
    due: due("2026-09-16", 2),
    state: null,
    deep_link: `/home/approvals?band=signature&select=${gate("granite-e14")}`,
    context_line: "Luis Ferrante signed; your signature completes gate G3.",
    why_blocks: p("Luis Ferrante signed; your signature completes gate G3."),
    folded: 0,
    highlight_refs: [gate("granite-e14")],
  },
];

export function margaretToday(): TodayVm {
  return {
    brief_date: "2026-09-14",
    brief_id: stableId("daily-briefing:user:margaret:2026-09-14"),
    first_name: "Margaret",
    items: 4,
    engagements: 3,
    cells: [cell("decision", 2), cell("sign_off", 0), cell("signature", 2), cell("overdue", 0)],
    lead_facts: [
      {
        key: "lead.decisions_blocking",
        values: { decisions: 2, first: "Northwind", blocks: 3 },
        refs: [gate("northwind-materiality")],
      },
      { key: "lead.signatures_week", values: { signatures: 2 }, refs: [gate("granite-e14")] },
    ],
    layout: "focus",
    needs_you_first: MARGARET_ROWS,
    cards: [
      {
        engagement_id: NORTHWIND_ENG,
        label: "Northwind Robotics 401(k) Plan · PY2025",
        rows: [row(MARGARET_ROWS, 0)],
        briefing_status: "ready",
      },
      {
        engagement_id: GRANITE_ENG,
        label: "Granite Peak Outdoor Supply, Inc. · FY2026",
        rows: [row(MARGARET_ROWS, 1), row(MARGARET_ROWS, 2)],
        briefing_status: "ready",
      },
    ],
    groups: [
      { key: "late", count: 0, summary: "Nothing is late." },
      {
        key: "needs_attention",
        count: 2,
        items: [
          {
            ref_id: NORTHWIND_ENG,
            title: "Northwind Robotics 401(k) Plan",
            detail: "PBC 11 of 24 · report target Oct 9",
            pills: ["requests_open"],
          },
          {
            ref_id: stableId("engagement:fairhaven-401k"),
            title: "Fairhaven Foods 401(k)",
            detail:
              "Letter E11 unsigned, so G3 blocks requests · your countersignature due Sep 18",
            pills: ["letter_unsigned"],
          },
        ],
      },
      {
        key: "running",
        count: 1,
        items: [
          {
            ref_id: stableId("agent-run:4127"),
            title: "Northwind run #4127 dispatched 9:24 AM",
            actor: "Marcus Delaney",
            deep_link: `/engagements/${NORTHWIND_ENG}?ov=run-trace:${stableId("agent-run:4127")}`,
          },
        ],
      },
    ],
    availability: { narrative: true, ask: true },
    status: "ready",
    needs_build: false,
    built_at: BUILT,
  };
}

/** SHL-23 5 (fixture until A-09): Margaret on Tue Dec 1, 8:30 AM, Late · 1 at the top. */
export function margaretDec1(): TodayVm {
  const base = margaretToday();
  return {
    ...base,
    brief_date: "2026-12-01",
    brief_id: stableId("daily-briefing:user:margaret:2026-12-01"),
    groups: [
      {
        key: "late",
        count: 1,
        items: [
          {
            ref_id: stableId("component-deliverable:pruett-lang-interim-memo"),
            title: "Pruett & Lang interim memo — Harlow & Pike Distribution, Inc.",
            detail:
              "Due Nov 30 · component auditor Renee Pruett · Harlow & Pike FY2026 group audit",
            detail_blocks: p("I can draft a follow-up to Renee Pruett for you to send."),
            pills: ["overdue"],
            deep_link: "/audits/harlow-pike-fy2026/component-auditors",
          },
        ],
      },
      ...base.groups.filter((g) => g.key !== "late"),
    ],
    built_at: "2026-12-01T14:30:00Z",
  };
}

// --- Quiet day (SHL-23 6), building (SHL-23 7, HOME-05 e), by_engagement (HOME-05 f) ------------

export function quietToday(): TodayVm {
  return {
    brief_date: "2026-09-14",
    brief_id: stableId("daily-briefing:user:quiet:2026-09-14"),
    first_name: "Daniel",
    items: 0,
    engagements: 0,
    cells: [
      cell("decision", 0),
      cell("sign_off", 0),
      cell("approval_send", 0),
      cell("overdue", 0),
    ],
    lead_facts: [],
    layout: "focus",
    needs_you_first: [],
    cards: [],
    groups: [{ key: "late", count: 0, summary: "Nothing is late." }],
    availability: { narrative: true, ask: true },
    status: "ready",
    needs_build: false,
    built_at: BUILT,
  };
}

/** The first open of the day: no snapshot yet; the client asks for the missing builds. */
export function buildingToday(): TodayVm {
  return {
    ...danielToday(),
    brief_id: null,
    status: "building",
    needs_build: true,
    built_at: null,
    cards: danielCards().map((c) => ({ ...c, briefing_status: "building" as const })),
  };
}

/** HOME-05 f: one card per engagement briefing (the Q1 fallback), counts unchanged. */
export function byEngagementToday(): TodayVm {
  const labels = [
    "Ridgeline 2025 Form 1065",
    "Harborview Form 8879-PE",
    "Whitley CP2000",
    "Thornbury acceptance",
  ];
  return {
    ...danielToday(),
    layout: "by_engagement",
    needs_you_first: [],
    cards: labels.map((label) => ({
      engagement_id: stableId(`engagement:${label}`),
      label,
      rows: [],
      briefing_status: "ready" as const,
    })),
  };
}

export const HISTORY: HistoryPage = {
  items: [
    {
      brief_id: stableId("daily-briefing:user:daniel:2026-09-11"),
      brief_date: "2026-09-11",
      built_at: "2026-09-11T13:58:00Z",
      counts: { decision: 2, sign_off: 4, approval_send: 1, overdue: 0 },
    },
  ],
  next_cursor: null,
};

// --- I-02-T17 (SHL-23 3): the Today session at 9:26 AM, the question and its cited answer -------

const cite = (n: number) => stableId(`citation:today:daniel:q1:${String(n)}`);

/** SHL-23 3 verbatim: the person's bubble and the answer card with its three citation chips. */
export const TODAY_SESSION: SessionSnapshotOut = {
  id: QUESTION_ACCEPTED.session_id,
  title: "Today · Mon Sep 14",
  state: "live",
  origin: "manual",
  locked: false,
  allowed_actions: ["message"],
  last_item_at: "2026-09-14T14:26:20Z",
  items: [
    {
      id: QUESTION_ACCEPTED.item_id,
      seq: 2,
      kind: "user_message",
      actor_kind: "human",
      actor_name: "Daniel Reyes",
      created_at: "2026-09-14T14:26:00Z",
      payload: { v: 1, body: "What happens if Samuel doesn't approve the M-2 fix today?" },
    },
    {
      id: stableId("session-item:today:daniel:a1"),
      seq: 3,
      kind: "agent_blocks",
      actor_kind: "agent",
      actor_name: "Daniel Reyes",
      created_at: "2026-09-14T14:26:20Z",
      payload: {
        v: 1,
        turn_of: "2",
        blocks: {
          version: 1,
          parts: [
            {
              kind: "p",
              segments: [
                {
                  kind: "text",
                  text: "Capital Accounts stays blocked, so you can't give final approval, export or release the K-1s. The extension runs to Sep 15; a later 1065 is late and §6698 charges a penalty per partner per month. The Feld and Shah 1040s keep their draft K-1 holds; both are extended to Oct 15.",
                },
              ],
            },
            {
              kind: "cite_list",
              cites: [1, 2, 3].map((n) => ({ kind: "cite", citation_id: cite(n), n })),
            },
          ],
        },
        cites: {
          [cite(1)]: { n: 1, title: "Capital Accounts · Version 3", quote: "", loc: "Capital Accounts", match: null },
          [cite(2)]: { n: 2, title: "Form 7004 · filed Mar 12, 2026", quote: "", loc: "Form 7004", match: null },
          [cite(3)]: { n: 3, title: "Feld 1040 · extension", quote: "", loc: "Feld 1040", match: null },
        },
      },
    },
  ],
};
