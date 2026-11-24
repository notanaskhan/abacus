/** The status disc vocabulary (C-06): no registry import, so the States kit and the disc stay
 * out of the status registry's chunk (S53 end pass). `status.ts` re-exports all of it. */

export type DiscState =
  "done" | "prepared" | "todo" | "half" | "run" | "warn" | "fail" | "off" | "wait";
/** The disc sizes: 13 in issue rows, 15 in rows and rails, 17 in task rows (C-06), and 16 for the
 * inbox's "new" and "waiting" rows, which the blueprint draws at 16. */
export type DiscSize = 13 | 15 | 16 | 17;

export const DISC_STATES: readonly DiscState[] = [
  "done",
  "prepared",
  "todo",
  "half",
  "run",
  "warn",
  "fail",
  "off",
  "wait",
];

/** The accessible name of each disc (C-06). */
export const DISC_LABEL: Record<DiscState, string> = {
  done: "Done",
  prepared: "Prepared",
  todo: "To do",
  half: "In progress",
  run: "Running",
  warn: "Warning",
  fail: "Failed",
  off: "Skipped",
  wait: "Waiting",
};
