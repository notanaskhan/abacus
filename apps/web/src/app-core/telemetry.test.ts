// Q-01-T50: browser errors leave through the tunnel with the route template and release, and
// with no breadcrumbs, user, URL query or DOM text. The tunnel route itself (Q-01-T48) is not
// needed: the SDK runs for real and `fetch` stands in for the network.
import {
  type ErrorEvent,
  addBreadcrumb,
  captureException,
  captureMessage,
  close,
  flush,
  setExtra,
  setUser,
} from "@sentry/browser";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RuntimeConfig } from "./runtime-config";
import { framePath, scrubEvent, startTelemetry, telemetryOptions } from "./telemetry";

const TUNNEL = "/v1/telemetry/errors";
const CONFIG: RuntimeConfig = {
  environment: "staging",
  oidc: { authority: "https://auth.example.test", client_id: "client_example" },
  sentry: { dsn: "https://key@o0.ingest.example.test/0", tunnel: TUNNEL },
  release: "0123456789abcdef0123456789abcdef01234567",
  portal_base_domain: "portal.example.test",
};
const ROUTE = "/engagements/$engagementId";
// Seeded values that must never leave the browser: an email, an SSN, a TIN, page text, a query.
const EMAIL = "jordan.lee@example.test";
const SSN = "987-65-4321"; // area 9xx: never issued (ADR-085)
const TIN = "12-3456789";
const PAGE_TEXT = "Copperleaf Holdings trial balance";
const QUERY = "token=abc123";
const SEEDED = [EMAIL, SSN, TIN, PAGE_TEXT, QUERY, "abc123"];

const SIGNED_IN = { Authorization: "Bearer test-token", "X-Abacus-Tenant": "tenant-1" };

let fetchMock: ReturnType<typeof vi.fn>;
let headers: Record<string, string> | null;

function hooks() {
  return { routeTemplate: () => ROUTE, sessionHeaders: () => headers };
}

function sentBodies(): string[] {
  return fetchMock.mock.calls.map((call) => {
    const body = (call[1] as RequestInit).body;
    return typeof body === "string" ? body : new TextDecoder().decode(body as Uint8Array);
  });
}

/** The event items of the sent envelopes (header line, item header, payload, ...). */
function sentEvents(): Record<string, unknown>[] {
  return sentBodies().flatMap((body) => {
    const lines = body.split("\n").filter((line) => line.length > 0);
    const events: Record<string, unknown>[] = [];
    for (let i = 1; i + 1 < lines.length; i += 2) {
      const item = JSON.parse(lines[i] ?? "{}") as { type?: string };
      if (item.type === "event") {
        events.push(JSON.parse(lines[i + 1] ?? "{}") as Record<string, unknown>);
      }
    }
    return events;
  });
}

function hostileError(): Error {
  const error = new Error(`${PAGE_TEXT} for ${EMAIL}, SSN ${SSN}, TIN ${TIN}`);
  error.stack = [
    `Error: ${PAGE_TEXT} for ${EMAIL}`,
    `    at render (https://acme.portal.example.test/assets/index-abc.js?${QUERY}:10:20)`,
    "    at commit (https://acme.portal.example.test/assets/vendor-def.js#frag:3:4)",
  ].join("\n");
  return error;
}

beforeEach(() => {
  headers = SIGNED_IN;
  fetchMock = vi.fn(() => Promise.resolve(new Response("", { status: 200 })));
  vi.stubGlobal("fetch", fetchMock);
  window.history.replaceState(null, "", `/engagements/e-1?${QUERY}&email=${EMAIL}`);
});

