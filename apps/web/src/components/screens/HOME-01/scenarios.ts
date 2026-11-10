// HOME-01 R2 bands (I-01-T24): frames h and i, and a2's empty bands, from seeded to-dos and
// mentions only (revision.md: §9.8.3, §9.8.4, SHL-04 row e). The mention items are the C16 feed's
// rows with their read-time facts; the to-do is SHL-17's row-6 to-do.
import type { NotificationItemOut, TodoOut } from "@abacus/api-client";
import { CLOCKS, IDS, P, row6Todo } from "../../../fixtures/seed/collaboration";
import { stableId } from "../../../fixtures/seed/prng";

export type BandFrame = "a2" | "h" | "i";

export interface BandScenario {
  viewer: string;
  /** The pane header's count stays the built one (11 for Daniel): bands never count into it. */
  headerCount: number | null;
  todos: TodoOut[];
  mentions: NotificationItemOut[];
}

function mention(
  key: string,
  createdAt: string,
  read: boolean,
  excerpt: string,
  objectLabel: string,
): NotificationItemOut {
  return {
    id: stableId(`notification:home01:${key}`),
    kind: "mention",
    category: "mention",
    actor: { kind: "human", user_id: P.margaret.user_id },
    created_at: createdAt,
    engagement_id: IDS.northwind,
    facts: { actor_name: P.margaret.name, excerpt, object_label: objectLabel },
    inline_actions: [],
    pending: false,
    read,
    subject: { id: IDS.threadRow3, type: "comment_thread" },
  };
}

export const BAND_SCENARIOS: Record<BandFrame, BandScenario> = {
  // Daniel Reyes scrolled to the new bands: both empty, the header still 11.
  a2: { viewer: "daniel-reyes", headerCount: 11, todos: [], mentions: [] },
  h: {
    viewer: "hannah-leclerc",
    headerCount: null,
    todos: [],
    mentions: [
      mention(
        "row3",
        CLOCKS.shl18a,
        false,
        "this cutoff item drives AJE-1 — show it as factual on the SUM.",
        "Northwind · Exceptions row 3",
      ),
      mention(
        "aud03",
        "2026-09-14T08:31:00-05:00",
        true,
        "did the bridge letter request go to Keystone for Oct–Dec 2025?",
        "AUD-03 Source Documents",
      ),
    ],
  },
  i: { viewer: "marcus-delaney", headerCount: null, todos: [row6Todo("marcus")], mentions: [] },
};
