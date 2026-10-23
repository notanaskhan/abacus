// Persona adapters (F-04-T21; F-04.32): how a journey becomes a persona in each Playwright project.
//
//   fixture    `make dev-fixtures` (VITE_FIXTURES=1), no Docker: `?as=<slug>&clock=<iso>` and the
//              page clock fixed at the scenario instant; the API is the in-page fixture, so there
//              is nothing to probe over HTTP.
//   fullstack  `make dev` + `make seed-demo` + fakes + the injected clock, never a hosted database:
//              the local OIDC server's chooser signs the persona in by name.
//   staging    the demo tenant: real WorkOS, codes from the staging sink.
//   canary     the production canary tenant: real clock, no loader.
//
// Staging and canary sign in through WorkOS with a code from the sink mailbox, which F-04-T22's
// `mail.latest()` reads; that task registers the sign-in with `registerHostedSignIn`. Until then an
// adapter for those projects says so instead of guessing. Nothing here holds a credential.
import { test, type Page } from "@playwright/test";
import { DEMO_INSTANT, type Persona } from "./personas";

export const HARNESS_PROJECTS = ["fixture", "fullstack", "staging", "canary"] as const;
export type HarnessProject = (typeof HARNESS_PROJECTS)[number];

export interface OpenOptions {
  /** The business instant a fixture journey stands at (ISO 8601 with an offset). */
  clock?: string;
}

export interface PersonaAdapter {
  project: HarnessProject;
  /** Open `path` as `persona`, signing in first where the project needs it. */
  open(page: Page, persona: Persona, path: string, options?: OpenOptions): Promise<void>;
  /** The HTTP status `path` (an API path, `/v1/...`) answers the signed-in persona, or null where
   * the project has no HTTP API (fixture). INV-3 and INV-4 probes go through here. */
  probe(page: Page, path: string): Promise<number | null>;
}

/** The harness project a test runs in, from the project's `metadata.harness`. */
export function harnessProject(): HarnessProject {
  const value = test.info().project.metadata.harness as unknown;
  if (typeof value === "string" && (HARNESS_PROJECTS as readonly string[]).includes(value)) {
    return value as HarnessProject;
  }
  throw new Error(
    `project "${test.info().project.name}" is not a harness project (fixture, fullstack, staging, canary)`,
  );
}

function withQuery(path: string, params: Record<string, string>): string {
  const [base = "/", query = ""] = path.split("?");
  const search = new URLSearchParams(query);
  for (const [k, v] of Object.entries(params)) search.set(k, v);
  return `${base}?${search.toString()}`;
}

/** With the SPA's own session (its sessionStorage token and tenant): the status `path` answers. */
async function probeInPage(page: Page, path: string): Promise<number> {
  const headers = await page.evaluate(() => {
    const read = (key: string): string | null => sessionStorage.getItem(key);
    const session = JSON.parse(read("abacus.session") ?? "null") as {
      accessToken?: string;
    } | null;
    const out: Record<string, string> = {};
    if (session?.accessToken !== undefined) out.Authorization = `Bearer ${session.accessToken}`;
    const tenant = read("abacus.tenant");
    if (tenant !== null) out["X-Abacus-Tenant"] = tenant;
    return out;
  });
  const response = await page.request.get(path, { headers, failOnStatusCode: false });
  return response.status();
}

const fixture: PersonaAdapter = {
  project: "fixture",
  async open(page, persona, path, options = {}) {
    const clock = options.clock ?? DEMO_INSTANT;
    await page.clock.setFixedTime(new Date(clock));
    // The fixture session (ch. 04 §6.5 "?as= replaces PKCE"): the in-page fixture API never reads
    // a token, so the SPA only needs to believe it is signed in. A placeholder, not a credential.
    await page.addInitScript(
      (until) => {
        sessionStorage.setItem(
          "abacus.session",
          JSON.stringify({ accessToken: "fixture-session", expiresAt: until }),
        );
      },
      Date.parse(clock) + 12 * 3_600_000,
    );
    await page.goto(withQuery(path, { as: persona.slug, clock }));
  },
  probe: () => Promise.resolve(null),
};

const fullstack: PersonaAdapter = {
  project: "fullstack",
  async open(page, persona, path) {
    await page.goto("/");
    const choose = page.getByRole("button", { name: new RegExp(`\\b${persona.name}\\b`) });
    if ((await choose.count()) > 0) {
      await choose.first().click();
      await page.getByText(persona.name).first().waitFor();
    }
    if (path !== "/") await page.goto(path);
  },
  probe: probeInPage,
};

export type HostedSignIn = (page: Page, persona: Persona) => Promise<void>;

const hostedSignIns = new Map<"staging" | "canary", HostedSignIn>();

/** F-04-T22 registers the WorkOS sign-in that reads the code from the sink (`mail.latest()`). */
export function registerHostedSignIn(project: "staging" | "canary", signIn: HostedSignIn): void {
  hostedSignIns.set(project, signIn);
}

function hosted(project: "staging" | "canary"): PersonaAdapter {
  return {
    project,
    async open(page, persona, path) {
      const signIn = hostedSignIns.get(project);
      if (signIn === undefined) {
        throw new Error(
          `${project}: no hosted sign-in registered; it needs the sink mailbox reader mail.latest() (F-04-T22)`,
        );
      }
      await signIn(page, persona);
      await page.goto(path);
    },
    probe: probeInPage,
  };
}

const ADAPTERS: Readonly<Record<HarnessProject, PersonaAdapter>> = {
  fixture,
  fullstack,
  staging: hosted("staging"),
  canary: hosted("canary"),
};

export function adapterFor(project: HarnessProject): PersonaAdapter {
  return ADAPTERS[project];
}
