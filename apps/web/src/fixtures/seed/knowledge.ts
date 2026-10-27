// KNW-01's slice of the Brightwater Hale E0 seed (K-01-T04; KNW-01 handoff spec.md "CARDS",
// revision R2): the 48 catalog cards, the 2 review-queue rows and the 4 change-log entries,
// verbatim. A field the handoff does not give is null, never invented. Typed against the generated
// client (`KnowledgeItemOut`, `ReviewQueueItemOut`, `ChangeLogEntryOut`).
//
// Footings (knowledge.foot.test.ts): All 48 = Methodology 4 + Firm standards 12 + Templates 12 +
// Research & positions 6 + Agent instructions 14; Published 46 + Draft 1 + Superseded 1. The five
// categories added by R2 (Engagement templates, Frameworks, Skills, Notes, Content packs) have no
// provider at E0: no cards and no count.

import type { ChangeLogEntryOut, KnowledgeItemOut, ReviewQueueItemOut } from "@abacus/api-client";
import { stableId } from "./prng";

type Category = KnowledgeItemOut["category"];
type UsageKind = NonNullable<KnowledgeItemOut["usage_kind"]>;

interface Card {
  n: number;
  category: Category;
  title: string;
  version: string | null;
  status?: KnowledgeItemOut["status"];
  subtitle?: string;
  effective?: string;
  owner?: string;
  usage?: [number | null, UsageKind];
  /** The day it last changed, when the card shows it (the draft memo's "Sep 12, 2026"). */
  updated?: string;
}

const MO = "Margaret Okonkwo";
const DR = "Daniel Reyes";
const PR = "Priya Raman";
const SI = "Samuel Ito";
const JAN1 = "2026-01-01";
const JAN20 = "2026-01-20";

