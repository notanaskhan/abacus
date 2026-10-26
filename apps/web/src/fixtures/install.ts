// Loading the seed (F-04-T05): `VITE_FIXTURES=1` dev (main.tsx) and the /components gallery
// (gallery/fixture-mode.ts) both come here. Imported dynamically behind the compile-time
// VITE_FIXTURES flag, so a production build holds none of it.

import { type Scenario, installFixtureMode } from "../app-core/fixture-mode";
import { sessionHandlers } from "./handlers";
import { seedScenario } from "./scenario";
import { screenScenario, withOpens } from "./screen-scenarios";

export interface SeedInstall {
  /** Persona slug (`?as=`); the scenario's default when absent. */
  persona?: string | undefined;
  /** ISO 8601 instant (`?clock=`); the demo instant when absent or unparseable. */
  clock?: string | undefined;
  /** Milliseconds added to every answer (`?latency=`). */
  latency?: string | number | undefined;
}

/** Route the generated client to the seed (or to `base`, a screen's own scenario built on it).
 * Returns a function that restores real fetch. */
export function installSeedFixtures(
  options: SeedInstall = {},
  base: Scenario = seedScenario(),
): () => void {
  const scenario = base;
  const clock =
    options.clock !== undefined && !Number.isNaN(Date.parse(options.clock))
      ? options.clock
      : scenario.clock;
  const latencyMs = Number(options.latency);
  return installFixtureMode(
    {
      ...scenario,
      // P-01-T11: the shell refreshes a session on load; fixture mode always has one.
      handlers: { ...scenario.handlers, ...sessionHandlers() },
      ...(clock === undefined ? {} : { clock }),
    },
    {
      ...(options.persona === undefined ? {} : { persona: options.persona }),
      ...(Number.isFinite(latencyMs) && latencyMs > 0 ? { latencyMs } : {}),
    },
  );
}

/** The same, from a URL query string (`?as=lena-park&clock=2026-09-14T09:41:00-05:00&latency=250`).
 * `?screen=ADM-03&st=b` serves that screen's scenario instead (G-01-T16; screen-scenarios.ts)
 * and, in a browser, opens the state's search when the URL has none of its own. */
export function installSeedFromSearch(search: string): () => void {
  const params = new URLSearchParams(search);
  const options = {
    persona: params.get("as") ?? undefined,
    clock: params.get("clock") ?? undefined,
    latency: params.get("latency") ?? undefined,
  };
  const screen = screenScenario(search);
  if (screen === null) return installSeedFixtures(options);
  if (typeof window !== "undefined" && window.location.search === search) {
    const { pathname, hash } = window.location;
    const next = withOpens(pathname, search, hash, screen.opens);
    if (next !== `${pathname}${search}${hash}`) window.history.replaceState(null, "", next);
  }
  return installSeedFixtures(options, screen.scenario);
}
