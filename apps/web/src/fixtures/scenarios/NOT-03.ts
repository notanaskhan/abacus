// NOT-03 Response letter editor (N-04-T20; the handoff spec): the fixture scenarios on N1.
//
//   a    samuel-ito    Mon Sep 14, 10:02 AM  in review: DRAFT watermark, Approve…
//   b    daniel-reyes  10:14 AM              approved: Send for client signature…
//   c    samuel-ito    Sep 15                out for signature: read-only, the waiting strip
//   d    samuel-ito    Sep 16                ready to send: both signed, Direct Pay accepted
//   d2   samuel-ito    Sep 17                the Mark as sent sheet
//   e    samuel-ito    Sep 17                Awaiting IRS: follow-up Nov 16
//   f    samuel-ito    Dec 2                 resolved
//   g    samuel-ito    9:24 AM               approval blocked: waiting for the partner's decision
//
// Dev and test only.

import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { not02Activity, not02Analysis, not02Notice } from "../seed/not02";
import { type Not03Variant, not03Response } from "../seed/not03";

const E0 = seedScenario();

function frame(
  state: Not03Variant,
  persona = "samuel-ito",
  clock = "2026-09-14T10:02:00-05:00",
): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        "GET /v1/notices/{notice_id}": () => json(not02Notice("c", persona)),
        "GET /v1/notices/{notice_id}/analysis": () => json(not02Analysis("c")),
        "GET /v1/notices/{notice_id}/activity": () => json(not02Activity()),
        "GET /v1/notices/{notice_id}/response": () => json(not03Response(state)),
        "POST /v1/notices/{notice_id}/response/send-for-signature": () =>
          json({
            envelope_id: "00000000-0000-4000-8000-0000000000d3",
            confirmation_request_item_id: null,
          }),
        "POST /v1/notices/{notice_id}/response/mark-sent": () =>
          json({ sent_on: "2026-09-17", follow_up_on: "2026-11-16", confirmation_last4: "4821" }),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b", "daniel-reyes", "2026-09-14T10:14:00-05:00"),
  c: frame("c", "samuel-ito", "2026-09-15T10:02:00-05:00"),
  d: frame("d", "samuel-ito", "2026-09-16T10:02:00-05:00"),
  d2: frame("d2", "samuel-ito", "2026-09-17T10:02:00-05:00"),
  e: frame("e", "samuel-ito", "2026-09-17T10:02:00-05:00"),
  f: frame("f", "samuel-ito", "2026-12-02T10:02:00-06:00"),
  g: frame("g", "samuel-ito", "2026-09-14T09:24:00-05:00"),
});

export type Not03State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Not03State[];