const CARDS: readonly Card[] = [
  // Methodology
  {
    n: 1,
    category: "methodology",
    title: "BH Audit Methodology · EBP",
    version: "v3",
    subtitle: "Programs, PBC template and report forms for employee benefit plan audits.",
    effective: JAN1,
    owner: MO,
    usage: [14, "engagements"],
  },
  {
    n: 2,
    category: "methodology",
    title: "BH Audit Methodology · FS",
    version: "v5",
    effective: JAN1,
    owner: MO,
    usage: [6, "engagements"],
  },
  {
    n: 3,
    category: "methodology",
    title: "BH SSARS Methodology · Review, Compilation & Preparation",
    version: "v2",
    effective: JAN1,
    owner: PR,
    usage: [7, "engagements"],
  },
  {
    n: 4,
    category: "methodology",
    title: "BH Audit Methodology · EBP",
    version: "v2",
    status: "superseded",
    subtitle: "Kept for engagements archived under it.",
  },
  // Firm standards
  {
    n: 5,
    category: "firm_standards",
    title: "1065 Review Checklist",
    version: "v4",
    subtitle: "42 checks",
    owner: DR,
    usage: [38, "returns"],
  },
  {
    n: 6,
    category: "firm_standards",
    title: "1040 Review Checklist",
    version: "v6",
    subtitle: "38 checks",
    effective: JAN20,
    owner: DR,
    usage: [162, "returns"],
  },
  {
    n: 7,
    category: "firm_standards",
    title: "BH AJE thresholds",
    version: "v2",
    subtitle: "Payroll accruals $15,000 · other classes $10,000 · attest clients always held",
    effective: JAN20,
    owner: PR,
    usage: [22, "closes"],
  },
  {
    n: 8,
    category: "firm_standards",
    title: "Materiality ranges",
    version: "v2",
    owner: MO,
    usage: [20, "audits"],
  },
  {
    n: 9,
    category: "firm_standards",
    title: "1120-S Review Checklist",
    version: "v3",
    usage: [12, "returns"],
  },
  {
    n: 10,
    category: "firm_standards",
    title: "1120 Review Checklist",
    version: "v2",
    usage: [5, "returns"],
  },
  {
    n: 11,
    category: "firm_standards",
    title: "1041 Review Checklist",
    version: "v2",
    usage: [6, "returns"],
  },
  {
    n: 12,
    category: "firm_standards",
    title: "990 Review Checklist",
    version: "v1",
    usage: [1, "returns"],
  },
  {
    n: 13,
    category: "firm_standards",
    title: "Variance thresholds",
    version: "v3",
    usage: [22, "closes"],
  },
  {
    n: 14,
    category: "firm_standards",
    title: "BH document confidence",
    version: "v1",
    subtitle: "Hold matches below 90% for staff",
  },
  { n: 15, category: "firm_standards", title: "Review levels by risk tier", version: "v2" },
  {
    n: 16,
    category: "firm_standards",
    title: "BH-TAX-02 Return approval",
    version: "v1",
    subtitle: "The signing partner gives final approval on returns he or she signs.",
  },
  // Templates
  {
    n: 17,
    category: "pbc_templates",
    title: "Engagement letter · EBP audit (§103(a)(3)(C))",
    version: "v4",
    owner: MO,
    usage: [14, "engagements"],
  },
  {
    n: 18,
    category: "pbc_templates",
    title: "Report · EBP §103(a)(3)(C) (AU-C 703)",
    version: "v3",
    usage: [14, "engagements"],
  },
  {
    n: 19,
    category: "pbc_templates",
    title: "PBC template · EBP (BH-EBP-110)",
    version: "v3",
    subtitle: "24 requests",
    usage: [14, "engagements"],
  },
  {
    n: 20,
    category: "pbc_templates",
    title: "Rep letter · EBP",
    version: "v3",
    usage: [14, "engagements"],
  },
  {
    n: 21,
    category: "pbc_templates",
    title: "AU-C 260 planning letter",
    version: "v2",
    usage: [20, "engagements"],
  },
  {
    n: 22,
    category: "pbc_templates",
    title: "Engagement letter · CAS monthly",
    version: "v3",
    usage: [22, "closes"],
  },
  {
    n: 23,
    category: "pbc_templates",
    title: "Close plan · Café with Square/Shopify",
    version: "v1",
    usage: [1, "closes"],
  },
  {
    n: 24,
    category: "pbc_templates",
    title: "Engagement letter · Individual & fiduciary",
    version: "v7",
  },
  {
    n: 25,
    category: "pbc_templates",
    title: "§7216 consent set · Use · AI disclosure",
    version: "v2",
  },
  { n: 26, category: "pbc_templates", title: "Binder · 1040 prior-year", version: "v5" },
  {
    n: 27,
    category: "pbc_templates",
    title: "Preparer memo outline · Entity returns",
    version: "v2",
    usage: [55, "returns"],
  },
  { n: 28, category: "pbc_templates", title: "Notice response · CP2000", version: "v2" },
  // Research & positions
  {
    n: 29,
    category: "research",
    title: "§754 election — Ridgeline transfer to Pell Street II LLC",
    version: "Research memo",
    status: "draft",
    owner: DR,
    updated: "2026-09-12",
  },
  {
    n: 30,
    category: "research",
    title: "PTET credits for nonresident partners (IL, CO, NY)",
    version: "Firm position",
  },
  {
    n: 31,
    category: "research",
    title: "De minimis safe harbor and repairs vs improvements ($2,500)",
    version: "Firm position",
    owner: PR,
  },
  {
    n: 32,
    category: "research",
    title: "§706(d) interim closing — monthly convention",
    version: "Firm position",
  },
  {
    n: 33,
    category: "research",
    title: "Schedule 1-A senior deduction",
    version: "Research memo",
    owner: SI,
  },
  {
    n: 34,
    category: "research",
    title: "Timeliness of participant contribution deposits (large plans)",
    version: "Research memo",
    owner: MO,
  },
  // Agent instructions (35–48), each "Used by: My Agents"
  ...(
    [
      ["Request Chaser", "v3"],
      ["Season Progress Reporter", "v2"],
      ["Notice Intake & Response Drafter", "v4"],
      ["Consent Expiry Watcher", "v1"],
      ["Bank Reconciliation", "v3"],
      ["Return Drafter", "v5"],
      ["Return Review Packet", "v3"],
      ["Flux Explainer", "v2"],
      ["Season Setup Planner", "v2"],
      ["K-1 Reconciliation Workpaper", "v2"],
      ["EBP Audit Workpapers", "v3"],
      ["Trial Balance Tie-Out", "v2"],
      ["Sample Selection & Item Requests", "v2"],
      ["Close Planner", "v1"],
    ] as const
  ).map(([title, version], i): Card => ({
    n: 35 + i,
    category: "agent_instructions",
    title,
    version,
    usage: [null, "agents"],
  })),
];

/** The default grid order of All (spec: "cards 1, 2, 3, 5, 6, 7, 17, 29, 31", then the roster). */
const LEAD: readonly number[] = [1, 2, 3, 5, 6, 7, 17, 29, 31];

export const knowledgeId = (n: number): string => stableId(`knowledge:card:${String(n)}`);

