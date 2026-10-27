// Copy shared by HOME-01 and HOME-02 (docs/screens/HOME-01.md, Copy), verbatim from the handoff
// spec and revision; marked where a string has no handoff source (undesigned, I-01 §5.5).

import type { GateBandsOut } from "@abacus/api-client";

type Band = keyof GateBandsOut;

const plural = (n: number, one: string, many: string): string =>
  `${String(n)} ${n === 1 ? one : many}`;

export const HOME_MESSAGES = {
  bands: {
    decisions: "Decisions",
    sign_offs: "Sign-offs",
    agent_outputs: "Agent outputs",
    approvals_sends: "Approvals & sends",
  } satisfies Record<Band, string>,
  summary: {
    decisions: (n: number) => plural(n, "decision", "decisions"),
    sign_offs: (n: number) => plural(n, "sign-off", "sign-offs"),
    agent_outputs: (n: number) => plural(n, "agent output", "agent outputs"),
    approvals_sends: (n: number) => plural(n, "approval & send", "approvals & sends"),
  } satisfies Record<Band, (n: number) => string>,
  sortedBy: "sorted by deadline",
  due: {
    /** "Sep 15 · 1 day" */
    inDays: (on: string, n: number) => `${on} · ${plural(n, "day", "days")}`,
    overdue: "Overdue",
  },
  /** Undesigned (I-01 §5.5): the Approvals badge's accessible name. */
  approvalsWaiting: (n: number) => `Approvals, ${String(n)} waiting`,
  /** Undesigned (I-01 §5.5): a blocked row's words, never colour alone. */
  blocked: "Blocked",
} as const;
