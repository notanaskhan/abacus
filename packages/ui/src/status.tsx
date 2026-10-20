import type { JSX } from "react";
import type { Tone } from "./components/surfaces";
import { StatusPill } from "./components/workspace";

// The status vocabulary (TASK-101, the plan's §3.3.1): every state the product shows, with its
// word and tone, in one place, so the same state never reads two ways on two screens.

export interface StatusWord {
  label: string;
  tone: Tone;
}

export const STATUS = {
  // The plan's firm-side request words (S19 §3; TASK-105): asked, uploaded and waiting for the
  // team, screened and ready for a decision, or returned to the client. ("Received" means accepted
  // in the plan, so an upload is never called received.)
  request: {
    open: { label: "Requested", tone: "neutral" },
    received: { label: "Uploaded", tone: "warning" },
    ready_for_review: { label: "Ready for review", tone: "warning" },
    needs_revision: { label: "Returned", tone: "danger" },
    accepted: { label: "Received", tone: "success" },
  },
  engagement: {
    active: { label: "Active", tone: "success" },
    archived: { label: "Archived", tone: "neutral" },
  },
  workpaper: {
    not_started: { label: "Not started", tone: "neutral" },
    draft: { label: "Draft", tone: "warning" },
    ready: { label: "Prepared", tone: "warning" },
    reviewed: { label: "Reviewed", tone: "success" },
  },
  result: {
    supported: { label: "Supported", tone: "success" },
    exception: { label: "Exception", tone: "danger" },
    not_tested: { label: "Not tested", tone: "neutral" },
  },
  decision: {
    accept: { label: "Accepted", tone: "success" },
    reject: { label: "Sent back", tone: "warning" },
  },
} as const satisfies Record<string, Record<string, StatusWord>>;

export type StatusDomain = keyof typeof STATUS;

/** The word and tone for a state; an unknown state reads as itself, neutral. */
export function statusWord(domain: StatusDomain, value: string): StatusWord {
  const words: Record<string, StatusWord> = STATUS[domain];
  return words[value] ?? { label: value, tone: "neutral" };
}

/** A state as a pill. */
export function Status({ domain, value }: { domain: StatusDomain; value: string }): JSX.Element {
  const word = statusWord(domain, value);
  return <StatusPill tone={word.tone}>{word.label}</StatusPill>;
}
