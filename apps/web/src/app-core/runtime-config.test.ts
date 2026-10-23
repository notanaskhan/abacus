// docs/contracts/platform-ops.md section 3.2: the schema of `/runtime-config.json`, against the
// contract's own example, a missing file and malformed ones (Q-01-T50; Q-01-T23 extends it).
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  RUNTIME_CONFIG_PATH,
  type RuntimeConfig,
  loadRuntimeConfig,
  parseRuntimeConfig,
  telemetryTarget,
} from "./runtime-config";

const CONTRACT_EXAMPLE = {
  environment: "staging",
  oidc: { authority: "https://auth.example.test", client_id: "client_example" },
  sentry: { dsn: "https://key@o0.ingest.example.test/0" },
  release: "0123456789abcdef0123456789abcdef01234567",
  portal_base_domain: "portal.example.test",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("runtime-config.json schema (platform-ops section 3.2)", () => {
  it("accepts the contract's example and ignores unknown keys", () => {
    const config = parseRuntimeConfig({ ...CONTRACT_EXAMPLE, later_key: true });
    expect(config).toEqual(CONTRACT_EXAMPLE);
  });

  it("treats sentry as optional", () => {
    const withoutSentry: Partial<typeof CONTRACT_EXAMPLE> = { ...CONTRACT_EXAMPLE };
    delete withoutSentry.sentry;
    expect(parseRuntimeConfig(withoutSentry)?.sentry).toEqual({});
  });

  it("refuses a file with a required field missing or of the wrong type", () => {
    for (const broken of [
      null,
      [],
      "staging",
      { ...CONTRACT_EXAMPLE, environment: "dev" },
      { ...CONTRACT_EXAMPLE, release: "" },
      { ...CONTRACT_EXAMPLE, oidc: { authority: "https://auth.example.test" } },
      { ...CONTRACT_EXAMPLE, portal_base_domain: 3 },
      { ...CONTRACT_EXAMPLE, sentry: "https://key@o0.ingest.example.test/0" },
      { ...CONTRACT_EXAMPLE, sentry: { dsn: 7 } },
    ]) {
      expect(parseRuntimeConfig(broken), JSON.stringify(broken)).toBeNull();
    }
  });

  it("loads the file from this origin and answers null when it is missing or not JSON", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => Promise.resolve(Response.json(CONTRACT_EXAMPLE)));
    vi.stubGlobal("fetch", fetchMock);
    expect(await loadRuntimeConfig()).toEqual(CONTRACT_EXAMPLE);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(RUNTIME_CONFIG_PATH);

    vi.stubGlobal("fetch", () => Promise.resolve(new Response("not found", { status: 404 })));
    expect(await loadRuntimeConfig()).toBeNull();
    vi.stubGlobal("fetch", () =>
      Promise.resolve(new Response("<!doctype html>", { status: 200 })),
    );
    expect(await loadRuntimeConfig()).toBeNull();
    vi.stubGlobal("fetch", () => Promise.reject(new TypeError("offline")));
    expect(await loadRuntimeConfig()).toBeNull();
  });
});

describe("Q-01-T50 telemetryTarget", () => {
  const dsn = CONTRACT_EXAMPLE.sentry.dsn;
  const config = (sentry: Record<string, string>): RuntimeConfig => {
    const parsed = parseRuntimeConfig({ ...CONTRACT_EXAMPLE, sentry });
    if (parsed === null) throw new Error("the contract example should parse");
    return parsed;
  };

  it("reports only with both a DSN and a same-origin tunnel path", () => {
    expect(telemetryTarget(config({ dsn, tunnel: "/v1/telemetry/errors" }))).toEqual({
      dsn,
      tunnel: "/v1/telemetry/errors",
    });
    expect(telemetryTarget(config({ dsn }))).toBeNull();
    expect(telemetryTarget(config({ tunnel: "/v1/telemetry/errors" }))).toBeNull();
    expect(telemetryTarget(config({}))).toBeNull();
  });

  it("never sends to another origin", () => {
    for (const tunnel of [
      "https://o0.ingest.example.test/api/0/envelope/",
      "//evil.example.test/collect",
      "/\\evil.example.test",
      "v1/telemetry/errors",
    ]) {
      expect(telemetryTarget(config({ dsn, tunnel })), tunnel).toBeNull();
    }
  });
});
