// PresenceStore (C-28 completion; F-08-T24; TASK-8930; F-08 §F; ADR P-15; DEC-5932): who else is
// on an object, from heartbeats the server fans out as identifiers only (F-08-T13's anchors:
// record, cell, section, card). Pure and framework-free; the kit's hook and markers read it.
//
// - Tints follow join order (the first other person gets --viz-p1 / --viz-d1, the fifth reuses
//   the first), and the viewer never appears in their own stack: their own heartbeat is dropped
//   before tints are given, so a tint never jumps when the viewer joins or leaves.
// - A person whose last heartbeat is older than IDLE_MS (5 minutes) is idle and renders at 60%.
// - A person whose last heartbeat is older than the server's TTL (45 s, P-10) has left: they are
//   dropped on read, so a dead tab never lingers.
// - Presence never locks anything: the store has no lock, owner or "being edited" gate; a section
//   editing banner is information (the editor's one-editor rule is DocumentEditor's, ADR P-59).
import { type PersonTint, tintForJoin } from "../../brand/person";

export type PresenceAnchorKind = "record" | "cell" | "section" | "card";
export type PresenceActivity = "viewing" | "editing";

export interface PresenceHeartbeat {
  userId: string;
  name: string;
  anchor: { kind: PresenceAnchorKind; key: string } | null;
  activity: PresenceActivity;
  /** When this heartbeat was seen (ms since epoch). */
  at: number;
}

export interface PresencePeer {
  userId: string;
  name: string;
  tint: PersonTint;
  idle: boolean;
  anchor: { kind: PresenceAnchorKind; key: string } | null;
  activity: PresenceActivity;
  /** The first heartbeat this session saw from them: the join order. */
  joinedAt: number;
  lastSeenAt: number;
}

/** Idle over five minutes renders at 60% (F-08 §F). */
export const IDLE_MS = 5 * 60_000;
/** A heartbeat expires after 45 s (P-10's TTL; F-08-T13). */
export const TTL_MS = 45_000;

interface Entry {
  userId: string;
  name: string;
  anchor: PresenceHeartbeat["anchor"];
  activity: PresenceActivity;
  joinedAt: number;
  lastSeenAt: number;
  /** The last time the person did something other than sit (an activity or anchor change). */
  activeAt: number;
}

export class PresenceStore {
  private readonly entries = new Map<string, Entry>();
  private joined = 0;
  private readonly order = new Map<string, number>();

  constructor(private readonly viewerId: string) {}

  /** Record a heartbeat; the viewer's own are ignored. */
  apply(beat: PresenceHeartbeat): void {
    if (beat.userId === this.viewerId) return;
    const was = this.entries.get(beat.userId);
    if (!this.order.has(beat.userId)) {
      this.order.set(beat.userId, this.joined);
      this.joined += 1;
    }
    const moved =
      was === undefined ||
      was.activity !== beat.activity ||
      was.anchor?.kind !== beat.anchor?.kind ||
      was.anchor?.key !== beat.anchor?.key;
    this.entries.set(beat.userId, {
      userId: beat.userId,
      name: beat.name,
      anchor: beat.anchor,
      activity: beat.activity,
      joinedAt: was?.joinedAt ?? beat.at,
      lastSeenAt: beat.at,
      activeAt: was === undefined || moved ? beat.at : was.activeAt,
    });
  }

  /** Someone left (a closed tab's last word); the TTL drops the rest. */
  leave(userId: string): void {
    this.entries.delete(userId);
  }

  /** Everyone else here now, in join order, each with their tint and idle state. */
  peers(now: number): PresencePeer[] {
    const out: PresencePeer[] = [];
    for (const e of this.entries.values()) {
      if (now - e.lastSeenAt > TTL_MS) continue;
      out.push({
        userId: e.userId,
        name: e.name,
        tint: tintForJoin(this.order.get(e.userId) ?? 0),
        idle: now - e.activeAt > IDLE_MS,
        anchor: e.anchor,
        activity: e.activity,
        joinedAt: e.joinedAt,
        lastSeenAt: e.lastSeenAt,
      });
    }
    return out.sort((a, b) => (this.order.get(a.userId) ?? 0) - (this.order.get(b.userId) ?? 0));
  }

  /** The people on one anchor (a cell, a section, a card), in join order. */
  on(kind: PresenceAnchorKind, key: string, now: number): PresencePeer[] {
    return this.peers(now).filter((p) => p.anchor?.kind === kind && p.anchor.key === key);
  }
}
