// Persona adapters (F-04-T21; F-04.32): how a journey becomes a persona in each Playwright project.
//
//   fixture    `make dev-fixtures` (VITE_FIXTURES=1), no Docker: `?as=<slug>&clock=<iso>` and the
//              page clock fixed at the scenario instant; the API is the in-page fixture, so there
//              is nothing to probe over HTTP.
//   fullstack  `make dev` + `make seed-demo` + fakes + the injected clock, never a hosted database:
//              the local OIDC server's chooser signs the persona in by name, or, for the
//              scenario's staff, the WorkOS fake's email code and authenticator (F-04-T27).
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
  /** Flags the firm reads as on, in the fixture project only (`?flags=`): a step walks a screen
   * built on fixtures whose flag E0 leaves off. The other projects read the firm's own flags. */
  flags?: readonly string[];
  /** A screen's own fixture scenario, in the fixture project only (`BND-02:b` becomes
   * `?screen=BND-02&st=b`, G-01-T16): a step walks a screen whose routes only its scenarios
   * answer yet. */
  scenario?: string;
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

/** `BND-02:b` as the firm entry's `?screen=BND-02&st=b`; nothing when no scenario is named. */
function screenParams(scenario: string | undefined): Record<string, string> {
  if (scenario === undefined) return {};
  const [screen = "", st = "a"] = scenario.split(":");
  return { screen, st };
}

function withQuery(path: string, params: Record<string, string>): string {
  // A fragment (`#link=…`, an emailed link's token) stays last, after the query.
  const [url = "/", fragment] = path.split("#");
  const [base = "/", query = ""] = url.split("?");
  const search = new URLSearchParams(query);
  for (const [k, v] of Object.entries(params)) search.set(k, v);
  return `${base}?${search.toString()}${fragment === undefined ? "" : `#${fragment}`}`;
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

/**
 * F-04-T26: a portal persona's entry path is the portal's own page (portal.html), as the portal
 * origin serves it (P-08-T07; DEC-59). The fixture server is the firm's vite dev server, which
 * answers every path with the firm entry, so the entry navigation is answered with portal.html;
 * the portal's router then reads the real path.
 */
async function servePortalEntry(page: Page, path: string): Promise<void> {
  const entry = path.split("?")[0] ?? "/";
  const html = await (await page.request.get("/portal.html")).text();
  await page.route(
    (url) => url.pathname === entry,
    (route) => route.fulfill({ status: 200, contentType: "text/html", body: html }),
  );
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
    if (persona.kind !== "staff") await servePortalEntry(page, path);
    const flags = options.flags ?? [];
    await page.goto(
      withQuery(path, {
        as: persona.slug,
        clock,
        ...(flags.length === 0 ? {} : { flags: flags.join(",") }),
        ...screenParams(options.scenario),
      }),
    );
  },
  probe: () => Promise.resolve(null),
};

/** A seat's work email, as the scenario writes it (people.py `email_of`). */
export function staffEmail(name: string): string {
  const [first = "", ...rest] = name.toLowerCase().split(" ");
  return `${first}.${rest.join("")}@brightwaterhale.com`;
}

async function harnessCode(page: Page, url: string): Promise<string> {
  const response = await page.request.get(url, { failOnStatusCode: true });
  const body = (await response.json()) as { code?: string | null };
  if (typeof body.code !== "string") throw new Error(`no sign-in code at ${url}`);
  return body.code;
}

/**
 * F-04-T27: the WorkOS fake's hosted email-code sign-in on the local sign-in server (SHL-06a →
 * b → c → g). The emailed code and the authenticator code come from the fake's harness readers,
 * which exist only on that local server.
 */
export async function signInWithEmailCode(page: Page, persona: Persona): Promise<void> {
  const email = staffEmail(persona.name);
  const idp = new URL(page.url()).origin;
  const query = `email=${encodeURIComponent(email)}`;
  await page.getByLabel("Work email").fill(email);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("heading", { name: "Check your email" }).waitFor();
  await page.getByLabel("Code").fill(await harnessCode(page, `${idp}/_harness/code?${query}`));
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("heading", { name: "Two-step verification" }).waitFor();
  const totp = await harnessCode(page, `${idp}/_harness/totp?${query}`);
  await page.getByLabel("Authenticator code").fill(totp);
  await page.getByRole("button", { name: "Verify" }).click();
  await page.waitForURL((url) => url.origin !== idp);
}

const fullstack: PersonaAdapter = {
  project: "fullstack",
  async open(page, persona, path) {
    await page.goto("/");
    const choose = page.getByRole("button", { name: new RegExp(`\\b${persona.name}\\b`) });
    if ((await choose.count()) > 0) {
      await choose.first().click();
      await page.getByText(persona.name).first().waitFor();
    } else if (persona.kind === "staff" && (await page.getByLabel("Work email").count()) > 0) {
      // The scenario's staff (make seed-demo) are not on the chooser: they sign in by email code.
      await signInWithEmailCode(page, persona);
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
