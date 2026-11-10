// P-10-T35 (SPEC-648 accessibility): run-state changes are announced politely; item arrivals are
// not (a streaming feed would talk over the person).
import type { JSX } from "react";

export function RunStateAnnouncer({ message }: { message: string }): JSX.Element {
  return (
    <div aria-live="polite" aria-atomic="true" data-agents="run-state-live" className="sr-only">
      {message}
    </div>
  );
}
