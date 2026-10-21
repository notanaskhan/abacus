// Loading the seed (F-04-T05): `VITE_FIXTURES=1` dev (main.tsx) and the /components gallery
// (gallery/fixture-mode.ts) both come here. Imported dynamically behind the compile-time
// VITE_FIXTURES flag, so a production build holds none of it.

import { installFixtureMode } from "../app-core/fixture-mode";
import { seedScenario } from "./scenario";

export interface SeedInstall {
  /** Persona slug (`?as=`); the scenario's default when absent. */
  persona?: string | undefined;
  /** ISO 8601 instant (`?clock=`); the demo instant when absent or unparseable. */
  clock?: string | undefined;
  /** Milliseconds added to every answer (`?latency=`). */
  latency?: string | number | undefined;
}

/** Route the generated client to the seed. Returns a function that restores real fetch. */
export function installSeedFixtures(options: SeedInstall = {}): () => void {
  const scenario = seedScenario();
  const clock =
    options.clock !== undefined && !Number.isNaN(Date.parse(options.clock))
      ? options.clock
      : scenario.clock;
  const latencyMs = Number(options.latency);
  return installFixtureMode(
    { ...scenario, ...(clock === undefined ? {} : { clock }) },
    {
      ...(options.persona === undefined ? {} : { persona: options.persona }),
      ...(Number.isFinite(latencyMs) && latencyMs > 0 ? { latencyMs } : {}),
    },
  );
}

/** The same, from a URL query string (`?as=lena-park&clock=2026-09-14T09:41:00-05:00&latency=250`). */
export function installSeedFromSearch(search: string): () => void {
  const params = new URLSearchParams(search);
  return installSeedFixtures({
    persona: params.get("as") ?? undefined,
    clock: params.get("clock") ?? undefined,
    latency: params.get("latency") ?? undefined,
  });
}
