import {
  autonomyOptions,
  autonomyQueryKey,
  letterPolicyOptions,
  letterPolicyQueryKey,
  setAutonomyMutation,
  setLetterPolicyMutation,
} from "@abacus/api-client/query";
import { Alert, Button, Panel, Skeleton, StatusPill } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

// ADR-061 in plain words; decisions stay with people at every level (ADR-005).
const LEVELS = [
  {
    level: 0,
    name: "Advise",
    may: "Suggests what to do next. Nothing runs on its own: your team starts retrievals and screening.",
    available: true,
  },
  {
    level: 1,
    name: "Routine",
    may: "Re-pulls ledger data, screens evidence as it arrives, proposes matches and sends routine reminders.",
    available: true,
  },
  {
    level: 2,
    name: "Manage",
    may: "Plans its own day for each engagement, sequences follow-ups and escalates to the team.",
    available: false,
  },
  {
    level: 3,
    name: "Portfolio",
    may: "Coordinates work across engagements.",
    available: false,
  },
];

/** SPEC-024 AC-5: the firm's autonomy level (firm administrators change it). */
export function Autonomy({ canSet }: { canSet: boolean }): JSX.Element {
  const queryClient = useQueryClient();
  const current = useQuery(autonomyOptions());
  const [picked, setPicked] = useState<number | null>(null);
  const [confirm, setConfirm] = useState(false);
  const save = useMutation({
    ...setAutonomyMutation(),
    onSuccess: () => {
      setPicked(null);
      void queryClient.invalidateQueries({ queryKey: autonomyQueryKey() });
      void queryClient.invalidateQueries();
    },
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
    },
  });
  if (current.isPending) return <Skeleton className="h-48" />;
  if (current.isError) {
    return <Alert title="Couldn't load autonomy">{errorMessage(current.error)}</Alert>;
  }
  const chosen = picked ?? current.data.level;
  return (
    <Panel title="Autonomy">
      <p className="text-sm text-muted">
        How much the agent may do on its own. People always make the decisions: accepting,
        rejecting and sending back evidence.
      </p>
      <fieldset className="flex flex-col gap-2" disabled={!canSet || save.isPending}>
        <legend className="sr-only">Autonomy level</legend>
        {LEVELS.map((l) => (
          <label
            key={l.level}
            className={`flex items-start gap-3 rounded-[var(--radius-control)] border p-3 ${
              chosen === l.level ? "border-accent bg-accent-soft" : "border-line"
            } ${l.available ? "" : "opacity-60"}`}
          >
            <input
              type="radio"
              name="autonomy"
              value={l.level}
              checked={chosen === l.level}
              disabled={!l.available}
              onChange={() => {
                setPicked(l.level);
              }}
              className="mt-1"
            />
            <span className="flex flex-col gap-0.5">
              <span className="flex items-center gap-2 font-semibold">
                {l.name}
                {current.data.level === l.level && <StatusPill tone="success">Current</StatusPill>}
                {!l.available && (
                  <StatusPill tone="neutral">Coming with the engagement agent</StatusPill>
                )}
              </span>
              <span className="text-sm text-muted">{l.may}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {canSet ? (
        <div className="flex items-center gap-3">
          <Button
            disabled={save.isPending}
            onClick={() => {
              save.mutate({ body: { level: chosen } });
            }}
          >
            {current.data.set_at === null && picked === null ? "Confirm Routine" : "Save"}
          </Button>
          {current.data.set_at !== null && (
            <span className="text-xs text-muted">
              Last set {new Date(current.data.set_at).toLocaleString()}
            </span>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted">Only firm administrators can change this.</p>
      )}
      {save.isError && !isForbidden(save.error) && (
        <p role="alert" className="text-sm text-danger">
          {errorMessage(save.error)}
        </p>
      )}
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </Panel>
  );
}

/** SPEC-025 Q4: whether the engagement letter must be recorded before client data. */
export function LetterPolicy({ canSet }: { canSet: boolean }): JSX.Element | null {
  const queryClient = useQueryClient();
  const policy = useQuery({ ...letterPolicyOptions(), retry: false });
  const [confirm, setConfirm] = useState(false);
  const save = useMutation({
    ...setLetterPolicyMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: letterPolicyQueryKey() });
    },
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
    },
  });
  if (policy.data === undefined) return null;
  return (
    <Panel title="Engagement letters">
      <label className="flex items-start gap-3 text-sm">
        <input
          type="checkbox"
          className="mt-1"
          checked={policy.data.required}
          disabled={!canSet || save.isPending}
          onChange={(event) => {
            save.mutate({ body: { required: event.target.checked } });
          }}
        />
        <span>
          Require the engagement letter before client data
          <span className="block text-muted">
            Off: a missing letter is flagged but doesn&apos;t block. The standards say the letter
            should be agreed, preferably before the work begins.
          </span>
        </span>
      </label>
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </Panel>
  );
}
