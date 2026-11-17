// AUD-13 Analytics (A-08-T28; SPEC-657; handoff AUD-13): one fixture scenario per artboard on
// Granite Peak FY2026's seed figures (`fixtures/seed/fieldwork.ts`). Fixture mode only.
//
//   a  Preliminary · 2 unexplained (default): 14 lines, 8 over, 6 explained, 2 unexplained
//   b  Agent running: three run rows, tallies "Pending" (Sun Sep 13, 5:36 PM)
//   c  Ask client: the O3 sheet with two question cards for Luis Ferrante (POR-05)
//   d  Answered: inventory explained by the client answer of Sep 16, with Accept
//   e  Final analytics: adjusted FY2026 vs audited FY2025 after 3 recorded adjustments
//   s  Substantive tab (DF-05, composed from the preliminary grammar; never locked)
export const AUD13_SCENARIOS = ["a", "b", "c", "d", "e", "s"] as const;
export type Aud13Scenario = (typeof AUD13_SCENARIOS)[number];

export type Aud13Stage = "preliminary" | "substantive" | "final";

export const STAGE_OF = {
  a: "preliminary",
  b: "preliminary",
  c: "preliminary",
  d: "preliminary",
  e: "final",
  s: "substantive",
} as const satisfies Record<Aud13Scenario, Aud13Stage>;
