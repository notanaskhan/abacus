import { type JSX, useEffect, useRef, useState } from "react";
import { type Actor } from "../attribution/actor";
import { AgentFilledMarker, type Suggestion } from "../attribution/agent-filled";
import type { CitationView } from "../tracing/types";

// AgentFilledCell (F-08-T07; F-08 §3 A3; C-31 on T18d/T18e and TPL-20 a-c). The agent column's
// cell, on the C-31 marker:
// - suggested: ink-2 with the ink-3 atom 8 px from the right edge; the tooltip reads
//   "Suggested by Accrued Agent · <n> citations · not yet adopted" with Adopt (a HumanAction,
//   so only a named person sees it), Edit and Open row;
// - adopted: ink with the olive atom, only once the consumer's onAdopt resolves (P-35,
//   DEC-24: never optimistic); a pending or failed adopt leaves the cell suggested;
// - edited: keeps "Edited by <initials> · was <old>";
// - running: an empty cell shows the 10 px kit spinner while the run fills it.
// Citations are typed C4 views (INV-2): the kit numbers them and never reads "[n]" from text.

export type AgentCellState = "empty" | "suggested" | "adopted" | "edited";

export interface AgentFilledCellProps {
  value: string;
  state: AgentCellState;
  citations?: readonly CitationView[] | undefined;
  by?: Actor | undefined;
  at?: string | undefined;
  was?: string | undefined;
  exception?: boolean | undefined;
  /** The run is filling this cell (an empty cell only). */
  running?: boolean | undefined;
  viewer: Actor;
  onAdopt?: (() => Promise<void>) | undefined;
  onEdit?: (() => void) | undefined;
  onOpenRow?: (() => void) | undefined;
}

/** The marker's cited lines, from typed citation views only. */
export function citationLines(citations: readonly CitationView[] | undefined): string[] {
  return (citations ?? []).map((c) => `${c.title} · ${c.loc}`);
}

export function AgentFilledCell({
  value,
  state,
  citations,
  by,
  at,
  was,
  exception = false,
  running = false,
  viewer,
  onAdopt,
  onEdit,
  onOpenRow,
}: AgentFilledCellProps): JSX.Element {
  // Set only when onAdopt resolved; a new value or state from the consumer clears it.
  const [adoptedBy, setAdoptedBy] = useState<Actor | null>(null);
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);
  useEffect(() => {
    setAdoptedBy(null);
  }, [value, state]);

  const shown: AgentCellState = state === "suggested" && adoptedBy !== null ? "adopted" : state;
  const suggestion: Suggestion = {
    state: shown === "empty" && running ? "running" : shown,
    value,
    cites: citationLines(citations),
    ...(shown === "adopted" && adoptedBy !== null ? { by: adoptedBy } : by ? { by } : {}),
    ...(at === undefined ? {} : { at }),
    ...(was === undefined ? {} : { was }),
    ...(shown === "empty" && running ? { ask: "Agent column running" } : {}),
  };

  function adopt(): void {
    if (onAdopt === undefined) return;
    onAdopt().then(
      () => {
        if (live.current) setAdoptedBy(viewer);
      },
      () => {
        // A refused adopt leaves the value suggested; the consumer shows its own error.
      },
    );
  }

  return (
    <AgentFilledMarker
      suggestion={suggestion}
      viewer={viewer}
      onAdopt={adopt}
      {...(onEdit === undefined ? {} : { onEdit })}
      {...(onOpenRow === undefined ? {} : { onOpenRow })}
      exception={exception}
      width="full"
    />
  );
}
