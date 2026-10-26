// The logged PII reveal on the cockpit viewer (A-01-T15 on P-03-T16; C4 §3.5, DEC-370): one click
// on "Reveal (logged)" posts `POST /v1/evidence-versions/{v}/pii-reveals {region_id}`; the value
// shows in place of its mask for `expires_in` seconds and is never stored or logged here. A stale
// or missing MFA answers 403 `mfa_required` and opens the shell's step-up; any other refusal shows
// nothing (offshore, role and independence refusals are the plain 403, DEC-370).

import { revealPiiMutation } from "@abacus/api-client/query";
import { Button, DEFAULT_TZ, Dialog, type RevealedValue, time, toast } from "@abacus/ui";
import { useMutation } from "@tanstack/react-query";
import { type JSX, useEffect, useRef, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useSession } from "../../app-core/session";
import { AUDIT_MESSAGES } from "./messages";

function needsMfa(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const facts = (error as { facts?: { reason?: unknown } }).facts;
  return facts?.reason === "mfa_required";
}

export interface LoggedReveal {
  revealed: Readonly<Record<string, RevealedValue>>;
  onReveal: (maskId: string) => void;
  /** The step-up is needed: the host opens `ConfirmItsYou`. */
  stepUp: boolean;
  setStepUp: (open: boolean) => void;
}

export function useLoggedReveal(versionId: string): LoggedReveal {
  const session = useSession();
  const tz = session.tz ?? DEFAULT_TZ;
  const name = session.user?.displayName ?? "";
  const reveal = useMutation({ ...revealPiiMutation() });
  const [revealed, setRevealed] = useState<Record<string, RevealedValue>>({});
  const [stepUp, setStepUp] = useState(false);
  const timers = useRef<number[]>([]);
  useEffect(
    () => () => {
      for (const t of timers.current) window.clearTimeout(t);
    },
    [],
  );
  const onReveal = (maskId: string): void => {
    reveal.mutateAsync({ path: { version_id: versionId }, body: { region_id: maskId } }).then(
      (out) => {
        setRevealed((was) => ({
          ...was,
          [maskId]: {
            value: out.value,
            note: AUDIT_MESSAGES.viewer.revealed(name, time(out.revealed_at, { tz })),
          },
        }));
        timers.current.push(
          window.setTimeout(() => {
            setRevealed((was) =>
              Object.fromEntries(Object.entries(was).filter(([id]) => id !== maskId)),
            );
          }, out.expires_in * 1000),
        );
      },
      (error: unknown) => {
        if (needsMfa(error)) setStepUp(true);
        else toast.show({ kind: "error", text: AUDIT_MESSAGES.viewer.revealFailed });
      },
    );
  };
  return { revealed, onReveal, stepUp, setStepUp };
}

/** The step-up a stale MFA asks for (ADR-030), as the shell's `ConfirmItsYou` draws it. */
export function RevealStepUp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  const words = AUDIT_MESSAGES.viewer.stepUp;
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={words.title} description={words.body}>
      <div className="flex justify-end gap-2">
        <Button
          variant="secondary"
          onClick={() => {
            onOpenChange(false);
          }}
        >
          {words.cancel}
        </Button>
        <Button
          onClick={() => {
            signIn(currentRoute(), { forceLogin: true });
          }}
        >
          {words.signIn}
        </Button>
      </div>
    </Dialog>
  );
}
