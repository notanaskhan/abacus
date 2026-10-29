// Fixture-versus-live drift (Q-03-T061; chapter 10 §10.4): every route fixture mode answers is a
// route the OpenAPI document has (stubs included), so a fixture can never serve an endpoint the API
// will not. Read from the fixture sources (`"METHOD /v1/…"` handler keys) and the generated
// document; the quality report counts the same thing (abacus_tools.quality.report). A route still
// ahead of its contract is listed here by name with its defect, and the list must shrink: an
// entry whose route has since landed fails until it is removed.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const SPEC = JSON.parse(
  readFileSync(
    join(here, "..", "..", "..", "..", "packages", "api-client", "openapi.json"),
    "utf8",
  ),
) as { paths: Record<string, Record<string, unknown>> };

const SOURCES = import.meta.glob<string>(["./**/*.ts", "../app-core/**/*.ts", "!./**/*.test.ts"], {
  query: "?raw",
  import: "default",
  eager: true,
});

/** Routes fixture mode answers ahead of their contract, each with its defect (ED-270 …). */
const KNOWN_DRIFT: Readonly<Record<string, string>> = {
  "PUT /v1/engagements/{}/auto-mode": "ED-270: P-10-T39 serves it (AUD-02 f, DEC-405)",
};

const shape = (path: string): string => path.replace(/\{[^}]+\}/g, "{}");
const METHODS = ["get", "post", "put", "patch", "delete"];

function live(): Set<string> {
  const found = new Set<string>();
  for (const [path, ops] of Object.entries(SPEC.paths)) {
    for (const method of Object.keys(ops)) {
      if (METHODS.includes(method)) found.add(`${method.toUpperCase()} ${shape(path)}`);
    }
  }
  return found;
}

function answered(): Map<string, string> {
  const found = new Map<string, string>();
  const KEY = /["'`](GET|POST|PUT|PATCH|DELETE) (\/v1\/[a-z][A-Za-z0-9_{}./-]*)["'`]/g;
  for (const [file, source] of Object.entries(SOURCES)) {
    for (const match of source.matchAll(KEY)) {
      const [, method = "", path = ""] = match;
      found.set(`${method} ${shape(path)}`, file);
    }
  }
  return found;
}

describe("fixture-versus-live drift", () => {
  it("fixture mode answers only routes the OpenAPI document has", () => {
    const routes = live();
    const drift = [...answered().entries()]
      .filter(([route]) => !routes.has(route) && !(route in KNOWN_DRIFT))
      .map(([route, file]) => `${route} (${file})`);
    expect(drift).toEqual([]);
  });

  it("each known drift is still ahead of its contract (remove it once its route lands)", () => {
    const routes = live();
    const landed = Object.keys(KNOWN_DRIFT).filter((route) => routes.has(route));
    expect(landed).toEqual([]);
  });
});
