// A built screen's own fixture scenario for the firm entry (G-01-T16; DEC-457): `make dev-fixtures`
// with `?screen=ADM-03&st=b` serves ADM-03's scenario b (its handlers, persona, clock and flags)
// instead of the plain E0 seed, so a fixture journey can walk a screen that sits behind a flag
// E0 leaves off, through the real route, as the portal entry's `?st=` already does (P-08-T08).
// When the URL carries no search of its own, the state's opening search (OPENS) is applied, as
// the /components gallery does. Fixture builds only: install.ts is behind VITE_FIXTURES.
//
// P-06-T25 and P-01-T16 add the binder, request and shell screens their journeys walk. A state that
// opens a record names its ids (`ids`, from the scenario's OPENS), and a `_key_` path segment or
// query value (`/binders/_binderId_?ov=request:new:_binderId_`) resolves to them, so a journey
// opens the record a scenario holds without knowing its id.

import type { Scenario } from "../app-core/fixture-mode";
import { scenarios as adm01 } from "./scenarios/ADM-01";
import { OPENS as ADM02_OPENS, scenarios as adm02 } from "./scenarios/ADM-02";
import { OPENS as ADM03_OPENS, scenarios as adm03 } from "./scenarios/ADM-03";
import { OPENS as ADM06_OPENS, scenarios as adm06 } from "./scenarios/ADM-06";
import { OPENS as ADM07_OPENS, scenarios as adm07 } from "./scenarios/ADM-07";
import { scenarios as aud01 } from "./scenarios/AUD-01";
import { IDS as AUD03_IDS, scenarios as aud03 } from "./scenarios/AUD-03";
import { scenarios as bnd01 } from "./scenarios/BND-01";
import { OPENS as BND02_OPENS, scenarios as bnd02 } from "./scenarios/BND-02";
import { OPENS as CLI04_OPENS, scenarios as cli04 } from "./scenarios/CLI-04";
import { OPENS as CLI07_OPENS, scenarios as cli07 } from "./scenarios/CLI-07";
import {
  CLIENT_ID as CLI08_CLIENT,
  ENGAGEMENT_ID as CLI08_ENGAGEMENT,
  scenarios as cli08,
} from "./scenarios/CLI-08";
import { scenarios as home01 } from "./scenarios/HOME-01";
import { scenarios as knw01 } from "./scenarios/KNW-01";
import { scenarios as shl03 } from "./scenarios/SHL-03";
import { scenarios as shl04 } from "./scenarios/SHL-04";
import { OPENS as SHL14_OPENS, scenarios as shl14 } from "./scenarios/SHL-14";

type Ids = Readonly<Record<string, string>>;

/** Per state, the client (and engagement) a P-07 screen opens (P-07-T53's gates and access walk). */
function idsOf<S extends string>(
  states: Readonly<Record<S, unknown>>,
  of: (state: S) => Readonly<Record<string, string>>,
): Readonly<Record<string, Readonly<Record<string, string>>>> {
  return Object.fromEntries((Object.keys(states) as S[]).map((s) => [s, of(s)]));
}

interface ScreenScenarios {
  scenarios: Readonly<Record<string, Scenario>>;
  opens: Readonly<Record<string, string>>;
  /** Per state, the ids of the records it opens (`binderId`, `requestId`). */
  ids?: Readonly<Record<string, Readonly<Record<string, string | null>>>>;
}

export const SCREEN_SCENARIOS: Readonly<Record<string, ScreenScenarios>> = {
  "ADM-01": { scenarios: adm01, opens: {} },
  "ADM-02": { scenarios: adm02, opens: ADM02_OPENS },
  "ADM-03": { scenarios: adm03, opens: ADM03_OPENS },
  "ADM-06": { scenarios: adm06, opens: ADM06_OPENS }, // G-02-T16
  "ADM-07": { scenarios: adm07, opens: ADM07_OPENS }, // G-02-T13
  "AUD-01": { scenarios: aud01, opens: {} }, // A-01-T26: j03 6, j04 1
  "AUD-03": { scenarios: aud03, opens: {}, ids: AUD03_IDS }, // A-01-T26: j03 4e, 5, 5c
  "BND-01": { scenarios: bnd01, opens: {} },
  "BND-02": { scenarios: bnd02, opens: {}, ids: BND02_OPENS },
  // P-07-T53: the gates and access walk opens the live routes on the screens' own states.
  "CLI-04": {
    scenarios: cli04,
    opens: {},
    ids: idsOf(CLI04_OPENS, (s) => ({ clientId: CLI04_OPENS[s] })),
  },
  "CLI-07": { scenarios: cli07, opens: {}, ids: idsOf(CLI07_OPENS, (s) => CLI07_OPENS[s]) },
  "CLI-08": {
    scenarios: cli08,
    opens: {},
    ids: idsOf(cli08, () => ({ clientId: CLI08_CLIENT, engagementId: CLI08_ENGAGEMENT })),
  },
  "HOME-01": { scenarios: home01, opens: {} }, // I-01-T05
  "KNW-01": { scenarios: knw01, opens: {} }, // K-01-T04
  "SHL-03": { scenarios: shl03, opens: {} },
  "SHL-04": { scenarios: shl04, opens: {} },
  "SHL-14": { scenarios: shl14, opens: {}, ids: SHL14_OPENS },
};

/** The fixture params the screen choice itself uses; anything else is the screen's own search. */
const OWN = new Set(["screen", "st", "as", "clock", "latency", "flags"]);

export interface ScreenChoice {
  scenario: Scenario;
  /** The state's opening search and anchor ("?expand=CHI#offshore"), or "" for none. */
  opens: string;
  /** The ids the state opens, by key; `_key_` in the URL resolves to them (`withIds`). */
  ids: Ids;
}

/** `?screen=<ID>&st=<state>` (state a when absent); null for no screen or an unknown one. */
export function screenScenario(search: string): ScreenChoice | null {
  const params = new URLSearchParams(search);
  const screen = SCREEN_SCENARIOS[params.get("screen") ?? ""];
  if (screen === undefined) return null;
  const st = params.get("st") ?? "a";
  const scenario = screen.scenarios[st];
  if (scenario === undefined) return null;
  const ids = Object.fromEntries(
    Object.entries(screen.ids?.[st] ?? {}).filter(
      (entry): entry is [string, string] => typeof entry[1] === "string",
    ),
  );
  return { scenario, opens: screen.opens[st] ?? "", ids };
}

/** The URL with each `_key_` path segment or query value (bounded by `/`, `=`, `?`, `&`, `:` or
 * its escape `%3A`) replaced by the id the state opens under that key; unknown keys stay. */
export function withIds(url: string, ids: Ids): string {
  const tokens = /(\/|=|:|%3A)_([A-Za-z]+)_(?=[/?&:#]|%3A|$)/g;
  return url.replace(tokens, (token, lead: string, key: string) => {
    const id = ids[key];
    return id === undefined ? token : `${lead}${id}`;
  });
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
