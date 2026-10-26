// A built screen's own fixture scenario for the firm entry (G-01-T16; DEC-457): `make dev-fixtures`
// with `?screen=ADM-03&st=b` serves ADM-03's scenario b (its handlers, persona, clock and flags)
// instead of the plain E0 seed, so a fixture journey can walk a screen that sits behind a flag
// E0 leaves off, through the real route, as the portal entry's `?st=` already does (P-08-T08).
// When the URL carries no search of its own, the state's opening search (OPENS) is applied, as
// the /components gallery does. Fixture builds only: install.ts is behind VITE_FIXTURES.

import type { Scenario } from "../app-core/fixture-mode";
import { scenarios as adm01 } from "./scenarios/ADM-01";
import { OPENS as ADM02_OPENS, scenarios as adm02 } from "./scenarios/ADM-02";
import { OPENS as ADM03_OPENS, scenarios as adm03 } from "./scenarios/ADM-03";

interface ScreenScenarios {
  scenarios: Readonly<Record<string, Scenario>>;
  opens: Readonly<Record<string, string>>;
}

export const SCREEN_SCENARIOS: Readonly<Record<string, ScreenScenarios>> = {
  "ADM-01": { scenarios: adm01, opens: {} },
  "ADM-02": { scenarios: adm02, opens: ADM02_OPENS },
  "ADM-03": { scenarios: adm03, opens: ADM03_OPENS },
};

/** The fixture params the screen choice itself uses; anything else is the screen's own search. */
const OWN = new Set(["screen", "st", "as", "clock", "latency"]);

export interface ScreenChoice {
  scenario: Scenario;
  /** The state's opening search and anchor ("?expand=CHI#offshore"), or "" for none. */
  opens: string;
}

/** `?screen=<ID>&st=<state>` (state a when absent); null for no screen or an unknown one. */
export function screenScenario(search: string): ScreenChoice | null {
  const params = new URLSearchParams(search);
  const screen = SCREEN_SCENARIOS[params.get("screen") ?? ""];
  if (screen === undefined) return null;
  const st = params.get("st") ?? "a";
  const scenario = screen.scenarios[st];
  if (scenario === undefined) return null;
  return { scenario, opens: screen.opens[st] ?? "" };
}

/** The URL to open: `opens` merged in when the search names nothing but the fixture params. */
export function withOpens(pathname: string, search: string, hash: string, opens: string): string {
  const params = new URLSearchParams(search);
  const own = [...params.keys()].some((key) => !OWN.has(key));
  if (opens === "" || own) return `${pathname}${search}${hash}`;
  const [query = "", anchor = ""] = opens.replace(/^\?/, "").split("#");
  const merged = new URLSearchParams(query);
  for (const [key, value] of params) merged.set(key, value);
  const tail = anchor === "" ? hash : `#${anchor}`;
  return `${pathname}?${merged.toString()}${tail}`;
}
