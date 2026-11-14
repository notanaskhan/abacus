// The trusts-and-estates scenario keys (T-07-T08; T-07 §5.3; docs/screens/TXT-01.md to TXT-04.md):
// 25 artboards and 6 composed states, each with its persona and snapshot. Each screen row
// (T-07-T15, T17, T25, T26) builds its `scenarios.ts` from these keys and the fixture seed; a
// composed state is fixture-only and never locked at Tier C.
export type TxtSnapshot = "e0" | "ready_to_release" | "released" | "estate" | "election";

export interface TxtScenarioKey {
  key: string;
  screen: "TXT-01" | "TXT-02" | "TXT-03" | "TXT-04";
  persona: "samuel-ito" | "kevin-osei" | "daniel-reyes";
  snapshot: TxtSnapshot;
  composed: boolean;
}

const k = (
  screen: TxtScenarioKey["screen"],
  letter: string,
  persona: TxtScenarioKey["persona"],
  snapshot: TxtSnapshot,
  composed = false,
): TxtScenarioKey => ({
  key: `${screen.toLowerCase().replace("-", "")}.${letter}`,
  screen,
  persona,
  snapshot,
  composed,
});

export const TXT_SCENARIO_KEYS: readonly TxtScenarioKey[] = [
  ...["a", "a2", "a3", "a4", "b", "c", "d"].map((l) => k("TXT-01", l, "samuel-ito", "e0")),
  ...["d1", "d2", "d3"].map((l) => k("TXT-01", l, "kevin-osei", "e0", true)),
  ...["a", "a2", "b", "c", "d", "e"].map((l) => k("TXT-02", l, "samuel-ito", "e0")),
  k("TXT-02", "f1", "samuel-ito", "e0", true),
  k("TXT-03", "a", "samuel-ito", "e0"),
  k("TXT-03", "a2", "samuel-ito", "ready_to_release"),
  k("TXT-03", "b", "samuel-ito", "released"),
  k("TXT-03", "c", "samuel-ito", "election"),
  k("TXT-03", "d", "samuel-ito", "e0"),
  k("TXT-03", "e", "samuel-ito", "e0"),
  k("TXT-03", "a3", "samuel-ito", "ready_to_release", true),
  ...["a", "b", "c", "d", "e", "f"].map((l) => k("TXT-04", l, "samuel-ito", "estate")),
  k("TXT-04", "c1", "daniel-reyes", "estate", true),
];
