// WB-02 copy, verbatim from the handoff spec (W-02 §2.1). The suggested prompts are static product
// copy, never saved prompts (R2 revision: "suggested prompts stay distinct"; glossary "Suggested
// prompt", DEC-4602).
import type { SuggestedPrompt } from "@abacus/ui";

export const COPY = {
  title: "What should we work on?",
  body: "Ask in plain language. I read before I write, I ask when something could mean two things, and anything that changes a record waits for your approval.",
  newSession: "New session",
  contextLabel: "Context",
  firmWide: "Firm-wide · read-only",
  addContext: "+ Add context",
  pickerSearch: "Search clients, binders, workpapers",
  pickerFooter: "Only records you can open are listed.",
  selected: (n: number) => `${String(n)} selected`,
  add: "Add to session",
  composer: "Message",
  readOnlyLine: "Nothing was written.",
} as const;

export const SUGGESTED_PROMPTS: readonly SuggestedPrompt[] = [
  {
    id: "status-report",
    title: "Status report on open engagements",
    detail: "Find what needs attention across open work and prepare a report by office.",
  },
  {
    id: "tie-out",
    title: "Tie the trial balance to the ledger",
    detail:
      "Compare a client's trial balance with the ledger and source documents and show what doesn't tie.",
  },
  {
    id: "explain-change",
    title: "Explain a change from last period",
    detail: "Trace why a balance moved and point to the documents behind it.",
  },
  {
    id: "year-end-planning",
    title: "Year-end planning screen",
    detail: "Review 1040 clients for planning opportunities worth raising before December 31.",
  },
];