afterEach(async () => {
  await close();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("Q-01-T50 options", () => {
  it("leaves reporting off without a DSN or a tunnel", () => {
    expect(telemetryOptions({ ...CONFIG, sentry: {} }, hooks())).toBeNull();
    expect(
      telemetryOptions(
        { ...CONFIG, sentry: { dsn: "https://key@o0.ingest.example.test/0" } },
        hooks(),
      ),
    ).toBeNull();
    expect(startTelemetry({ ...CONFIG, sentry: { tunnel: TUNNEL } }, hooks())).toBe(false);
  });

  it("turns off breadcrumbs, default integrations and collected request data", () => {
    const options = telemetryOptions(CONFIG, hooks());
    expect(options?.tunnel).toBe(TUNNEL);
    expect(options?.release).toBe(CONFIG.release);
    expect(options?.environment).toBe("staging");
    expect(options?.maxBreadcrumbs).toBe(0);
    expect(options?.defaultIntegrations).toBe(false);
    const integrations = (options?.integrations ?? []) as { name: string }[];
    expect(integrations.map((i) => i.name).sort()).toEqual([
      "Dedupe",
      "GlobalHandlers",
      "LinkedErrors",
    ]);
    expect(options?.beforeBreadcrumb?.({ message: EMAIL })).toBeNull();
    expect(options?.dataCollection).toMatchObject({
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      urlQueryParams: false,
    });
  });
});

describe("Q-01-T50 scrubEvent allowlist", () => {
  it("keeps the error type, frames, route template and release, and nothing else", () => {
    const event = {
      type: undefined,
      event_id: "e1",
      timestamp: 1,
      platform: "javascript",
      level: "error",
      release: CONFIG.release,
      environment: "staging",
      message: EMAIL,
      user: { email: EMAIL, ip_address: "10.0.0.1" },
      breadcrumbs: [{ message: PAGE_TEXT }],
      request: { url: `https://acme.example.test/engagements/e-1?${QUERY}` },
      extra: { ssn: SSN },
      contexts: { page: { text: PAGE_TEXT } },
      tags: { tin: TIN },
      fingerprint: [EMAIL],
      exception: {
        values: [
          {
            type: "TypeError",
            value: `${PAGE_TEXT} ${EMAIL}`,
            mechanism: { type: "onerror", handled: false, data: { ssn: SSN } },
            stacktrace: {
              frames: [
                {
                  filename: `https://acme.example.test/assets/index.js?${QUERY}`,
                  function: "render",
                  lineno: 1,
                  colno: 2,
                  in_app: true,
                  context_line: PAGE_TEXT,
                  vars: { email: EMAIL },
                },
              ],
            },
          },
        ],
      },
    } as unknown as ErrorEvent;

    const scrubbed = scrubEvent(event, ROUTE);
    expect(scrubbed).toEqual({
      type: undefined,
      event_id: "e1",
      timestamp: 1,
      platform: "javascript",
      level: "error",
      release: CONFIG.release,
      environment: "staging",
      tags: { route: ROUTE },
      exception: {
        values: [
          {
            type: "TypeError",
            mechanism: { type: "onerror", handled: false },
            stacktrace: {
              frames: [
                {
                  filename: "/assets/index.js",
                  function: "render",
                  lineno: 1,
                  colno: 2,
                  in_app: true,
                },
              ],
            },
          },
        ],
      },
    });
    const text = JSON.stringify(scrubbed);
    for (const seeded of SEEDED) expect(text).not.toContain(seeded);
  });

  it("drops events that carry no exception or are not errors", () => {
    expect(scrubEvent({ type: undefined, message: EMAIL }, ROUTE)).toBeNull();
    const exception = { values: [{ type: "Error", value: EMAIL }] };
    expect(scrubEvent({ type: undefined, level: "info", exception }, ROUTE)).toBeNull();
    expect(scrubEvent({ type: undefined, level: "warning", exception }, ROUTE)).toBeNull();
    expect(scrubEvent({ type: undefined, level: "fatal", exception }, ROUTE)).not.toBeNull();
  });

  it("strips origin, query and fragment from frame paths", () => {
    expect(framePath(`https://acme.example.test/assets/a.js?${QUERY}#x`)).toBe("/assets/a.js");
    expect(framePath("/assets/a.js#x")).toBe("/assets/a.js");
    expect(framePath(undefined)).toBeUndefined();
  });
});

describe("Q-01-T50 through the tunnel", () => {
  it("posts a thrown error to the tunnel with the route template and release only", async () => {
    expect(startTelemetry(CONFIG, hooks())).toBe(true);
    setUser({ email: EMAIL, id: "u-1" });
    setExtra("ssn", SSN);
    addBreadcrumb({ message: PAGE_TEXT });
    captureException(hostileError());
    await flush(2000);

    expect(fetchMock).toHaveBeenCalled();
    for (const call of fetchMock.mock.calls) {
      expect(call[0]).toBe(TUNNEL);
      const init = call[1] as RequestInit;
      expect(init.method).toBe("POST");
      expect(init.headers).toMatchObject(SIGNED_IN);
    }
    const [event] = sentEvents();
    expect(event).toMatchObject({
      release: CONFIG.release,
      environment: "staging",
      tags: { route: ROUTE },
    });
    for (const key of ["user", "breadcrumbs", "request", "extra", "contexts", "message"]) {
      expect(event, key).not.toHaveProperty(key);
    }
    const body = sentBodies().join("\n");
    for (const seeded of SEEDED) expect(body, seeded).not.toContain(seeded);
  });

  it("sends nothing for a bare message", async () => {
    startTelemetry(CONFIG, hooks());
    captureMessage(`${PAGE_TEXT} ${EMAIL}`);
    await flush(2000);
    expect(sentEvents()).toEqual([]);
  });

  it("sends nothing when no one is signed in", async () => {
    headers = null;
    startTelemetry(CONFIG, hooks());
    captureException(hostileError());
    await flush(2000);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
