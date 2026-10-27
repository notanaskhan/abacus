// The gate-class registry (I-01 §5.2; DF-25; docs/contracts/home-and-gates.md §4): band order, the
// glyph each class draws, and the summary rule. A new subkind needs no code here: its kind decides
// its band and glyph; the owner's resolver gives its title and context (I-01-T07). A row is a link
// to where the gate is decided, never a decision control (INV-1): nothing here names a gate verb.

import type { GateBandsOut, HumanGateOut } from "@abacus/api-client";
import type { IconName, PillVariant } from "@abacus/ui";
import { HOME_MESSAGES } from "./messages";

export type Band = keyof GateBandsOut;

/** Decisions · Sign-offs · Agent outputs · Approvals & sends: the fixed order (DF-25). */
export const BANDS: readonly Band[] = [
  "decisions",
  "sign_offs",
  "agent_outputs",
  "approvals_sends",
];

/** Bands always shown, even empty (the summary rule, AC1.2). */
const ALWAYS: ReadonlySet<Band> = new Set<Band>(["decisions", "sign_offs"]);

type Kind = HumanGateOut["kind"];

/** The glyph chip a class draws (HOME-01a): a question for a decision, a check for a sign-off. */
const GLYPH: Readonly<Record<Kind, IconName>> = {
  decision: "circle-help",
  sign_off_request: "circle-check",
  proposal: "sparkles",
  send: "send",
  final_approval: "circle-check",
  export: "circle-check",
  release: "circle-check",
  evidence_review: "file-search",
};

export function glyphOf(gate: Pick<HumanGateOut, "kind" | "blocked">): IconName {
  return gate.blocked ? "triangle-alert" : GLYPH[gate.kind];
}

/** "3 decisions · 6 sign-offs · 2 approvals & sends": Decisions and Sign-offs always, the others
 * when above zero (AC1.2). The words come from the one counts response. */
export function summaryParts(bands: GateBandsOut): string[] {
  return BANDS.filter((b) => ALWAYS.has(b) || bands[b] > 0).map((b) =>
    HOME_MESSAGES.summary[b](bands[b]),
  );
}

/** The bands to draw: Decisions and Sign-offs whenever there is anything, the rest when held. */
export function visibleBands(bands: GateBandsOut): Band[] {
  return BANDS.filter((b) => ALWAYS.has(b) || bands[b] > 0);
}

const MS_PER_DAY = 86_400_000;

function daysBetween(today: string, due: string): number {
  return Math.round(
    (Date.parse(`${due}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / MS_PER_DAY,
  );
}

export type DueRisk = "overdue" | "due_soon" | "approaching" | "later";

/** The due-risk tier (status vocabulary `due_risk`): overdue, 0 to 7 days, 8 to 14, beyond. */
export function dueRisk(today: string, due: string): DueRisk {
  const n = daysBetween(today, due);
  if (n < 0) return "overdue";
  if (n <= 7) return "due_soon";
  if (n <= 14) return "approaching";
  return "later";
}

const RISK_VARIANT: Readonly<Record<DueRisk, PillVariant>> = {
  overdue: "red-tint",
  due_soon: "red-tint",
  approaching: "amber",
  later: "neutral",
};

/** The due chip: "Sep 15 · 1 day" (words carry the tier, never colour alone). */
export function dueChip(
  today: string,
  due: string,
  formatDate: (iso: string) => string,
): { label: string; variant: PillVariant; risk: DueRisk } {
  const risk = dueRisk(today, due);
  const n = daysBetween(today, due);
  const on = formatDate(due);
  const label =
    risk === "overdue"
      ? HOME_MESSAGES.due.overdue
      : risk === "later"
        ? on
        : HOME_MESSAGES.due.inDays(on, n);
  return { label, variant: RISK_VARIANT[risk], risk };
}
