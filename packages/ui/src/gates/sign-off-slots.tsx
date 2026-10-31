import type { JSX } from "react";
import { HumanAction } from "../attribution/human-action";
import type { Actor } from "../attribution/actor";
import { cn } from "../cn";
import { StatusDisc } from "../components/status";
import type { GateCheck } from "./checks-list";
import { ChecksList } from "./checks-list";

// SignOffSlots (C-25; E7; P-04-T40; SHL-12): the ladder of sign-off levels on a target (L1 to
// L5), each slot empty, signed (a person and when) or stale (signed before the content changed).
// P-04-T49: the ladder never signs. Every slot and the viewer's next "Sign off…" only open SHL-12
// (`onOpenSignOff(level)`), the one place a sign-off is added (chapter 04 E7); the next slot's
// opener stays disabled while a check fails. A slot is never signed for the agent.

export interface SignOffSlot {
  level: string;
  /** "Preparer", "Reviewer", "Manager", "Partner". */
  role: string;
  signer: string | null;
  /** Already formatted ("Sep 14, 9:24 AM"). */
  at: string | null;
  stale?: boolean;
}

export interface SignOffSlotsProps {
  slots: readonly SignOffSlot[];
  /** The level the viewer may sign now, if any. */
  next?: string | null;
  actor: Actor;
  checks?: readonly GateCheck[];
  busy?: boolean;
  /** Opens SHL-12 at that level. Nothing here signs. */
  onOpenSignOff?: (level: string) => void;
  className?: string;
}

export function SignOffSlots({
  slots,
  next = null,
  actor,
  checks = [],
  busy = false,
  onOpenSignOff,
  className,
}: SignOffSlotsProps): JSX.Element {
  const blocked = checks.some((c) => !c.ok);
  return (
    <section
      aria-label="Sign-offs"
      data-gate="sign-offs"
      className={cn("flex flex-col gap-[10px]", className)}
    >
      <ol className="flex flex-col divide-y-[0.5px] divide-hair rounded-nested bg-card shadow-e1">
        {slots.map((s) => (
          <li
            key={s.level}
            data-level={s.level}
            className="flex min-h-[44px] items-center gap-[10px] px-[12px]"
          >
            <StatusDisc state={s.signer === null ? "todo" : s.stale === true ? "warn" : "done"} />
            {onOpenSignOff === undefined ? (
              <span className="w-[32px] text-dense font-medium">{s.level}</span>
            ) : (
              <button
                type="button"
                data-open-sign-off={s.level}
                aria-label={`${s.role} ${s.level}`}
                onClick={() => {
                  onOpenSignOff(s.level);
                }}
                className="w-[32px] text-left text-dense font-medium underline-offset-2 hover:underline"
              >
                {s.level}
              </button>
            )}
            <span className="flex-1 text-body">
              {s.signer === null ? (
                <span className="text-ink-3">{s.role}</span>
              ) : (
                <>
                  {s.signer}
                  {s.at !== null && <span className="pl-[6px] text-meta text-ink-3">{s.at}</span>}
                  {s.stale === true && (
                    <span className="pl-[6px] text-meta text-amber-ink">
                      stale: the content changed
                    </span>
                  )}
                </>
              )}
            </span>
            {s.level === next && (
              <HumanAction
                verb="Sign off"
                object={s.level}
                opensDialog
                actor={actor}
                disabled={busy || blocked}
                onClick={() => onOpenSignOff?.(s.level)}
              />
            )}
          </li>
        ))}
      </ol>
      {checks.length > 0 && <ChecksList checks={checks} label="Before you sign off" />}
    </section>
  );
}
