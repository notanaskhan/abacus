// AUD-26 Review, compilation & preparation workspace (A-08-T31; SPEC-657 F9; handoff AUD-26): one
// fixture scenario per artboard. The mode comes from the engagement type (set at ENG-03), never
// chosen here. Fixture mode only.
//
//   a  Analytics: Lakeshore FY2026 review (AR-C 90); Grants over threshold, explained (default)
//   b  Inquiries: 11 of 14 answered; 3 "Requested Sep 10"; Send reminder… · Publish to portal
//   c  Compilation · Fenwick Family Foundation (AR-C 80)
//   d  Preparation · Juniper & Oak Interiors (AR-C 70): "No assurance is provided." on every page
//   e  Over threshold, unexplained: Grants amber with "Ask client…" (Sep 8, before the answer)
export const AUD26_SCENARIOS = ["a", "b", "c", "d", "e"] as const;
export type Aud26Scenario = (typeof AUD26_SCENARIOS)[number];

export type EngagementType = "ssars_review" | "ssars_compilation" | "ssars_preparation";

/** Each artboard's engagement (its type decides the mode). */
export const ENGAGEMENT_OF = {
  a: { name: "Lakeshore Literacy Alliance", type: "ssars_review" },
  b: { name: "Lakeshore Literacy Alliance", type: "ssars_review" },
  c: { name: "Fenwick Family Foundation", type: "ssars_compilation" },
  d: { name: "Juniper & Oak Interiors, LLC", type: "ssars_preparation" },
  e: { name: "Lakeshore Literacy Alliance", type: "ssars_review" },
} as const satisfies Record<Aud26Scenario, { name: string; type: EngagementType }>;
