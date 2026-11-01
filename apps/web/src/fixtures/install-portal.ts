// The portal entry in fixture mode (P-08-T08): `?st=` picks a POR-01 scenario (a when absent) and
// `?as=` the persona, so `make dev-fixtures` can walk sign-in to the shell with no backend.
// Imported dynamically behind the compile-time VITE_FIXTURES flag: a production build holds none
// of it.
//
// F-04-T26 (J12-core): once signed in, the person lands on their home, so the persona's POR-02
// home (Claire a, Tess d, Meera e, Luis g, Marisol h) answers `GET /v1/portal/home`; anyone else keeps the sign-in
// scenario's answer.
//
// R-01-T21 (J12 4, 5 and 15; J03 4c): the persona's documents answer too, so the journeys walk
// from home into Documents and the room on fixtures: Claire's Feld 2025 Binder (POR-03 a, with
// POR-04's 1095-C sheet), Dana Kowalski's Northwind requests (POR-03 i) and Sam Ortiz's Keystone
// room (POR-14 a). The sign-in scenario's own handlers win where both answer.
//
// A-02-T34 (j02 6, POR-16 reconnect): `?screen=POR-16&st=<state>` serves POR-16's own scenario
// (its handlers, persona and clock) instead, as the firm entry's `?screen=` does
// (screen-scenarios.ts), so a fixture journey walks /connections through the real route.

import { type Scenario, installFixtureMode } from "../app-core/fixture-mode";
import { type Por01Scenario, scenarios } from "./scenarios/POR-01";
import { scenarios as homes } from "./scenarios/POR-02";
import { scenarios as documents } from "./scenarios/POR-03";
import { scenarios as questions } from "./scenarios/POR-05";
import { scenarios as sign } from "./scenarios/POR-06";
import { scenarios as k1s } from "./scenarios/POR-13";
import { scenarios as rooms } from "./scenarios/POR-14";
import { scenarios as connections } from "./scenarios/POR-16";

const HOME_OF: Readonly<Record<string, keyof typeof homes>> = {
  "claire-feld": "a",
  "tess-moreno": "d",
  "meera-shah": "e",
  "luis-ferrante": "g",
  "marisol-vega": "h",
};
const HOME = "GET /v1/portal/home";
const SCREENS: Readonly<Record<string, Readonly<Record<string, Scenario>>>> = {
  "POR-05": questions, // T-02-T32: j06 2 walks /questions on POR-05's own states
  "POR-06": sign, // N-02-T40: the signature journeys walk /sign on POR-06's own states
  "POR-13": k1s, // T-02-T32: j07 8 and j08 16 walk /k1s on POR-13's own states
  "POR-16": connections,
};
const DOCUMENTS_OF: Readonly<Record<string, Scenario>> = {
  "claire-feld": documents.a,
  "dana-kowalski": documents.i,
  "sam-ortiz": rooms.a,
};

export function installPortalFixtures(search: string): () => void {
  const params = new URLSearchParams(search);
  const st = params.get("st") ?? "a";
  const persona = params.get("as");
  const screen = SCREENS[params.get("screen") ?? ""]?.[st];
  if (screen !== undefined) return installFixtureMode(screen, persona === null ? {} : { persona });
  const scenario = st in scenarios ? scenarios[st as Por01Scenario] : scenarios.a;
  const who = persona ?? scenario.persona ?? "";
  const key: keyof typeof homes | undefined = HOME_OF[who];
  const home = key === undefined ? undefined : homes[key].handlers[HOME];
  const own = { ...DOCUMENTS_OF[who]?.handlers, ...scenario.handlers };
  const handlers = home === undefined ? own : { ...own, [HOME]: home };
  return installFixtureMode({ ...scenario, handlers }, persona === null ? {} : { persona });
}
