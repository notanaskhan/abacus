import type { JSX } from "react";
import { cn } from "../cn";
import { Icon } from "../icons";
import { Pill } from "../components/pill";

// SignOffSlots chips (C-25 presentational; F-06-T20; T6 d, TPL-06 e): the initials of the people
// who signed a target, in level order (P before R), each a button that only hands off to SHL-12
// through `onOpenSignOff(target, level)`. There is no create path and no slot for the agent: a
// slot is a person's signature, and signing happens in SHL-12 (P-04). A stale slot says so in
// words and with an icon ("!" and "Changed after sign-off"), never by colour alone. The ladder
// with the Sign off HumanAction is P-04's (`gates/sign-off-slots.tsx`, SHL-12).

export interface SignOffChip {
  /** "L1", "L2" … sorted ascending, so the preparer's chip comes before the reviewer's. */
  level: string;
  initials: string;
  name: string;
  /** Already formatted ("Sep 14, 9:40 AM"). */
  when?: string | undefined;
  stale?: boolean | undefined;
}

export interface SignOffChipsCopy {
  /** The group's accessible name ("Sign-offs"). */
  label: string;
  /** "Changed after sign-off". */
  changedAfter: string;
  /** A chip's accessible name: "Samuel Ito, L2: open sign-off". */
  open: (name: string, level: string) => string;
  /** The green-tint pill after a current review sign-off ("Reviewed · SI"); omitted, no pill. */
  reviewed?: ((initials: string) => string) | undefined;
}

export interface SignOffSlotChipsProps {
  target: string;
  slots: readonly SignOffChip[];
  copy: SignOffChipsCopy;
  /** The level whose current signature earns the reviewed pill ("L2"). */
  reviewLevel?: string;
  onOpenSignOff: (target: string, level: string) => void;
  className?: string;
}

const levelNo = (level: string): number => Number.parseInt(level.replace(/\D/g, ""), 10) || 0;

export function SignOffSlotChips({
  target,
  slots,
  copy,
  reviewLevel = "L2",
  onOpenSignOff,
  className,
}: SignOffSlotChipsProps): JSX.Element | null {
  if (slots.length === 0) return null;
  const ordered = [...slots].sort((a, b) => levelNo(a.level) - levelNo(b.level));
  const reviewer = ordered.find((s) => s.level === reviewLevel && s.stale !== true);
  return (
    <span
      role="group"
      aria-label={copy.label}
      data-sign-off-slots=""
      className={cn("flex items-center gap-[6px]", className)}
    >
      {ordered.map((s) => (
        <button
          key={s.level}
          type="button"
          data-sign-off-chip={s.initials}
          data-level={s.level}
          {...(s.stale === true ? { "data-stale": "" } : {})}
          aria-label={copy.open(s.name, s.level)}
          title={s.when === undefined ? s.name : `${s.name} · ${s.when}`}
          onClick={() => {
            onOpenSignOff(target, s.level);
          }}
          className="flex items-center gap-[4px] rounded-pill"
        >
          {s.stale === true ? (
            <>
              <span className="text-meta text-ink-3 line-through">✓ {s.initials}</span>
              <Pill variant="amber" size="sm">
                <Icon name="triangle-alert" size={12} />
                <span aria-hidden className="px-[2px] font-medium">
                  !
                </span>
                {copy.changedAfter}
              </Pill>
            </>
          ) : (
            <Pill variant="green" size="tally" check>
              {s.initials}
            </Pill>
          )}
        </button>
      ))}
      {reviewer !== undefined && copy.reviewed !== undefined && (
        <Pill variant="green-tint" size="sm" data-reviewed-pill="">
          {copy.reviewed(reviewer.initials)}
        </Pill>
      )}
    </span>
  );
}
