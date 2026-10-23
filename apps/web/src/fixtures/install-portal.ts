// The portal entry in fixture mode (P-08-T08): `?st=` picks a POR-01 scenario (a when absent) and
// `?as=` the persona, so `make dev-fixtures` can walk sign-in to the shell with no backend.
// Imported dynamically behind the compile-time VITE_FIXTURES flag: a production build holds none
// of it.
//
// F-04-T26 (J12-core): once signed in, the person lands on their home, so the persona's POR-02
// home (Claire a, Tess d, Meera e) answers `GET /v1/portal/home`; anyone else keeps the sign-in
// scenario's answer.

import { installFixtureMode } from "../app-core/fixture-mode";
import { type Por01Scenario, scenarios } from "./scenarios/POR-01";
import { scenarios as homes } from "./scenarios/POR-02";

const HOME_OF: Readonly<Record<string, keyof typeof homes>> = {
  "claire-feld": "a",
  "tess-moreno": "d",
  "meera-shah": "e",
};
const HOME = "GET /v1/portal/home";

export function installPortalFixtures(search: string): () => void {
  const params = new URLSearchParams(search);
  const st = params.get("st") ?? "a";
  const scenario = st in scenarios ? scenarios[st as Por01Scenario] : scenarios.a;
  const persona = params.get("as");
  const who = persona ?? scenario.persona ?? "";
  const key: keyof typeof homes | undefined = HOME_OF[who];
  const home = key === undefined ? undefined : homes[key].handlers[HOME];
  const handlers = home === undefined ? scenario.handlers : { ...scenario.handlers, [HOME]: home };
  return installFixtureMode({ ...scenario, handlers }, persona === null ? {} : { persona });
}
