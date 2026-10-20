import { STATUS, type Tone } from "@abacus/ui";

/** Item statuses as words and tones (never colour alone, SPEC-016): the design system's request
 * vocabulary (TASK-105). */
export const ITEM_STATUS: Record<string, { label: string; tone: Tone }> = STATUS.request;

export const SCREENING: Record<string, string> = {
  ready_for_review: "Ready for review",
  needs_revision: "Needs revision",
};

export function statusOf(status: string): { label: string; tone: Tone } {
  return ITEM_STATUS[status] ?? { label: status, tone: "neutral" };
}

/** A balance as the snapshot holds it, grouped and signed, without currency guessing. */
export function balance(value: string): string {
  const n = Number(value);
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : value;
}