const ROUTE: Readonly<Record<Category, string>> = {
  methodology: "/knowledge/methodology",
  pbc_templates: "/knowledge/templates",
  firm_standards: "/knowledge/standards",
  research: "/knowledge/research",
  agent_instructions: "/workbench/agents",
  engagement_templates: "/knowledge/engagement-templates",
  frameworks: "/knowledge/frameworks",
  skills: "/knowledge/skills",
  notes: "/knowledge/notes",
  content_packs: "/knowledge/content-packs",
};

function toItem(card: Card): KnowledgeItemOut {
  const status = card.status ?? "published";
  const id = knowledgeId(card.n);
  return {
    id,
    category: card.category,
    title: card.title,
    subtitle: card.subtitle ?? null,
    status,
    version_label: card.version,
    effective_from: card.effective ?? null,
    owner_name: card.owner ?? null,
    usage_count: card.usage?.[0] ?? null,
    usage_kind: card.usage?.[1] ?? null,
    updated_at: `${card.updated ?? "2026-01-20"}T15:00:00Z`,
    match: [],
    route: `${ROUTE[card.category]}/${id}`,
  };
}

/** The 48 E0 cards in the default grid order. */
export function knowledgeItems(): KnowledgeItemOut[] {
  const ordered = [
    ...LEAD.map((n) => CARDS.find((c) => c.n === n)),
    ...CARDS.filter((c) => !LEAD.includes(c.n)),
  ].filter((c): c is Card => c !== undefined);
  return ordered.map(toItem);
}

/** A card's number, for order within a category. */
export function cardNumber(id: string): number {
  return CARDS.find((c) => knowledgeId(c.n) === id)?.n ?? 0;
}

/** Words a card is found by beyond its title (EBP v3's programs: planning materiality). */
export const KEYWORDS: Readonly<Record<string, readonly string[]>> = {
  [knowledgeId(1)]: ["Materiality"],
};

/** KNW-01c: the two drafts waiting for approval. */
export function reviewQueue(): ReviewQueueItemOut[] {
  return [
    {
      category: "firm_standards",
      object_id: stableId("knowledge:draft:1040-review-checklist-v7"),
      title: "1040 Review Checklist",
      version_label: "v7 (TY2026)",
      status: "draft",
      submitted_by_name: DR,
      submitted_at: "2026-09-10T15:00:00Z",
      flags_open: 0,
      route: `/knowledge/standards/${knowledgeId(6)}`,
    },
    {
      category: "research",
      object_id: knowledgeId(29),
      title: "§754 election — Ridgeline",
      version_label: "Research memo",
      status: "draft",
      submitted_by_name: DR,
      submitted_at: null,
      flags_open: 0,
      route: `/knowledge/research/${knowledgeId(29)}`,
    },
  ];
}

/** KNW-01d: what was approved and published, newest last. */
export function changeLog(): ChangeLogEntryOut[] {
  const actor = (name: string | null, kind: "human" | "system" = "human") => ({
    kind,
    user_id: name === null ? null : stableId(`user:${name.toLowerCase().replaceAll(" ", "-")}`),
    name,
    on_behalf_of_user_id: null,
  });
  return [
    {
      id: stableId("knowledge:change:1"),
      at: "2026-01-12T16:00:00Z",
      category: "methodology",
      object_id: knowledgeId(1),
      title: "BH Audit Methodology · EBP v3",
      kind: "approved",
      actor: actor(MO),
      facts: { effective_from: JAN1 },
    },
    {
      id: stableId("knowledge:change:2"),
      at: "2026-01-20T15:00:00Z",
      category: "firm_standards",
      object_id: knowledgeId(7),
      title: "BH AJE thresholds v2",
      kind: "published",
      actor: actor(PR),
      facts: {},
    },
    {
      id: stableId("knowledge:change:3"),
      at: "2026-01-20T16:00:00Z",
      category: "firm_standards",
      object_id: knowledgeId(6),
      title: "1040 Review Checklist v6",
      kind: "published",
      actor: actor(DR),
      facts: {},
    },
    {
      id: stableId("knowledge:change:4"),
      at: "2026-09-02T15:00:00Z",
      category: "agent_instructions",
      object_id: knowledgeId(35),
      // DF-32: the library agent's row reads "Request Chaser v3".
      title: "Request Chaser v3",
      kind: "published",
      actor: actor(null, "system"),
      facts: {},
    },
  ];
}

/** The categories with a provider at E0 (the CategoryList counts only these). */
export const E0_CATEGORIES: readonly Category[] = [
  "methodology",
  "firm_standards",
  "pbc_templates",
  "research",
  "agent_instructions",
];
