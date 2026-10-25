// POR-02 Portal home: one scenario per artboard, each a data condition on `GET /v1/portal/home`
// and `/v1/me` → `portal` (P-08-T08 wrote a–f and M; P-08-T23 adds g and h). g (Granite Peak's
// statements review, Thu Oct 22) and h (Tessellate's SOC 2) are the R2 waves 6 and 7: fixture-only,
// behind the `statements_studio` and `attest` entitlements, until A-10/R-02 and X-01 register their
// home sources (docs/screens/POR-02.md). Clocks: E0 for all but b (Mon Feb 2, 2026, the first
// visit) and g (Thu Oct 22, 2026, 8:30 AM CT).

import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import type { PortalHomeOut } from "@abacus/api-client";
import { portalHandlers } from "../handlers/portal";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import {
  claireAllDone,
  claireFirstVisit,
  claireHome,
  luisHome,
  marisolHome,
  meeraHome,
  STATEMENTS_REVIEW_CLOCK,
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
  g: at("g", "luis-ferrante", luisHome(), STATEMENTS_REVIEW_CLOCK),
  h: at("h", "marisol-vega", marisolHome()),
  M: at("M", "claire-feld", claireHome(feldOpenUploads())),
});
