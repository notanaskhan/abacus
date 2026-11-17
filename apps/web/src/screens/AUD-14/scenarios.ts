// AUD-14 Confirmations (A-08-T29; SPEC-657 F7; handoff AUD-14): one fixture scenario per artboard
// on Granite Peak FY2026's confirmation log (`fixtures/seed/fieldwork.ts`). Fixture mode only.
//
//   a  Default: C3 Alpine Ridge exception with the drawer open (Tue Oct 6, 11:20 AM)
//   b  Authorization pending: C1 waiting on Luis Ferrante (SIG-02); C2 to C4 Draft (Sep 16)
//   c  Respondents viewed: C2 to C4 Sent, "Viewed Sep 19"; C1 sent over the network
//   d  Exception cleared: Hannah accepted the reconciliation; C3 Closed; Exception tile 0
//   e  Address not verified: a new confirmation with a client-only address; Send disabled
export const AUD14_SCENARIOS = ["a", "b", "c", "d", "e"] as const;
export type Aud14Scenario = (typeof AUD14_SCENARIOS)[number];
