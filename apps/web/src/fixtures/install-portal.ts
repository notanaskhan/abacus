// The portal entry in fixture mode (P-08-T08): `?st=` picks a POR-01 scenario (a when absent) and
// `?as=` the persona, so `make dev-fixtures` can walk sign-in to the shell with no backend.
// Imported dynamically behind the compile-time VITE_FIXTURES flag: a production build holds none
// of it.

import { installFixtureMode } from "../app-core/fixture-mode";
import { type Por01Scenario, scenarios } from "./scenarios/POR-01";

export function installPortalFixtures(search: string): () => void {
  const params = new URLSearchParams(search);
  const st = params.get("st") ?? "a";
  const scenario = st in scenarios ? scenarios[st as Por01Scenario] : scenarios.a;
  const persona = params.get("as");
  return installFixtureMode(scenario, persona === null ? {} : { persona });
}
