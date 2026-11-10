// HOME-01 Home dashboard: one fixture scenario per artboard and state (I-01-T05;
// docs/screens/HOME-01.md, States). E0 is Mon Sep 14, 2026, 9:24 AM CT; h and i stand at 12:40 PM.
// Data: seed/home.ts through handlers/home.ts (`GET /v1/home`) and handlers/human-gates.ts (the
// list and the one count source, computed from the same rows).
//
//   a, a2           daniel-reyes: 11 = 3 + 6 + 2 (a2 scrolls to "Your returns 6")
//   b, c, d, e      margaret-okonkwo 4 = 2 + 2 · samuel-ito 6 = 0 + 4 + 2 · kevin-osei "My work 4" ·
//                   grace-holloway 2 (spec-only role states, DF-06)
//   f               daniel-reyes on a quiet day: the counts read 0
//   g               daniel-reyes while `GET /v1/home` and the counts never answer
//   h, i            hannah-leclerc and marcus-delaney at 12:40 PM (their R2 bands are I-01-T24's)
//   office-denver   daniel-reyes with the Office chip on Denver (TPL-11f's counts)
//   tile-popover    daniel-reyes; the popover over a tile is I-01-T11's (by_office is in the data)
//   today-brief-off daniel-reyes with `today_brief.enabled` off: no "Open Today →"
//   walled          lena-park, walled from Ashford: nothing of Ashford in any count or row
//
// They live under fixtures/ (dev and test only); src/screens/HOME-01/scenarios.ts re-exports them.

import type { CapabilitiesOut, NotificationItemOut, TodoOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { homeHandlers } from "../handlers/home";
import { humanGateHandlers } from "../handlers/human-gates";
import { CLOCKS, IDS, P, row6Todo } from "../seed/collaboration";
import { stableId as bandId } from "../seed/prng";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { HOME_AFTERNOON } from "../seed/home";
import { capabilitiesFor, meV3For, officeIdOf } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

function capabilities(persona: string | undefined, brief: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "daniel-reyes");
  return {
    ...base,
    flags: { ...base.flags, "today_brief.enabled": brief },
  };
}

function at(
  state: string,
  persona: string,
  options: { clock?: string; brief?: boolean; handlers?: Record<string, FixtureHandler> } = {},
): Scenario {
  const brief = options.brief ?? true;
  return {
    state,
    persona,
    clock: options.clock ?? DEMO_INSTANT,
    handlers: {
      ...E0.handlers,
      ...homeHandlers(),
      ...humanGateHandlers(seed),
      "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who, brief)),
      // `/v1/me` v3: the firm's offices name the Office chip's options.
      "GET /v1/me": ({ persona: who }) => json(meV3For(seed, who ?? persona)),
      ...options.handlers,
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "daniel-reyes"),
  a2: at("a2", "daniel-reyes"),
  b: at("b", "margaret-okonkwo"),
  c: at("c", "samuel-ito"),
  d: at("d", "kevin-osei"),
  e: at("e", "grace-holloway"),
  f: at("f", "daniel-reyes", { handlers: humanGateHandlers(seed, { rows: () => [] }) }),
  g: at("g", "daniel-reyes", {
    handlers: {
      "GET /v1/home": () => never(),
      "GET /v1/human-gates/counts": () => never(),
      "GET /v1/human-gates": () => never(),
    },
  }),
  h: at("h", "hannah-leclerc", { clock: HOME_AFTERNOON }),
  i: at("i", "marcus-delaney", { clock: HOME_AFTERNOON }),
  "office-denver": at("office-denver", "daniel-reyes"),
  "tile-popover": at("tile-popover", "daniel-reyes"),
  "today-brief-off": at("today-brief-off", "daniel-reyes", { brief: false }),
  walled: at("walled", "lena-park"),
});

/** The office each state opens on (null: all offices): office-denver opens on Denver. */
export const OFFICE: Readonly<Partial<Record<keyof typeof scenarios, string>>> = {
  "office-denver": officeIdOf("Denver"),
};

// ---- HOME-01 R2 bands (I-01-T24): h, i and a2, seeded to-dos and mentions only (revision.md) ----

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
    id: bandId(`notification:home01:${key}`),
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
