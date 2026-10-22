import { type JSX, useId, useState } from "react";
import { cn } from "../cn";
import { Spinner } from "../components/motion";
import { Icon } from "../icons";
import { type Actor, AGENT_NAME, formatActor, isPerson } from "./actor";
import { HumanAction } from "./human-action";

// AgentFilledMarker (F-05-T30; C-31): a value the Accrued Agent filled in. Until a named person
// adopts it, it reads ink-2 with the atom glyph in ink-3; adopted, it reads ink with an olive
// atom (colour and glyph both change, so the state survives greyscale); edited, an amber dot.
// The agent never adopts: `adoptSuggestion` refuses it, and Adopt is a HumanAction.

export type FilledState = "suggested" | "adopted" | "edited" | "running" | "input" | "empty";

export interface Suggestion {
  state: FilledState;
  value: string;
  /** Who adopted or edited it. */
  by?: Actor;
  /** When, already formatted ("Oct 1"). */
  at?: string;
  /** The agent's value before an edit. */
  was?: string;
  /** Cited sources, each already formatted ("Invoice FRF-30418 · Jun 29, 2026"). */
  cites?: readonly string[];
  /** For `input` and `running`: the question or the run's label. */
  ask?: string;
}

/** A named person adopts the agent's value (C-31). The agent, a policy or the system cannot. */
export function adoptSuggestion(s: Suggestion, by: Actor, at: string): Suggestion {
  if (!isPerson(by)) throw new Error(`${formatActor(by)} cannot adopt a suggestion`);
  return { ...s, state: "adopted", by, at };
}

/** A different value is an edit (kept on rerun); picking the agent's value back re-adopts it. */
export function editSuggestion(s: Suggestion, value: string, by: Actor, at: string): Suggestion {
  if (!isPerson(by)) throw new Error(`${formatActor(by)} cannot edit a suggestion`);
  if (value === s.value) return s;
  const was = s.state === "edited" && s.was !== undefined ? s.was : s.value;
  if (value === was)
    return { state: "adopted", value, by, at, ...(s.cites ? { cites: s.cites } : {}) };
  return { ...s, state: "edited", value, was, by, at };
}

/** The tooltip's two lines (C-31). */
export function suggestionLines(s: Suggestion): { head: string; line: string } {
  const n = s.cites?.length ?? 0;
  const cited = `${String(n)} citation${n === 1 ? "" : "s"}`;
  const head =
    s.state === "suggested"
      ? `Suggested by ${AGENT_NAME} · ${cited} · not yet adopted`
      : s.state === "adopted"
        ? `Suggested by ${AGENT_NAME} · ${cited}`
        : "";
  const by = s.by === undefined ? "" : formatActor(s.by);
  const line =
    s.state === "adopted"
      ? `Adopted by ${by}${s.at === undefined ? "" : ` · ${s.at}`}`
      : s.state === "edited"
        ? `Edited by ${by}${s.was === undefined ? "" : ` · was ${s.was}`}`
        : s.state === "input" || s.state === "running"
          ? (s.ask ?? "")
          : "";
  return { head, line };
}

const VALUE_INK: Record<FilledState, string> = {
  suggested: "text-ink-2",
  adopted: "text-ink",
  edited: "text-ink",
  // C-31 draws these ink-4; the AA ladder (DEC-11) makes them ink-3, as the status kit's `soon`.
  running: "text-ink-3",
  input: "text-amber-ink",
  empty: "text-ink-3",
};

const FIXED_TEXT: Partial<Record<FilledState, string>> = {
  running: "Running…",
  input: "Needs input",
  empty: "—",
};

export interface AgentFilledMarkerProps {
  suggestion: Suggestion;
  /** The signed-in person: Adopt renders only for a named person. */
  viewer: Actor;
  onAdopt?: () => void;
  onEdit?: () => void;
  onOpenRow?: () => void;
  /** An exception value carries the red flag (C-31: "Improperly excluded"). */
  exception?: boolean;
  width?: number | "full";
  /** Hold the tooltip open (specimens). */
  open?: boolean;
  className?: string;
}

