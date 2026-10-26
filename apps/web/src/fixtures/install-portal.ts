// The portal entry in fixture mode (P-08-T08): `?st=` picks a POR-01 scenario (a when absent) and
// `?as=` the persona, so `make dev-fixtures` can walk sign-in to the shell with no backend.
// Imported dynamically behind the compile-time VITE_FIXTURES flag: a production build holds none
// of it.
//
// F-04-T26 (J12-core): once signed in, the person lands on their home, so the persona's POR-02
// home (Claire a, Tess d, Meera e, Luis g, Marisol h) answers `GET /v1/portal/home`; anyone else keeps the sign-in
// scenario's answer.
//
// P-06-T25: `?scenario=POR-03:a` lays a portal screen's own scenario over that (its routes answer
// first), so a journey walks a portal screen whose routes only its scenarios answer yet.

import { type Scenario, installFixtureMode } from "../app-core/fixture-mode";
import { type Por01Scenario, scenarios } from "./scenarios/POR-01";
import { scenarios as homes } from "./scenarios/POR-02";

const HOME_OF: Readonly<Record<string, keyof typeof homes>> = {
  "claire-feld": "a",
  "tess-moreno": "d",
  "meera-shah": "e",
  "luis-ferrante": "g",
  "marisol-vega": "h",
};
const HOME = "GET /v1/portal/home";

// The portal screens' scenarios only (INV-4: nothing of the firm's), loaded on demand.
const PORTAL_SCENARIOS = import.meta.glob<{ scenarios?: Record<string, Scenario> }>([
  "./scenarios/POR-*.ts",
  "!./scenarios/*.test.ts",
]);

/** The portal screen scenario `?scenario=<POR-nn>:<state>` names, or undefined. */
export async function portalScenarioFromSearch(search: string): Promise<Scenario | undefined> {
  const named = new URLSearchParams(search).get("scenario");
  if (named === null) return undefined;
  const [screen = "", state = ""] = named.split(":");
  const load = PORTAL_SCENARIOS[`./scenarios/${screen}.ts`];
  if (load === undefined) throw new Error(`no portal fixture scenarios for ${screen}`);
  const found = (await load()).scenarios?.[state];
  if (found === undefined) throw new Error(`no scenario ${state} on ${screen}`);
  return found;
}

export function installPortalFixtures(search: string, screen?: Scenario): () => void {
  const params = new URLSearchParams(search);
  const st = params.get("st") ?? "a";
  const scenario = st in scenarios ? scenarios[st as Por01Scenario] : scenarios.a;
  const persona = params.get("as");
  const who = persona ?? scenario.persona ?? "";
  const key: keyof typeof homes | undefined = HOME_OF[who];
  const home = key === undefined ? undefined : homes[key].handlers[HOME];
  const base = home === undefined ? scenario.handlers : { ...scenario.handlers, [HOME]: home };
  const handlers = screen === undefined ? base : { ...screen.handlers };
  if (screen !== undefined) {
    for (const [route, handler] of Object.entries(base)) {
      if (!(route in handlers)) handlers[route] = handler;
    }
  }
  return installFixtureMode(
    { ...scenario, handlers, ...(screen?.clock === undefined ? {} : { clock: screen.clock }) },
    persona === null ? {} : { persona },
  );
}
