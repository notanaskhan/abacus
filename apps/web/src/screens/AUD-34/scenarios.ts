// AUD-34 (A-09-T31): one fixture scenario per artboard, as the handoff draws them.
//   a Blocked · partner view (default; Margaret Okonkwo, Mon 14 Sep 2026, 3:38 PM)
//   b Manager view (Omar Haddad, 3:10 PM): radios disabled, the banner, Remind Margaret
//   c Decided (3:40 PM): the one-line decision, PMs final, Draft component instructions…
//   d Proposing (Omar, 2:55 PM): the planned-work picker on Real Estate with the suggestion
//   e Coverage: the two bars full width with the per-component table
//   f Flag off (ff.group_audit)
export const AUD34_SCENARIOS = ["a", "b", "c", "d", "e", "f"] as const;
export type Aud34Scenario = (typeof AUD34_SCENARIOS)[number];

export interface Aud34State {
  manager: boolean;
  decided: boolean;
  picking: boolean;
  segment: "Components" | "Coverage" | "Aggregation";
}

export const AUD34_STATE: Record<Exclude<Aud34Scenario, "f">, Aud34State> = {
  a: { manager: false, decided: false, picking: false, segment: "Components" },
  b: { manager: true, decided: false, picking: false, segment: "Components" },
  c: { manager: false, decided: true, picking: false, segment: "Components" },
  d: { manager: true, decided: false, picking: true, segment: "Components" },
  e: { manager: false, decided: true, picking: false, segment: "Coverage" },
};
