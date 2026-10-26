// Loading the seed (F-04-T05): `VITE_FIXTURES=1` dev (main.tsx) and the /components gallery
// (gallery/fixture-mode.ts) both come here. Imported dynamically behind the compile-time
// VITE_FIXTURES flag, so a production build holds none of it.

import { installFixtureMode, json, type FixtureHandler } from "../app-core/fixture-mode";
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
  const clock =
    options.clock !== undefined && !Number.isNaN(Date.parse(options.clock))
      ? options.clock
      : scenario.clock;
  const latencyMs = Number(options.latency);
  const flags = (options.flags ?? "")
    .split(",")
    .map((flag) => flag.trim())
    .filter((flag) => flag !== "");
  const handlers = { ...scenario.handlers, ...sessionHandlers() };
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
      ...(options.persona === undefined ? {} : { persona: options.persona }),
      ...(Number.isFinite(latencyMs) && latencyMs > 0 ? { latencyMs } : {}),
    },
  );
}

/** The same, from a URL query string
 * (`?as=lena-park&clock=2026-09-14T09:41:00-05:00&latency=250&flags=clients.v2`). */
export function installSeedFromSearch(search: string): () => void {
  const params = new URLSearchParams(search);
  return installSeedFixtures({
    persona: params.get("as") ?? undefined,
    clock: params.get("clock") ?? undefined,
    latency: params.get("latency") ?? undefined,
    flags: params.get("flags") ?? undefined,
  });
}
