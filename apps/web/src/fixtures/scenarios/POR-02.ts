// POR-02 Portal home: the fixture scenarios P-08-T08 can build before the screen (P-08-T15): a, b,
// c, d, e, f and M, each a data condition on `GET /v1/portal/home` and `/v1/me` → `portal`. g
// (Granite Peak statements review, Thu Oct 22) and h (Tessellate SOC 2) are the R2 waves 6 and 7
// and arrive with their epochs (docs/screens/POR-02.md). Clocks: E0 for all but b (Mon Feb 2,
// 2026, the first visit).

import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import type { PortalHomeOut } from "@abacus/api-client";
import { portalHandlers } from "../handlers/portal";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import {
  claireAllDone,
  claireFirstVisit,
  claireHome,
  meeraHome,
  tessHome,
} from "../seed/portal-home";

const seed = getSeed();

/** "Upload 2" is the Feld binder's Intake 2: its open requests in the seed. */
export function feldOpenUploads(): number {
  const id = seed.engagementIds.feld;
  const items = id === undefined ? [] : (seed.requestItems[id] ?? []);
  return items.filter((r) => ["requested", "uploaded", "returned"].includes(r.status)).length;
}

/** Mon Feb 2, 2026, 9:04 AM CT: Claire's first visit (POR-02 b). */
export const FIRST_VISIT_CLOCK = "2026-02-02T09:04:00-06:00";

const at = (
  state: string,
  persona: string,
  home: PortalHomeOut | null,
  clock = DEMO_INSTANT,
): Scenario => ({ state, persona, clock, handlers: portalHandlers({ clock, home }) });

export const scenarios = defineScenarios({
  a: at("a", "claire-feld", claireHome(feldOpenUploads())),
  b: at("b", "claire-feld", claireFirstVisit(), FIRST_VISIT_CLOCK),
  c: at("c", "claire-feld", claireAllDone()),
  d: at("d", "tess-moreno", tessHome()),
  e: at("e", "meera-shah", meeraHome()),
  f: at("f", "claire-feld", null),
  M: at("M", "claire-feld", claireHome(feldOpenUploads())),
});