/** The C-31 cell: the value, the atom (or spinner) and, on hover or focus, the tooltip. */
export function AgentFilledMarker({
  suggestion: s,
  viewer,
  onAdopt,
  onEdit,
  onOpenRow,
  exception = false,
  width = 220,
  open: forced,
  className,
}: AgentFilledMarkerProps): JSX.Element {
  const [hover, setHover] = useState(false);
  const tipId = useId();
  const open = forced ?? hover;
  const text = FIXED_TEXT[s.state] ?? s.value;
  const { head, line } = suggestionLines(s);
  const hasTip = s.state !== "empty";
  const flagged =
    exception && (s.state === "suggested" || s.state === "adopted" || s.state === "edited");
  return (
    <span
      className={cn("relative inline-block align-middle", className)}
      style={{ width: width === "full" ? "100%" : width }}
      onMouseEnter={() => {
        setHover(true);
      }}
      onMouseLeave={() => {
        setHover(false);
      }}
      onFocus={() => {
        setHover(true);
      }}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setHover(false);
      }}
    >
      <span
        data-actor={s.state === "suggested" ? "agent" : undefined}
        data-filled={s.state}
        tabIndex={hasTip ? 0 : undefined}
        aria-describedby={hasTip && open ? tipId : undefined}
        className={cn(
          "relative flex min-h-[34px] items-center gap-[5px] rounded-tile py-[6px] pr-[26px] pl-[10px] text-cell",
          VALUE_INK[s.state],
        )}
      >
        <span className="truncate whitespace-nowrap">{text}</span>
        {flagged && (
          <Icon
            name="flag"
            size={12}
            className="size-[11px] shrink-0 text-red"
            label="Exception"
          />
        )}
        <span className="absolute top-1/2 right-[8px] -translate-y-1/2">
          {s.state === "running" ? (
            <Spinner label="Running" size={10} showLabel={false} />
          ) : s.state === "empty" ? null : (
            <span className="relative block">
              <Icon
                name="atom"
                size={12}
                className={cn("size-[11px]", s.state === "adopted" ? "text-green" : "text-ink-3")}
                label={s.state === "adopted" ? "Adopted agent value" : "Agent value"}
              />
              {s.state === "edited" && (
                <span
                  aria-hidden="true"
                  className="absolute -top-[2px] -right-[2px] size-[4px] rounded-pill bg-amber ring-1 ring-card"
                />
              )}
            </span>
          )}
        </span>
      </span>
      {hasTip && open && (
        <span
          id={tipId}
          role="tooltip"
          className="absolute top-full left-0 z-(--z-pop) mt-[4px] flex w-[260px] flex-col gap-[7px] rounded-tile bg-card px-[10px] py-[8px] text-meta text-ink shadow-e3"
        >
          {head !== "" && (
            <span className="text-ink-2">
              {head}
              {s.cites?.map((c, i) => (
                <span
                  key={c}
                  title={c}
                  className="ml-[3px] inline-flex h-[17px] items-center rounded-pill bg-nested px-[5px] text-micro font-medium text-ink-2 inset-ring-[0.5px] inset-ring-hair"
                >
                  {i + 1}
                </span>
              ))}
            </span>
          )}
          {line !== "" && <span>{line}</span>}
          <span className="flex gap-[4px]">
            {s.state === "suggested" && (
              <HumanAction
                verb="Adopt"
                actor={viewer}
                size="xs"
                variant="secondary"
                onClick={onAdopt}
              />
            )}
            {(s.state === "suggested" || s.state === "adopted" || s.state === "edited") &&
              isPerson(viewer) && (
                <button
                  type="button"
                  onClick={onEdit}
                  className="h-[23px] rounded-pill px-[9px] text-meta font-medium text-ink-2 hover:bg-nested"
                >
                  Edit
                </button>
              )}
            {s.state !== "running" && (
              <button
                type="button"
                onClick={onOpenRow}
                className="h-[23px] rounded-pill px-[9px] text-meta font-medium text-ink-2 hover:bg-nested"
              >
                Open row
              </button>
            )}
            {s.state === "running" && (
              <button
                type="button"
                onClick={onOpenRow}
                className="h-[23px] rounded-pill px-[9px] text-meta font-medium text-ink-2 hover:bg-nested"
              >
                Open run
              </button>
            )}
          </span>
        </span>
      )}
    </span>
  );
}
