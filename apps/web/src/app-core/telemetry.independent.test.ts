// Q-01-T53 (ADR-078): independent tests for browser error reporting (Q-01-T50), from the
// acceptance text: "browser payloads carry no URL query, user or breadcrumbs". Written against
// the module's public surface; the SDK runs for real and `fetch` stands in for the network.
// Same-session authorship in a solo lane (TASK-1238): independence is nominal.
import {
  type ErrorEvent,
  addBreadcrumb,
  captureException,
  close,
  flush,
  setContext,
  setTag,
  setUser,
} from "@sentry/browser";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RuntimeConfig } from "./runtime-config";
import { scrubEvent, startTelemetry, telemetryOptions } from "./telemetry";

const TUNNEL = "/v1/telemetry/errors";
const CONFIG: RuntimeConfig = {
  environment: "production",
  oidc: { authority: "https://auth.example.test", client_id: "client_example" },
  sentry: { dsn: "https://key@o0.ingest.example.test/0", tunnel: TUNNEL },
  release: "fedcba9876543210fedcba9876543210fedcba98",
  portal_base_domain: "portal.example.test",
};
const QUERY_SECRET = "reset_code=774411";
const USER_EMAIL = "sam.rivera@example.test";
const CRUMB = "Opened statement for account ending 5521";

let fetchMock: ReturnType<typeof vi.fn>;

function payloads(): string {
  return fetchMock.mock.calls
    .map((call) => {
      const body = (call[1] as RequestInit).body;
      return typeof body === "string" ? body : new TextDecoder().decode(body as Uint8Array);
    })
    .join("\n");
}

function eventItems(): Record<string, unknown>[] {
  const lines = payloads()
    .split("\n")
    .filter((line) => line.length > 0);
  const out: Record<string, unknown>[] = [];
  for (let i = 0; i + 1 < lines.length; i += 1) {
    const header = JSON.parse(lines[i] ?? "{}") as { type?: string };
    if (header.type === "event")
      out.push(JSON.parse(lines[i + 1] ?? "{}") as Record<string, unknown>);
  }
  return out;
}

beforeEach(() => {
  fetchMock = vi.fn(() => Promise.resolve(new Response("", { status: 200 })));
  vi.stubGlobal("fetch", fetchMock);
  window.history.replaceState(null, "", `/requests/r-9?${QUERY_SECRET}`);
});

afterEach(async () => {
  await close();
  setUser(null);
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("Q-01-T53: what a browser error payload may carry", () => {
  it("drops the URL and its query, the user and the breadcrumbs from an event", () => {
    const hostile: ErrorEvent = {
      type: undefined,
      level: "error",
      release: CONFIG.release,
      exception: {
        values: [
          {
            type: "TypeError",
            value: `failed at https://app.example.test/requests/r-9?${QUERY_SECRET}`,
            stacktrace: {
              frames: [
                { filename: `https://app.example.test/assets/a.js?${QUERY_SECRET}`, lineno: 1 },
              ],
            },
          },
        ],
      },
      request: {
        url: `https://app.example.test/requests/r-9?${QUERY_SECRET}`,
        query_string: QUERY_SECRET,
      },
      user: { email: USER_EMAIL, id: "user-1", ip_address: "203.0.113.9" },
      breadcrumbs: [{ message: CRUMB, category: "ui.click" }],
      extra: { note: CRUMB },
      contexts: { page: { url: `?${QUERY_SECRET}` } },
      tags: { tenant: "t-1" },
    };
    const kept = scrubEvent(hostile, "/requests/$requestId");
    expect(kept).not.toBeNull();
    const text = JSON.stringify(kept);
    for (const leaked of [QUERY_SECRET, "774411", USER_EMAIL, "203.0.113.9", CRUMB, "user-1"]) {
      expect(text, leaked).not.toContain(leaked);
    }
    for (const key of ["request", "user", "breadcrumbs", "extra", "contexts"]) {
      expect(kept, key).not.toHaveProperty(key);
    }
    expect(kept?.tags).toEqual({ route: "/requests/$requestId" });
  });

  it("asks the SDK for no breadcrumbs, no user data and no URL query at all", () => {
    const options = telemetryOptions(CONFIG, {
      routeTemplate: () => "/",
      sessionHeaders: () => ({ Authorization: "Bearer t" }),
    });
    expect(options).not.toBeNull();
    expect(options?.maxBreadcrumbs).toBe(0);
    expect(options?.beforeBreadcrumb?.({ message: CRUMB }, undefined)).toBeNull();
    expect(options?.dataCollection).toMatchObject({ userInfo: false, urlQueryParams: false });
  });

  it("sends a thrown error with a user, breadcrumbs and a query on the page, carrying none of them", async () => {
    expect(
      startTelemetry(CONFIG, {
        routeTemplate: () => "/requests/$requestId",
        sessionHeaders: () => ({ Authorization: "Bearer t" }),
      }),
    ).toBe(true);
    setUser({ email: USER_EMAIL, id: "user-1" });
    setTag("email", USER_EMAIL);
    setContext("page", { href: window.location.href });
    addBreadcrumb({ message: CRUMB });
    captureException(new TypeError(`could not load ?${QUERY_SECRET}`));
    await flush(2000);

    const [event] = eventItems();
    expect(event).toBeDefined();
    expect(event).toMatchObject({ release: CONFIG.release, environment: "production" });
    for (const key of ["user", "breadcrumbs", "request"])
      expect(event, key).not.toHaveProperty(key);
    const body = payloads();
    for (const leaked of [QUERY_SECRET, "774411", USER_EMAIL, CRUMB]) {
      expect(body, leaked).not.toContain(leaked);
    }
    expect(fetchMock.mock.calls.every((call) => call[0] === TUNNEL)).toBe(true);
  });
});
