// The Today brief in fixture mode (I-02-T03; docs/contracts/today.md): `/v1/me/today*` on the
// stub's shapes from seed/today.ts. Margaret Okonkwo sees her four items; every other persona sees
// Daniel Reyes's day (SHL-23 1). Builds answer 202; the drill-in is Ridgeline's.

import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  HISTORY,
  QUESTION_ACCEPTED,
  danielToday,
  margaretToday,
  ridgelineDrill,
} from "../seed/today";

export function todayHandlers(): Record<string, FixtureHandler> {
  return {
    "GET /v1/me/today": ({ persona }) =>
      json(persona === "margaret-okonkwo" ? margaretToday() : danielToday()),
    "POST /v1/me/today/builds": () => json({ status_url: "/v1/me/today", started: 1 }, 202),
    "GET /v1/me/today/work-items/{work_item_id}": () => json(ridgelineDrill()),
    "GET /v1/me/today/history": () => json(HISTORY),
    "GET /v1/me/today/history/{brief_id}": () => json(danielToday()),
    "POST /v1/me/today/questions": () => json(QUESTION_ACCEPTED, 202),

  };
}
