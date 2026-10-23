import type { IconName } from "../icons";
import type { DiscState } from "../status";

// The C-03 Rail kit and C-04 Record kit shapes (F-05-T40). Generic view models: a screen maps its
// API data into these; nothing here names a resource or imports the API client (L2 rule).

/** The second line of a phase as a pill (C-03 PhaseRow): Ready, In progress, Waiting on inputs. */
export type PhasePillKind = "ready" | "progress" | "waiting";

/** A rail link row (C-03 RailRow): Client, Requests, Methodology, Source Documents ... */
export interface RailLink {
  id: string;
  /** 15px ink-3 lead. In the compact rail a to-do disc stands in for it. */
  icon?: IconName;
  /** The disc of a compact rail's link (default `todo`). */
  disc?: DiscState;
  title: string;
  sub?: string;
  /** Opens somewhere else: a trailing arrow instead of the chevron. */
  elsewhere?: boolean;
}

/** A phase row (C-03 PhaseRow). State is always a disc plus words: a pill or a live line. */
export interface Phase {
  id: string;
  title: string;
  /** Default `todo`; `fail` also turns the title red ink. */
  disc?: DiscState;
  pill?: { kind: PhasePillKind; text: string };
  /** "Complete · 9:26 AM", "Running", "Queued"; amber for a line that wants a person. */
  live?: { text: string; tone?: "amber" };
  /** The dark "Begin…" pill on a to-do phase that can start now. */
  begin?: boolean;
  /** Versions, indented to 30. */
  children?: readonly Phase[];
}

/** A group band and its phases (C-03 GroupBand). */
export interface RailSection {
  id: string;
  title: string;
  /** A band that navigates ("Activity"): a trailing chevron-right, no phases. */
  nav?: boolean;
  /** The band's initial state (default open). */
  collapsed?: boolean;
  /** Default true in the default variant; the outline variant never collapses. */
  collapsible?: boolean;
  phases?: readonly Phase[];
}

/** The four items of a phase row's ··· menu, in order. */
export const ROW_MENU = ["Open", "Assign…", "Mark as Done", "Skip phase…"] as const;
export type RowMenuItem = (typeof ROW_MENU)[number];

// ---- C-04 Record kit --------------------------------------------------------------------------

export type RecordKind = "audit" | "tax" | "close";

/** The A7 state tones of a record's state pill. */
export type RecordTone = "amber" | "done" | "ready" | "issue" | "neutral" | "muted";

/** A summary stat row: the value never larger than 15px. */
export interface RecordStat {
  id: string;
  value: string;
  caption: string;
  /** The caption reads red ink ("Past Due (Sep 10)"). */
  overdue?: boolean;
}

export type KvKind = "text" | "link" | "person";

/** A key and value row (C-04 KVRow). */
export interface KvRow {
  id: string;
  label: string;
  value: string;
  kind?: KvKind;
  /** A link's trailing glyph: chevron (in place, the default) or arrow (opens elsewhere). */
  trail?: "chevron" | "arrow";
  /** A Preparers or Reviewers row leads with a disc: done when signed, the to-do ring when not. */
  signed?: boolean;
}

export interface KvGroup {
  title?: string;
  rows: readonly KvRow[];
}
