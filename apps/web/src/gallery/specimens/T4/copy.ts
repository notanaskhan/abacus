// T4 template artboards' own words (handoff T4a, T4f), verbatim. The TPL-04 specimen's words are
// the seed's (fixtures/seed/tpl04-sessions.ts).
import type { AgentFact, AgentRecentRun, SuggestedPrompt } from "@abacus/ui";

export const COPY = {
  agentsTitle: "My Agents",
  intentLog: "Action log",
} as const;

/** T4a's four suggested prompts. */
export const T4A_PROMPTS: readonly SuggestedPrompt[] = [
  {
    id: "t4a-1",
    title: "Which TY2025 returns are still in review?",
    detail: "Grouped by reviewer, oldest first",
  },
  {
    id: "t4a-2",
    title: "What’s still missing from Northwind’s PBC list?",
    detail: "Open requests by owner",
  },
  {
    id: "t4a-3",
    title: "Summarize the Copperleaf August close",
    detail: "Progress, open issues and what’s late",
  },
  {
    id: "t4a-4",
    title: "Which notices need a response this week?",
    detail: "Response dates across all clients",
  },
];

/** T4f · WB-06: the agent list and the SOC 1 Coverage Check detail. */
export const T4F_AGENTS: readonly {
  id: string;
  name: string;
  meta: string;
  dot?: "amber" | "spin";
}[] = [
  { id: "soc1", name: "SOC 1 Coverage Check", meta: "Audit · Today 9:00 AM", dot: "amber" },
  { id: "ebp", name: "EBP Audit Workpapers", meta: "Audit · Today 9:24 AM", dot: "spin" },
  { id: "chaser", name: "Missing Document Chaser", meta: "Client service · Sep 11" },
  { id: "k1", name: "K-1 Reconciliation", meta: "Tax preparation · Sep 10" },
  { id: "ext", name: "Extension Tracker", meta: "Tax preparation · Today 7:00 AM" },
  { id: "elr", name: "Engagement Letter Renewals", meta: "Operations · Sep 1" },
];

export const T4F_DETAIL = {
  name: "SOC 1 Coverage Check",
  provenance: "Published by Accrued",
  purpose:
    "Check that each service organization’s SOC 1 report and bridge letter cover the full plan year.",
  meta: "Audit · Installed Aug 3 by Grace Holloway",
  facts: [
    { label: "Schedule", value: "Weekdays at 9:00 AM, on audits in Planning or Fieldwork" },
    {
      label: "Reads",
      value: "SOC 1 reports, bridge letters and the Service Organizations workpaper",
    },
    {
      label: "Changes",
      value: "Raises an issue only after a manager answers. It never edits a workpaper",
    },
    { label: "Asks", value: "The engagement manager, when coverage has a gap" },
  ] satisfies AgentFact[],
  runs: [
    {
      id: "run-1",
      title: "Northwind Robotics 401(k) Plan",
      meta: "Today 9:00 AM · Waiting on Hannah Leclerc",
      state: "waiting",
    },
    {
      id: "run-2",
      title: "Northwind Robotics 401(k) Plan",
      meta: "Sep 11 · Paycrest bridge letter still outstanding",
      state: "done",
    },
    {
      id: "run-3",
      title: "Northwind Robotics 401(k) Plan",
      meta: "Sep 10 · Harborline bridge letter received",
      state: "done",
    },
  ] satisfies AgentRecentRun[],
};
