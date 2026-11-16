// AUD-12 Testing workspace (A-08-T27; SPEC-657 F2, F3; handoff AUD-12): one fixture scenario per
// artboard, on the seed figures the A-08 kit draws (Granite Peak FY2026's JE testing, Northwind's
// participant tests). Fixture mode only; dev and test.
//
//   a  JE testing, 40 selected, JE-26-17994 open with its value chips (default)
//   b  Test of details, Northwind
//   c  Test of controls, the deviation log (0 deviations, UDL 8.8% < tolerable 10%)
//   d  Agent testing (rows running, the viewer loading)
//   e  Exception raised on JE-26-17950
//   f  Expand testing sheet (Selected becomes 50)
//   g  Awaiting approval (Hannah Leclerc), +10 pending
//   h  Expand testing, Northwind participants
export const AUD12_SCENARIOS = ["a", "b", "c", "d", "e", "f", "g", "h"] as const;
export type Aud12Scenario = (typeof AUD12_SCENARIOS)[number];

/** Each artboard's kit board state. */
export const KIT_STATE_OF = {
  a: "je",
  b: "details",
  c: "controls",
  d: "agent",
  e: "exception",
  f: "expand",
  g: "awaiting",
  h: "details",
} as const satisfies Record<Aud12Scenario, string>;
