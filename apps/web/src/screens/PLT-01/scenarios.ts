// PLT-01 Accrued tenant console (G-04-T14; handoff PLT-01): one fixture scenario per artboard,
// seen by Rowan Achebe on the production US console. Fixture mode only.
//
//   a  Tenants (default): 6 rows; 6 / 4 Healthy / 1 Degraded / 1 Onboarding / 404 of 490
//   b  Tenant drawer · Brightwater Hale LLP
//   c  Provision tenant… · Review (Ainsley Ward Partners)
//   d  Support session request · Kessling Mott LLP (no approve control)
//   e  Library releases (fixture-only; the nav item is absent in production until W-03)
//   f  Regions
//   g  Tenant created: the toast and the tinted row
export const PLT01_SCENARIOS = ["a", "b", "c", "d", "e", "f", "g"] as const;
export type Plt01Scenario = (typeof PLT01_SCENARIOS)[number];
