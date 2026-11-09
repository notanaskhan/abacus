// The trace's words shared by the dock's run list and the drawer (split out so the dock loads
// the WB-09 drawer only when a trace opens: bundle budget, S32 partials end pass).
import type { AgentRunOut } from "@abacus/api-client";
import { count, ratio, type Tone } from "@abacus/ui";

// SPEC-318 (TASK-461): a run's state in the status words, never a confidence figure (I-12).
export const STATE: Record<AgentRunOut["state"], { label: string; tone: Tone }> = {
  queued: { label: "Queued", tone: "neutral" },
  running: { label: "Running", tone: "info" },
  succeeded: { label: "Finished", tone: "success" },
  needs_input: { label: "Needs a person", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
};
export const SUBJECT: Record<string, string> = {
  evidence_version: "An evidence version",
  inbox_file: "A file in the inbox",
  template_version: "A template version",
  task_scope: "Records in the run's scope",
};
/** Milliseconds as "850 ms", "4.2 s" or "3 min 5 s"; arithmetic only, no locale. */
export function duration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${count(ms)} ms`;
  if (ms < 60_000) return `${ratio(ms / 1000, 1)} s`;
  const s = Math.round(ms / 1000);
  return `${count(Math.floor(s / 60))} min ${count(s % 60)} s`;
}
