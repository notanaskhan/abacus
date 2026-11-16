import {
  AgentFilledMarker,
  type Actor,
  Button,
  IconButton,
  Label,
  Picker,
  SheetModal,
  type Suggestion,
} from "@abacus/ui";
import { type JSX, useId, useState } from "react";
import { FIELDWORK_COPY } from "./copy";

// ExpandTestingSheet (A-08-T26; AUD-12 revision f to h; AUD-36 and ATT-05 pattern): O3 500. The
// person picks how many to add by score and unpredictably (or participants, for a test of
// details), writes the rationale (the agent may draft it, shown with the C-31 marker), names the
// approver, and requests approval. Nothing expands until the approver decides (A-08-T17), and the
// agent never sends the request (ADR-005). The "becomes" line is a count of items, not a figure.

const C = FIELDWORK_COPY.expand;

export interface ExpandTestingSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  base: number;
  /** `participants` for a test of details (state h): one stepper. */
  mode?: "entries" | "participants";
  approvers: readonly { id: string; name: string }[];
  /** The agent's draft rationale, when there is one (C-31). */
  draft?: Suggestion | undefined;
  viewer: Actor;
  onRequest?: (request: {
    addByScore: number;
    addUnpredictable: number;
    rationale: string;
    approverId: string;
  }) => void;
  /** Hold the sheet open in place (gallery). */
  held?: boolean;
}

function Stepper({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (next: number) => void;
}): JSX.Element {
  const id = useId();
  return (
    <div className="flex h-[36px] items-center gap-[10px]">
      <Label htmlFor={id} className="flex-1 text-cell">
        {label}
      </Label>
      <IconButton
        icon="minus"
        label={`${C.less}: ${label}`}
        disabled={value <= 0}
        onClick={() => {
          onChange(value - 1);
        }}
      />
      <output id={id} aria-live="polite" className="w-[32px] text-center tabular-nums">
        {value}
      </output>
      <IconButton
        icon="plus"
        label={`${C.more}: ${label}`}
        disabled={value >= 500}
        onClick={() => {
          onChange(value + 1);
        }}
      />
    </div>
  );
}

export function ExpandTestingSheet(p: ExpandTestingSheetProps): JSX.Element {
  const [byScore, setByScore] = useState(10);
  const [unpredictable, setUnpredictable] = useState(0);
  // The agent's draft is the person's only once they adopt it (C-31): the field starts empty.
  const [rationale, setRationale] = useState("");
  const [approver, setApprover] = useState(p.approvers[0]?.id ?? "");
  const rationaleId = useId();
  const approverId = useId();
  const participants = p.mode === "participants";
  const adds = byScore + (participants ? 0 : unpredictable);
  const ready = rationale.trim().length > 0 && approver !== "" && adds > 0;
  return (
    <SheetModal
      open={p.open}
      onOpenChange={p.onOpenChange}
      title={C.title}
      dirty={rationale !== ""}
      {...(p.held === true ? { forceState: "open" as const, heldRole: "group" as const } : {})}
      action={
        <Button
          variant="primary"
          disabled={!ready}
          onClick={() => {
            p.onRequest?.({
              addByScore: byScore,
              addUnpredictable: participants ? 0 : unpredictable,
              rationale: rationale.trim(),
              approverId: approver,
            });
          }}
        >
          {C.request}
        </Button>
      }
    >
      <div data-fieldwork="expand" className="flex flex-col gap-[10px] p-[16px]">
        <Stepper
          label={participants ? C.participants : C.byScore}
          value={byScore}
          onChange={setByScore}
        />
        {!participants && (
          <Stepper label={C.unpredictable} value={unpredictable} onChange={setUnpredictable} />
        )}
        <p data-fieldwork="becomes" className="text-[12.5px] text-ink-2">
          {C.becomes(p.base + adds)}
        </p>
        <div className="flex flex-col gap-[6px]">
          <Label htmlFor={rationaleId}>{C.rationaleLabel}</Label>
          {p.draft !== undefined && (
            <AgentFilledMarker
              suggestion={p.draft}
              viewer={p.viewer}
              width="full"
              onAdopt={() => {
                setRationale(p.draft?.value ?? "");
              }}
            />
          )}
          <textarea
            id={rationaleId}
            required
            aria-describedby={`${rationaleId}-help`}
            value={rationale}
            onChange={(event) => {
              setRationale(event.target.value);
            }}
            maxLength={2000}
            className="min-h-[88px] rounded-input bg-card p-[8px] text-cell inset-ring-[0.5px] inset-ring-stroke"
          />
          <p id={`${rationaleId}-help`} className="text-[11.5px] text-ink-3">
            {C.rationaleHelp}
          </p>
        </div>
        <div className="flex flex-col gap-[6px]">
          <Label htmlFor={approverId}>{C.approver}</Label>
          <span id={approverId}>
            <Picker
              label={C.approver}
              options={p.approvers.map((a) => ({ value: a.id, label: a.name }))}
              value={approver}
              onChange={setApprover}
            />
          </span>
        </div>
      </div>
    </SheetModal>
  );
}
