// AUD-16 Misstatements & adjustments (A-06-T22; the handoff spec): the fixture scenarios, each on
// Northwind PY2025 (seed/aud16.ts), viewed by Hannah Leclerc unless noted:
//
//   a            Mon Sep 28, 10:15 AM  Passed (SUM): 2 passed, aggregate 34,150 = 18.1% of PM
//   b            10:15 AM              Proposed AJEs: AJE-1 Client approved · Dana Kowalski · Sep 25
//   b2           10:15 AM              Proposed AJEs before sending: Review required, Send enabled
//   c            10:15 AM              Reclassifications: RJE-1 14,850
//   d            10:15 AM              Below CT: BCT-1 4,210 Logged, not accumulated
//   e            Fri Oct 2, 4:30 PM    Concluded by Margaret Okonkwo; sign-off strip ✓ MO
//   f            10:15 AM              Approaching PM (illustrative): amber fill and AGGREGATE card
//   off          10:15 AM              `adjustments.entries` off: C-20
//   not_allowed  cole-hart             walled from Northwind: 404
//
// Dev and test only.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  AUD16_CARD,
  type Aud16Variant,
  aud16BelowCt,
  aud16Entries,
  aud16Preview,
  aud16Sum,
} from "../seed/aud16";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-28T10:15:00-05:00";
const AT_E = "2026-10-02T16:30:00-05:00";
const WI = "/v1/work-items/{work_item_id}";
const NOT_FOUND = { code: "not_found", message: "Not found." };

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return {
    ...base,
    flags: {
      ...base.flags,
      "audits.cockpit": true,
      "adjustments.entries": on,
    },
  };
}

function frame(
  state: string,
  options: { persona?: string; variant?: Aud16Variant; on?: boolean; clock?: string } = {},
): Scenario {
  const on = options.on ?? true;
  const variant = options.variant ?? "a";
  const walled = options.persona === "cole-hart";
  return {
    state,
    persona: options.persona ?? "hannah-leclerc",
    clock: options.clock ?? AT,
    get handlers(): Record<string, FixtureHandler> {
      const guard =
        (body: () => unknown): FixtureHandler =>
        () =>
          walled ? json(NOT_FOUND, 404) : json(body());
      return {
        ...E0.handlers,
        ...auditHandlers(seed, "run"),
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, on)),
        [`GET ${WI}/sum`]: guard(() => aud16Sum(variant)),
        [`GET ${WI}/proposed-entries`]: ({ query }) =>
          walled
            ? json(NOT_FOUND, 404)
            : json(aud16Entries(query.get("kind") === "rje" ? "rje" : "aje", variant)),
        [`GET ${WI}/misstatements`]: ({ query }) =>
          walled
            ? json(NOT_FOUND, 404)
            : query.get("view") === "below_ct"
              ? json(aud16BelowCt())
              : json({ items: [], total: 2 }),
        [`GET ${WI}/proposed-entries:send-preview`]: guard(() => aud16Preview()),
        [`POST ${WI}/proposed-entries:approve-and-send`]: () =>
          json(
            {
              approval_batch_id: "00000000-0000-4000-8000-0000000016b1",
              undo_until: "2026-09-28T15:15:10Z",
            },
            201,
          ),
        "POST /v1/approval-batches/{batch_id}/undo": ({ params }) =>
          json({ id: params.batch_id, label: "Undone: nothing reached the client" }),
        [`POST ${WI}/sum/request-conclusion`]: () => json({ decision_card_id: AUD16_CARD }, 201),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  b2: frame("b2", { variant: "b2" }),
  c: frame("c"),
  d: frame("d"),
  e: frame("e", { variant: "e", clock: AT_E }),
  f: frame("f", { variant: "f" }),
  off: frame("off", { on: false }),
  not_allowed: frame("not_allowed", { persona: "cole-hart" }),
});

export type Aud16State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud16State[];

/** The view each artboard opens on. */
export const VIEW_OF: Record<Aud16State, "proposed" | "reclass" | "passed" | "below_ct"> = {
  a: "passed",
  b: "proposed",
  b2: "proposed",
  c: "reclass",
  d: "below_ct",
  e: "passed",
  f: "passed",
  off: "passed",
  not_allowed: "passed",
};
