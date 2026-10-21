import clsx from "clsx";
import type { JSX } from "react";
import { personInitials } from "./initials";

// People (C-28 Presence, F-05-T14): a round avatar with initials, the name beside it, and the
// stack that shows who is in a document. There are no photos and no "online" dots, so an avatar
// is its initials on a tint. The tints are the chart fills in join order: one person keeps one
// tint for the whole document, the fifth person reuses the first. The Accrued Agent is never a
// person: it has AgentAvatar, no initials and no tint.

export const PERSON_TINTS = [1, 2, 3, 4] as const;
export type PersonTint = (typeof PERSON_TINTS)[number];

/** The tint of the nth person to join (0 is first); the fifth reuses the first. */
export function tintForJoin(order: number): PersonTint {
  const t = PERSON_TINTS[((Math.trunc(order) % 4) + 4) % 4];
  return t ?? 1;
}

export const PERSON_SIZES = [20, 22] as const;
export type PersonSize = (typeof PERSON_SIZES)[number];

const SIZE: Record<PersonSize, string> = { 20: "size-[20px]", 22: "size-[22px]" };

// Static class names so the Tailwind scan finds them. `idle` fades the fill, not the initials: the
// handoff fades the whole avatar to 60%, which drops the initials under AA (DEC-11).
const FILL: Record<PersonTint | 0, { solid: string; idle: string; ink: string }> = {
  0: { solid: "bg-chip", idle: "bg-chip/60", ink: "text-ink-2" },
  1: { solid: "bg-viz-p1", idle: "bg-viz-p1/60", ink: "text-ink" },
  2: { solid: "bg-viz-p2", idle: "bg-viz-p2/60", ink: "text-ink" },
  3: { solid: "bg-viz-p3", idle: "bg-viz-p3/60", ink: "text-ink" },
  4: { solid: "bg-viz-p4", idle: "bg-viz-p4/60", ink: "text-ink" },
};

export interface PersonAvatarProps {
  name: string;
  size?: PersonSize;
  /** The person's tint in this document; none gives the neutral chip fill. */
  tint?: PersonTint;
  /** No activity for over five minutes: the fill fades. */
  idle?: boolean;
  /** Hide it from assistive technology, where the name is written beside it. */
  decorative?: boolean;
  className?: string;
}

/** A 20px circle with the person's initials, 10.5px in medium weight. */
export function PersonAvatar({
  name,
  size = 20,
  tint,
  idle = false,
  decorative = false,
  className,
}: PersonAvatarProps): JSX.Element {
  const fill = FILL[tint ?? 0];
  return (
    <span
      {...(decorative ? { "aria-hidden": true } : { role: "img", "aria-label": name })}
      data-person-avatar=""
      data-tint={tint ?? "none"}
      data-idle={idle ? "" : undefined}
      className={clsx(
        "inline-flex flex-none items-center justify-center rounded-pill text-micro tracking-[0]",
        SIZE[size],
        idle ? fill.idle : fill.solid,
        fill.ink,
        className,
      )}
    >
      {personInitials(name)}
    </span>
  );
}

export interface PersonProps extends Omit<PersonAvatarProps, "decorative"> {
  /** Draw the name; false leaves the avatar alone, with the name as its accessible name. */
  showName?: boolean;
}

/** A person: the avatar, 8px of space, the name in 13px, cut with an ellipsis when it is long. */
export function Person({ showName = true, ...avatar }: PersonProps): JSX.Element {
  if (!showName) return <PersonAvatar {...avatar} />;
  return (
    <span className="inline-flex min-w-0 items-center gap-[8px]">
      <PersonAvatar {...avatar} decorative />
      <span className="truncate text-body text-ink">{avatar.name}</span>
    </span>
  );
}

export interface PersonStackProps {
  /** People in join order: the first gets the first tint. The viewer is not in their own stack. */
  people: readonly { name: string; idle?: boolean }[];
  /** At most this many circles, then a "+n" circle. Three in the handoff. */
  max?: number;
  className?: string;
}

/** Overlapping avatars, 1.5px white ring and a 6px overlap, then "+n" for the rest. */
export function PersonStack({ people, max = 3, className }: PersonStackProps): JSX.Element {
  const shown = people.slice(0, max);
  const more = people.length - shown.length;
  const ring = "ring-[1.5px] ring-card";
  return (
    <span
      role="group"
      aria-label={people.map((p) => p.name).join(", ")}
      className={clsx("inline-flex items-center", className)}
    >
      {shown.map((p, i) => (
        <PersonAvatar
          key={`${p.name}-${String(i)}`}
          name={p.name}
          tint={tintForJoin(i)}
          idle={p.idle ?? false}
          decorative
          className={clsx(ring, i > 0 && "-ml-[6px]")}
        />
      ))}
      {more > 0 && (
        <span
          aria-hidden="true"
          className={clsx(
            "-ml-[6px] inline-flex size-[20px] flex-none items-center justify-center rounded-pill bg-chip text-pill-sm text-ink-2",
            ring,
          )}
        >
          {`+${String(more)}`}
        </span>
      )}
    </span>
  );
}
