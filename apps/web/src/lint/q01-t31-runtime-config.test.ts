// @vitest-environment node
// Q-01-T31 (ADR-078): independent tests for the runtime config and auth config (Q-01-T23), from
// the acceptance text: "no authority or client ID is compiled into deployed bundles". Build once
// (ADR-088) promotes one bundle to every environment, so nothing environment-specific about
// sign-in may be written into the SPA's source or its build configuration: the identity provider
// is reached through the session BFF (P-01-T09, P-08-T06) and the public values come from
// `/runtime-config.json` (platform-ops contract 3.2). Same-session authorship (TASK-1238).
//
// Not here: "missing or malformed runtime config fails to a visible error state". Q-01-T23 (the
// boot gate) is not built: today a missing file leaves browser error reporting off and the app
// boots. That half waits for T23.
import { describe, expect, it } from "vitest";
import { WEB, list, read } from "./ui-files";

const SOURCE_DIRS = ["src"];
const BUILD_CONFIG = ["vite.config.ts", "index.html", "portal.html"];
// An identity-provider authority or client ID written as a literal, or read from build-time env.
const FORBIDDEN: readonly [string, RegExp][] = [
  ["a VITE_OIDC_* variable", /VITE_OIDC_[A-Z_]*/],
  ["a WorkOS host", /\b(?:api\.workos\.com|[a-z0-9-]+\.authkit\.app)\b/i],
  ["a WorkOS client ID", /\bclient_[0-9A-HJKMNP-TV-Z]{26}\b/],
  ["an OIDC discovery path", /\/\.well-known\/openid-configuration/],
];

function shipped(path: string): boolean {
  return (
    /\.(ts|tsx)$/.test(path) &&
    !/\.(test|spec)\.tsx?$/.test(path) &&
    !path.includes("fixtures/") &&
    !path.includes("lint/")
  );
}

async function sources(): Promise<[string, string][]> {
  const found: [string, string][] = [];
  for (const dir of SOURCE_DIRS) {
    for (const path of (await list(`${WEB}/${dir}`)).filter(shipped)) {
      found.push([`${dir}/${path}`, await read(`${WEB}/${dir}/${path}`)]);
    }
  }
  for (const path of BUILD_CONFIG) found.push([path, await read(`${WEB}/${path}`)]);
  return found;
}

describe("Q-01-T31: one bundle for every environment", () => {
  it("compiles no identity-provider authority or client ID into the SPA", async () => {
    const files = await sources();
    expect(files.length).toBeGreaterThan(50);
    const hits = files.flatMap(([path, text]) =>
      FORBIDDEN.filter(([, pattern]) => pattern.test(text)).map(([what]) => `${path}: ${what}`),
    );
    expect(hits).toEqual([]);
  });

  it("reads the environment's public values only from runtime-config.json", async () => {
    const config = await read(`${WEB}/src/app-core/runtime-config.ts`);
    expect(config).toContain('RUNTIME_CONFIG_PATH = "/runtime-config.json"');
    expect(config).toMatch(/cache: "no-store"/);
    const vite = await read(`${WEB}/vite.config.ts`);
    expect(vite).not.toMatch(/oidc|authority|client_id/i);
  });
});
