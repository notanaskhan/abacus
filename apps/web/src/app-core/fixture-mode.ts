import { client } from "@abacus/api-client/client";
import { setScenarioClock } from "./clock";

// Fixture mode (F-04-T04; ADR-143; chapter 04 §6.5): a screen renders from a scenario instead of
// the API. The generated client's `fetch` is swapped for a table of handlers keyed by OpenAPI
// path ("GET /v1/engagements/{engagement_id}"), so screens keep using the generated client
// unchanged. A scenario names its persona (`?as=`) and clock (`?clock=`), and `?latency=` slows
// every answer. Imported only from dev, test and gallery code: the production dist never holds it.

export interface FixtureRequest {
  method: string;
  path: string;
  params: Record<string, string>;
  query: URLSearchParams;
  body: unknown;
  persona: string | undefined;
  /** The request's headers (T-02-T24: `If-Match` for an autosave's version). */
  headers?: Headers;
}

export type FixtureHandler = (request: FixtureRequest) => Response | Promise<Response>;

export interface Scenario {
  /** The artboard state this scenario renders, e.g. "a". */
  state: string;
  /** The persona slug the screen is seen as, e.g. "hannah-leclerc". */
  persona?: string;
  /** The scenario's instant (ISO 8601 with an offset); the browser clock stands there. */
  clock?: string;
  handlers: Record<string, FixtureHandler>;
}

/** Typed scenarios for one screen, keyed by artboard state. */
export function defineScenarios<T extends Record<string, Scenario>>(scenarios: T): T {
  for (const [key, scenario] of Object.entries(scenarios)) {
    if (scenario.state !== key) throw new Error(`scenario ${key} says state ${scenario.state}`);
    for (const route of Object.keys(scenario.handlers)) {
      if (!/^(GET|POST|PUT|PATCH|DELETE) \/v1\//.test(route)) {
        throw new Error(`scenario ${key}: "${route}" is not "METHOD /v1/..."`);
      }
    }
  }
  return scenarios;
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** A response that never arrives: the screen stays in its loading state. */
export function never(): Promise<Response> {
  return new Promise<Response>(() => undefined);
}

interface CompiledRoute {
  method: string;
  pattern: RegExp;
  names: string[];
  handler: FixtureHandler;
}

/** The scenario's routes, the most specific first: a route with fewer `{param}` segments wins over
 * one that would also match (`/v1/tax-returns/summary` before `/v1/tax-returns/{return_id}`),
 * whatever order the handlers were spread in; ties keep their order. */
function compile(handlers: Record<string, FixtureHandler>): CompiledRoute[] {
  const routes = Object.entries(handlers).map(([key, handler]) => {
    const [method = "GET", template = "/"] = key.split(" ");
    const names: string[] = [];
    const source = template
      .replace(/[.*+?^$()|[\]\\]/g, "\\$&")
      .replace(/\{(\w+)\}/g, (_m, n: string) => {
        names.push(n);
        return "([^/]+)";
      });
    return { method, pattern: new RegExp(`^${source}$`), names, handler };
  });
  return routes
    .map((route, index) => ({ route, index }))
    .sort((a, b) => a.route.names.length - b.route.names.length || a.index - b.index)
    .map(({ route }) => route);
}

function bodyOf(text: string): unknown {
  if (text === "") return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

/** Route the generated client to the scenario. Returns a function that restores real fetch. */
export function installFixtureMode(
  scenario: Scenario,
  options: { latencyMs?: number; persona?: string } = {},
): () => void {
  const routes = compile(scenario.handlers);
  const persona = options.persona ?? scenario.persona;
  setScenarioClock(scenario.clock ?? null);
  const previous = client.getConfig().fetch ?? globalThis.fetch.bind(globalThis);
  const fixtureFetch = async (input: Request): Promise<Response> => {
    const url = new URL(input.url);
    const route = routes.find((r) => r.method === input.method && r.pattern.test(url.pathname));
    if (options.latencyMs) await sleep(options.latencyMs);
    if (route === undefined) return json({ detail: "no fixture for this route" }, 404);
    const match = route.pattern.exec(url.pathname) ?? [];
    const params = Object.fromEntries(
      route.names.map((n, i) => [n, decodeURIComponent(match[i + 1] ?? "")]),
    );
    return route.handler({
      method: input.method,
      path: url.pathname,
      params,
      query: url.searchParams,
      body: bodyOf(await input.clone().text()),
      headers: input.headers,
      persona,
    });
  };
  client.setConfig({ fetch: fixtureFetch as typeof fetch });
  return () => {
    setScenarioClock(null);
    client.setConfig({ fetch: previous });
  };
}
