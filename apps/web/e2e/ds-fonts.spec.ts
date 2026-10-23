// SPEC-048 AC-7 (F-05-T08, written from the spec before F-05-T04's fonts): fonts are self-hosted.
// Loading a page makes no request to fonts.googleapis.com or fonts.gstatic.com, Geist at 500 is
// available, Geist is served from this origin, Arimo and Gelasio stay out of the app shell (they
// load only in document chunks), and the `abacus-csp` policy in vite.config.ts is unchanged.
// Runs against the fixtures stack with no database: `make dev-fixtures`, then `make e2e`.
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

// The policy, line for line, as the security review fixed it (TASK-012). A font host added here
// would also have to be added to the CSP, so this doubles as the "CSP meta unchanged" check.
const EXPECTED_POLICY = [
  `"default-src 'self'"`,
  `"script-src 'self'"`,
  `"style-src 'self'"`,
  `"img-src 'self' data:"`,
  `"connect-src 'self'"`,
  `"frame-ancestors 'none'"`,
  `"object-src 'none'"`,
  `"base-uri 'none'"`,
  `"form-action 'self'"`,
];

test("ac7 no request goes to Google Fonts, and Geist 500 is available", async ({ page }) => {
  const requested: string[] = [];
  page.on("request", (request) => requested.push(request.url()));

  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.evaluate(async () => {
    await document.fonts.ready;
  });

  expect(requested.filter((u) => /fonts\.googleapis\.com|fonts\.gstatic\.com/.test(u))).toEqual(
    [],
  );
  expect(await page.evaluate(() => document.fonts.check("500 13px Geist"))).toBe(true);
});

test("ac7 Geist is served from this origin; Arimo and Gelasio wait for a document", async ({
  page,
  baseURL,
}) => {
  const fonts: string[] = [];
  page.on("request", (request) => {
    if (/\.(woff2?|ttf|otf)(\?|$)/.test(request.url())) fonts.push(request.url());
  });

  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.evaluate(async () => {
    await document.fonts.ready;
  });

  // `document.fonts.check` is also true when no face matches, so require a loaded Geist face.
  const loaded = await page.evaluate(() =>
    [...document.fonts]
      .filter((face) => face.status === "loaded")
      .map((face) => face.family.replaceAll('"', "")),
  );
  expect(loaded).toContain("Geist");

  const origin = new URL(baseURL ?? "http://localhost").origin;
  expect(fonts.length).toBeGreaterThan(0);
  expect(fonts.filter((u) => !u.startsWith(origin))).toEqual([]);
  expect(fonts.filter((u) => /arimo|gelasio/i.test(u))).toEqual([]);
});

test("ac7 the abacus-csp policy in vite.config.ts is unchanged", () => {
  const source = readFileSync("vite.config.ts", "utf8");
  const match = /const policy = \[([\s\S]*?)\]\.join\("; "\)/.exec(source);
  const lines = (match?.[1] ?? "")
    .split("\n")
    .map((line) => line.trim().replace(/,$/, ""))
    .filter((line) => line !== "");
  expect(lines).toEqual(EXPECTED_POLICY);
  expect(source).not.toMatch(/fonts\.googleapis\.com|fonts\.gstatic\.com/);
});
