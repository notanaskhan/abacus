// Loading the seed (F-04-T05): `VITE_FIXTURES=1` dev (main.tsx) and the /components gallery
// (gallery/fixture-mode.ts) both come here. Imported dynamically behind the compile-time
// VITE_FIXTURES flag, so a production build holds none of it.

import {
  installFixtureMode,
  json,
  type FixtureHandler,
  type Scenario,
} from "../app-core/fixture-mode";
import { sessionHandlers } from "./handlers";
import { seedScenario } from "./scenario";
import { getSeed } from "./seed";
import { capabilitiesFor } from "./seed/shell";

export interface SeedInstall {
  /** Persona slug (`?as=`); the scenario's default when absent. */
  persona?: string | undefined;
  /** ISO 8601 instant (`?clock=`); the demo instant when absent or unparseable. */
  clock?: string | undefined;
  /** Milliseconds added to every answer (`?latency=`). */
  latency?: string | number | undefined;
  /** Comma-separated flags the firm reads as on (`?flags=clients.v2,engagements.v2`): a journey
   * walks a screen built on fixtures whose flag E0 leaves off (P-07-T22). */
  flags?: string | undefined;
  /** A screen's scenario laid over the seed (`?scenario=BND-02:b`): its handlers answer first,
   * and its persona and clock stand unless `as` and `clock` say otherwise. */
  screen?: Scenario | undefined;
}

// The screens' fixture scenarios, loaded on demand (`?scenario=`), never their tests.
const SCREEN_SCENARIOS = import.meta.glob<{
  scenarios?: Record<string, Scenario>;
  OPENS?: Record<string, unknown>;
}>(["./scenarios/*.ts", "!./scenarios/*.test.ts"]);

export interface ScreenScenario {
  scenario: Scenario;
  /** What the state opens (its `OPENS` entry), flattened to `key → id` (`binderId`, `itemId`;
   * `id` where the entry is a bare id). */
  opens: Record<string, string>;
}

function flatten(value: unknown, key: string, out: Record<string, string>): void {
  if (typeof value === "string") out[key] = value;
  else if (typeof value === "object" && value !== null) {
    for (const [k, v] of Object.entries(value)) flatten(v, k, out);
  }
}

/** The screen scenario `?scenario=<SCREEN>:<state>` names (e.g. `BND-02:b`), or undefined. */
export async function screenScenarioFromSearch(
  search: string,
): Promise<ScreenScenario | undefined> {
  const named = new URLSearchParams(search).get("scenario");
  if (named === null) return undefined;
  const [screen = "", state = ""] = named.split(":");
  const load = SCREEN_SCENARIOS[`./scenarios/${screen}.ts`];
  if (load === undefined) throw new Error(`no fixture scenarios for ${screen}`);
  const module = await load();
  const found = module.scenarios?.[state];
  if (found === undefined) throw new Error(`no scenario ${state} on ${screen}`);
  const opens: Record<string, string> = {};
  flatten(module.OPENS?.[state], "id", opens);
  return { scenario: found, opens };
}

/** A path or query with `_<key>_` segments or values (`/binders/_binderId_?ov=request:new:_binderId_`)
 * resolved from what the scenario opens, so a journey names the record a scenario holds without
 * knowing its id. */
export function resolveOpens(url: string, opens: Readonly<Record<string, string>>): string {
  // Bounded by `/`, `=`, `?`, `&`, `:` or its escape `%3A` (`?ov=request:_requestId_:_binderId_`).
  const tokens = /(\/|=|:|%3A)_([A-Za-z]+)_(?=[/?&:]|%3A|$)/g;
  return url.replace(tokens, (token, lead: string, key: string) => {
    const id = opens[key];
    return id === undefined ? token : `${lead}${id}`;
  });
}

/** The screen's handlers first (they match first), then the seed's it does not answer. */
function overlay(
  screen: Scenario | undefined,
  seed: Record<string, FixtureHandler>,
): Record<string, FixtureHandler> {
  if (screen === undefined) return seed;
  const out = { ...screen.handlers };
  for (const [route, handler] of Object.entries(seed)) {
    if (!(route in out)) out[route] = handler;
  }
  return out;
}

const CAPABILITIES = "GET /v1/me/capabilities";

/** The capabilities handler with `flags` on, over whatever the scenario answers (the seed's
 * persona capabilities where it answers none). */
function withFlags(handler: FixtureHandler | undefined, flags: readonly string[]): FixtureHandler {
  return async (request) => {
    const response =
      handler === undefined
        ? json(capabilitiesFor(getSeed(), request.persona ?? ""))
        : await handler(request);
    if (!response.ok) return response;
    const body = (await response.json()) as { flags?: Record<string, unknown> };
    const on = Object.fromEntries(flags.map((flag) => [flag, true]));
    return json({ ...body, flags: { ...body.flags, ...on } });
  };
}

/** Route the generated client to the seed. Returns a function that restores real fetch. */
export function installSeedFixtures(options: SeedInstall = {}): () => void {
  const scenario = seedScenario();
  const screen = options.screen;
  const clock =
    options.clock !== undefined && !Number.isNaN(Date.parse(options.clock))
      ? options.clock
      : (screen?.clock ?? scenario.clock);
  const persona = options.persona ?? screen?.persona;
  const latencyMs = Number(options.latency);
  const flags = (options.flags ?? "")
    .split(",")
    .map((flag) => flag.trim())
    .filter((flag) => flag !== "");
  const handlers = { ...overlay(screen, scenario.handlers), ...sessionHandlers() };
  return installFixtureMode(
    {
      ...scenario,
      // P-01-T11: the shell refreshes a session on load; fixture mode always has one.
      handlers:
        flags.length === 0
          ? handlers
          : { ...handlers, [CAPABILITIES]: withFlags(handlers[CAPABILITIES], flags) },
      ...(clock === undefined ? {} : { clock }),
    },
    {
      ...(persona === undefined ? {} : { persona }),
      ...(Number.isFinite(latencyMs) && latencyMs > 0 ? { latencyMs } : {}),
    },
  );
}

/** The same, from a URL query string
 * (`?as=lena-park&clock=2026-09-14T09:41:00-05:00&latency=250&flags=clients.v2`), over the
 * screen scenario `?scenario=` named (`screenScenarioFromSearch`). */
export function installSeedFromSearch(search: string, screen?: Scenario): () => void {
  const params = new URLSearchParams(search);
  return installSeedFixtures({
    screen,
    persona: params.get("as") ?? undefined,
    clock: params.get("clock") ?? undefined,
    latency: params.get("latency") ?? undefined,
    flags: params.get("flags") ?? undefined,
  });
}
