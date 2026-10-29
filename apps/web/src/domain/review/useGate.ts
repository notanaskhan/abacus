// The E7 gate hook (P-04-T40; SPEC-360): one human gate command at a time, never optimistic. The
// card shows busy until the server answers; a 409 lands in the blocked state with its code and
// identifier-only facts (ADR-139), a 403 asks for a fresh sign-in through ConfirmItsYou (ADR-030),
// and a success raises an Undo toast whose only action is the caller's compensating command.

import { toast } from "@abacus/ui";
import { useCallback, useState } from "react";

/** A 403 on a gate needs recent MFA (ADR-030); the screen opens ConfirmItsYou. */
export function needsStepUp(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as { detail?: unknown }).detail === "forbidden"
  );
}

export interface GateBlocked {
  code: string;
  facts: Readonly<Record<string, string | number | boolean>>;
}

export type GatePhase = "idle" | "busy" | "blocked" | "done";

export interface UseGateOptions<T> {
  /** The gate command, over the generated client. */
  command: () => Promise<T>;
  /** The compensating command Undo calls (it writes `*.undone`); omit when the gate has none. */
  compensate?: () => Promise<unknown>;
  /** The toast's text once the command lands. */
  doneText: (result: T) => string;
  /** The toast's text when the command fails for any other reason. */
  failedText: string;
  onDone?: (result: T) => void;
}

export interface Gate {
  phase: GatePhase;
  blocked: GateBlocked | null;
  stepUp: boolean;
  setStepUp: (open: boolean) => void;
  run: () => Promise<void>;
  reset: () => void;
}

/** The 409 body's code and facts, or null when the error is not a conflict. */
export function conflictOf(error: unknown): GateBlocked | null {
  if (typeof error !== "object" || error === null) return null;
  const detail = (error as { detail?: unknown }).detail;
  if (typeof detail !== "string" || detail === "forbidden" || detail === "not_found") return null;
  const raw = (error as { facts?: unknown }).facts;
  const facts: Record<string, string | number | boolean> = {};
  if (typeof raw === "object" && raw !== null) {
    for (const [k, v] of Object.entries(raw)) {
      if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") facts[k] = v;
    }
  }
  return { code: detail, facts };
}

export function useGate<T>({
  command,
  compensate,
  doneText,
  failedText,
  onDone,
}: UseGateOptions<T>): Gate {
  const [phase, setPhase] = useState<GatePhase>("idle");
  const [blocked, setBlocked] = useState<GateBlocked | null>(null);
  const [stepUp, setStepUp] = useState(false);

  const run = useCallback(async () => {
    setPhase("busy");
    setBlocked(null);
    try {
      const result = await command();
      setPhase("done");
      onDone?.(result);
      toast.undoable({
        text: doneText(result),
        undo:
          compensate === undefined
            ? undefined
            : () => {
                void compensate().then(
                  () => {
                    setPhase("idle");
                  },
                  () => {
                    toast.show({ kind: "error", text: failedText });
                  },
                );
              },
      });
    } catch (error) {
      if (needsStepUp(error)) {
        setPhase("idle");
        setStepUp(true);
        return;
      }
      const conflict = conflictOf(error);
      if (conflict !== null) {
        setBlocked(conflict);
        setPhase("blocked");
        return;
      }
      setPhase("idle");
      toast.show({ kind: "error", text: failedText });
    }
  }, [command, compensate, doneText, failedText, onDone]);

  const reset = useCallback(() => {
    setPhase("idle");
    setBlocked(null);
  }, []);

  return { phase, blocked, stepUp, setStepUp, run, reset };
}
