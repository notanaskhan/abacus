// Presence markers (C-28; F-08-T24; F-08 §F; DEC-5932): the hook and the four markers the kits
// mount. Every marker decorates; none disables, locks or hides a control (no presence state ever
// locks a cell, card or section; locks derive from sign-off state only, ADR P-07).
//   - usePresence(source, viewerId): peers in join order, re-read on a tick so idle and TTL apply.
//   - CellPresenceRing: a 1.5 px ring in the person's dark tint (--viz-dN) with a 10.5 name label
//     on their light tint (TPL-20a: Simone on SURL-12 in --p2 / --d2); idle at 60%.
//   - SectionEditingBanner: "<Name> is editing <section>" (a statement, not a lock).
//   - CardPresence: the stack of people on a card (C-28 avatars, the card's 20 px owner chip size).
//   - RecordPresence: the record bar's stack with "Active now · <names> · Viewing <where>".
import { type JSX, type ReactNode, useEffect, useMemo, useReducer } from "react";
import { PersonAvatar, PersonStack, type PersonTint } from "../../brand/person";
import { useNow } from "../../clock";
import { cn } from "../../cn";
import { Tooltip } from "../../components/popover";
import type { PresenceSource } from "./sources";
import { type PresencePeer, PresenceStore } from "./store";

const TICK_MS = 15_000;

/** The peers on an object, from a source; the viewer is never among them. Time is the clock's
 * (`useNow`), re-read every heartbeat so idle and the TTL apply as it passes. */
export function usePresence(source: PresenceSource | undefined, viewerId: string): PresencePeer[] {
  const store = useMemo(() => new PresenceStore(viewerId), [viewerId]);
  const [version, bump] = useReducer((n: number) => n + 1, 0);
  const now = useNow(TICK_MS).getTime();
  useEffect(() => {
    if (source === undefined) return undefined;
    return source.subscribe((e) => {
      if (e.kind === "beat") store.apply(e.beat);
      else store.leave(e.userId);
      bump();
    });
  }, [source, store]);
  // `version` changes after each event, so the list is read again.
  return useMemo(() => (version >= 0 ? store.peers(now) : []), [store, version, now]);
}

const RING: Record<PersonTint, string> = {
  1: "ring-viz-d1",
  2: "ring-viz-d2",
  3: "ring-viz-d3",
  4: "ring-viz-d4",
};
const LABEL: Record<PersonTint, string> = {
  1: "bg-viz-p1",
  2: "bg-viz-p2",
  3: "bg-viz-p3",
  4: "bg-viz-p4",
};

/** A cell another person is on: the ring and their name label. Never a lock. */
export function CellPresenceRing({
  peer,
  children,
}: {
  peer: PresencePeer | undefined;
  children: ReactNode;
}): JSX.Element {
  if (peer === undefined) return <>{children}</>;
  return (
    <span
      data-presence-cell={peer.userId}
      data-tint={peer.tint}
      data-idle={peer.idle ? "" : undefined}
      className={cn(
        "relative block ring-[1.5px] ring-inset",
        RING[peer.tint],
        peer.idle && "opacity-60",
      )}
    >
      {children}
      <span
        className={cn(
          "absolute -top-[16px] right-0 rounded-t-[4px] px-[4px] text-[10.5px] leading-[16px] text-ink",
          LABEL[peer.tint],
        )}
      >
        {peer.name}
      </span>
    </span>
  );
}

/** The section another person is editing: a statement above the section, never a lock. */
export function SectionEditingBanner({
  peer,
  section,
}: {
  peer: PresencePeer | undefined;
  section: string;
}): JSX.Element | null {
  if (peer?.activity !== "editing") return null;
  return (
    <p
      role="status"
      data-presence-section={peer.userId}
      className={cn(
        "flex h-[28px] items-center gap-[6px] rounded-nested bg-nested px-[10px] text-[12px] text-ink-2",
        peer.idle && "opacity-60",
      )}
    >
      <PersonAvatar name={peer.name} tint={peer.tint} idle={peer.idle} decorative />
      {`${peer.name} is editing ${section}`}
    </p>
  );
}

/** The people on a card (C-24), as a small stack. */
export function CardPresence({ peers }: { peers: readonly PresencePeer[] }): JSX.Element | null {
  if (peers.length === 0) return null;
  return (
    <span data-presence-card="">
      <PersonStack people={peers.map((p) => ({ name: p.name, idle: p.idle }))} />
    </span>
  );
}

/** The record bar's stack: "Active now · Simone Baptiste · Viewing Note 5". */
export function RecordPresence({
  peers,
  where,
}: {
  peers: readonly PresencePeer[];
  /** What the first person is viewing ("Note 5"), when the host knows it. */
  where?: string;
}): JSX.Element | null {
  if (peers.length === 0) return null;
  const line = [
    "Active now",
    peers.map((p) => p.name).join(", "),
    ...(where ? [`Viewing ${where}`] : []),
  ].join(" · ");
  return (
    <Tooltip content={line}>
      <span data-presence-record="" aria-label={line}>
        <PersonStack people={peers.map((p) => ({ name: p.name, idle: p.idle }))} />
      </span>
    </Tooltip>
  );
}
