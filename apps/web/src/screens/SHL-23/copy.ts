// SHL-23 · Today brief panel words (I-02-T15; handoff SHL-23 spec.md; docs/screens/SHL-23.md).
// Verbatim from the handoff; the fact paragraph is code (DEC-4608): sentences over registered
// facts, never a model's.

export const COPY = {
  title: "Today",
  greeting: (first: string) => `Good morning, ${first}`,
  line: (items: number, engagements: number) =>
    `${String(items)} item${items === 1 ? "" : "s"} · ${String(engagements)} engagement${engagements === 1 ? "" : "s"}`,
  history: "History",
  more: "More",
  rebuild: "Rebuild brief",
  needsYouFirst: "Needs you first",
  nothingFirst: "Nothing needs you first.",
  quietBody: "I'll add items here as decisions, sign-offs and deadlines reach you.",
  ask: "Ask about your day…",
  building: (n: number, d: number, r: number) =>
    `Building your brief from ${String(n)} items, ${String(d)} deadlines and ${String(r)} runs…`,
  footer: (time: string) =>
    `Brief built ${time} from your queue, deadlines and runs · every line links to its source`,
  // I-02 staleness: a ready brief whose why lines name gates closed since.
  changedSince: (time: string) => `Written ${time} · items changed since`,
  open: "Open",
  assign: "Assign open items",
  summaryUnavailable: "Summary unavailable",
  aiUnavailable: "AI isn't available for real client data yet",
  consentOff: "Agents are off for this taxpayer — §7216 consent isn't on file",
  metadataOnly: "You can see this engagement's items, not its details.",
  budget: "The firm's AI budget for today is used up.",
  nothingLate: "Nothing is late.",
  more_rows: (n: number) => `+${String(n)} more`,
  // I-02-T17 (SHL-23 2, 3; HOME-05 b): drill-in, assign, history and ask.
  back: "Today",
  waitingDownstream: "Waiting downstream",
  openReturn: "Open return",
  reservedToYou: "Reserved to you — not assignable",
  newTodo: "New to-do",
  assignee: "Assignee",
  due: "Due",
  create: "Create",
  skip: "Skip",
  cancel: "Cancel",
  assignOf: (n: number, of: number) => `${String(n)} of ${String(of)}`,
  historyTitle: "Earlier briefs",
  noHistory: "No earlier briefs yet.",
  pastBrief: (day: string) => `Brief for ${day} · read only`,
  thinking: "Accrued Agent is answering…",
  readOnly: "I can't approve, sign off or send from Today. Those stay with you on their own screens.",
  openSignOff: "Open sign-off",
  askFailed: "I couldn't answer that just now.",
} as const;

export const CELL_LABELS: Readonly<Record<string, string>> = {
  decision: "Decisions",
  sign_off: "Sign-offs",
  approval_send: "Approvals & sends",
  signature: "Signatures",
  needs_attention: "Needs attention",
  overdue: "Overdue",
};

export const GROUP_LABELS: Readonly<Record<string, string>> = {
  high_risk: "High risk",
  late: "Late",
  due_tomorrow: "Due tomorrow",
  ready_for_signoff: "Ready for sign-off",
  needs_attention: "Needs attention",
  running: "Running",
};

export const REASON_COPY: Readonly<Record<string, string>> = {
  boundary_refused: COPY.aiUnavailable,
  not_synthetic: COPY.aiUnavailable,
  consent_7216: COPY.consentOff,
  metadata_only: COPY.metadataOnly,
  budget_soft_limit: COPY.budget,
  flag_off: COPY.aiUnavailable,
};

const WORDS = [
  "Zero",
  "One",
  "Two",
  "Three",
  "Four",
  "Five",
  "Six",
  "Seven",
  "Eight",
  "Nine",
  "Ten",
];

/** A small count as a word for a sentence start or middle ("Two of the six"). */
export function word(n: number, lower = false): string {
  const w = WORDS[n] ?? String(n);
  return lower && n < WORDS.length ? w.toLowerCase() : w;
}

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/** "Sep 15" from an ISO date (a calendar day: no time zone, no Date). */
function monthDay(iso: string): string {
  const [, m, d] = iso.split("-").map((x) => Number(x));
  return `${MONTHS[(m ?? 1) - 1] ?? ""} ${String(d ?? 1)}`;
}

type Values = Readonly<Record<string, unknown>>;
const num = (v: Values, k: string): number => (typeof v[k] === "number" ? v[k] : 0);
const str = (v: Values, k: string): string => (typeof v[k] === "string" ? v[k] : "");

/** One registered lead fact as its code sentence; an unknown key or a zero count says nothing. */
export function leadSentence(key: string, values: Values): string | null {
  switch (key) {
    case "lead.due_tomorrow": {
      const due = num(values, "due");
      if (due === 0) return null;
      const top = num(values, "top");
      const client = str(values, "top_client");
      const head = `${String(due)} of your ${String(num(values, "total"))} items are due tomorrow, ${monthDay(str(values, "date"))}`;
      return top > 0 && client !== ""
        ? `${head}; ${String(top)} of them are ${client}.`
        : `${head}.`;
    }
    case "lead.blocked_signoffs": {
      const blocked = num(values, "blocked") || num(values, "count");
      if (blocked === 0) return null;
      const total = num(values, "total");
      const first = str(values, "first");
      const second = str(values, "second");
      const lead =
        total > 0
          ? `${word(blocked)} of the ${word(total, true)} sign-offs are blocked`
          : `${word(blocked)} sign-off${blocked === 1 ? " is" : "s are"} blocked`;
      if (first === "") return `${lead}.`;
      const parts = [`${first} on ${str(values, "first_cause")}`];
      if (second !== "") parts.push(`${second} on ${str(values, "second_cause")}`);
      return `${lead}: ${parts.join(" and ")}.`;
    }
    case "lead.overdue": {
      const n = num(values, "count");
      return n === 0 ? null : `${word(n)} item${n === 1 ? " is" : "s are"} overdue.`;
    }
    case "lead.decisions_blocking": {
      const n = num(values, "count");
      return n === 0 ? null : `${word(n)} decision${n === 1 ? " blocks" : "s block"} other work.`;
    }
    default:
      return null;
  }
}
