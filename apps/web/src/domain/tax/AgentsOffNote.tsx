// T-05-T66 (TASK-8073; T-05 §F13; SPEC-651 AC-13.1): the note a TXP screen shows where a
// model-backed control is not offered, with the server's reason in words ("Prepared without agents ·
// Accrued Agent is off for this firm. Prepare this by hand."). TXP-01's note, shared.
import type { JSX } from "react";
import { PREPARED_WITHOUT_AGENTS } from "./agents";

export function AgentsOffNote({
  capability,
  reason,
}: {
  capability: string;
  reason: string | null;
}): JSX.Element | null {
  if (reason === null) return null;
  return (
    <p role="note" data-agents-off={capability} className="text-meta text-ink-2">
      {PREPARED_WITHOUT_AGENTS} · {reason}
    </p>
  );
}
