// The local screen parity report (F-04-T33; F-04.34): every artboard of every screen the route
// registry marks `fixture` or `live`, rendered from the gallery at 1440 x 900, DPR 2, with
// `?frame=1&static=1&contrast=reference` (DEC-11) and compared with the handoff's cropped PNG for
// that artboard (`<screen><state>.window` in docs/design/parity-manifest.json, fetched into the
// git-ignored .visual/ by `pnpm visual:baselines`; no PNG is ever committed). Each row is attached
// as a "parity-screen" annotation; the reporter writes parity-report/screens/parity.json and
// index.html (artboard -> diff % -> tier -> locked).
//
// Gate: Tier A blocks; Tier B blocks once the contract says it is locked; Tier C is report-only;
// Tier D (the host frame's computed styles) is measured by e2e/visual/tier-d.spec.ts, which blocks
// in the visual project, and is listed here as unmeasured. An artboard with no baseline on disk is
// reported as unmeasured, never passed. Local only until S11 (F-04 §5 cut 1): `pnpm parity:screens`.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import {
  FIXED_TIME,
  TIERS,
  pngSize,
  readManifest,
  screenUrl,
  masked,
  shootWhole,
} from "../visual/support";
import {
  BUILT_PLANNED,
  judge,
  screenRows,
  statusesFromSource,
  type ScreenRow,
} from "./screen-rows";

const MANIFEST_DIR = "src/routes/manifest";
const MANIFEST = statusesFromSource(
  readdirSync(MANIFEST_DIR)
    .filter((f) => f.endsWith(".ts") && !["index.ts", "types.ts"].includes(f))
    .map((f) => readFileSync(`${MANIFEST_DIR}/${f}`, "utf8")),
);

function contractOf(screen: string): string | null {
  const path = `../../docs/screens/${screen}.md`;
  return existsSync(path) ? readFileSync(path, "utf8") : null;
}

const { rows, missing } = screenRows(MANIFEST, contractOf, BUILT_PLANNED);
const parity = readManifest();

/** Playwright's comparator, run strictly so the report carries the exact pixel count. */
function diffPixels(actual: Uint8Array, name: string, threshold: number): number | string {
  try {
    expect(actual).toMatchSnapshot(name, { threshold, maxDiffPixelRatio: 0 });
    return 0;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const sizes = /Expected an image \d+px by \d+px, received \d+px by \d+px/.exec(message);
    if (sizes !== null) return sizes[0];
    const counted = /(\d+) pixels \(ratio/.exec(message);
    if (counted?.[1] !== undefined) return Number(counted[1]);
    throw error;
  }
}

function annotate(info: { annotations: { type: string; description?: string }[] }, row: object) {
  info.annotations.push({ type: "parity-screen", description: JSON.stringify(row) });
}

// A built screen whose contract has no Parity table is listed in the report, not failed: the
// table is its screen epic's to write (each contract's "## Parity" section).
test("built screens without a Parity table are listed", ({}, testInfo) => {
  testInfo.annotations.push({
    type: "parity-screen-missing",
    description: JSON.stringify(missing),
  });
  expect(Array.isArray(missing)).toBe(true);
});

for (const row of rows) {
  test(`${row.artboard} at tier ${row.tier}`, async ({ page }, testInfo) => {
    const result = await measure(page, row, testInfo);
    annotate(testInfo, result);
    if (result.status === "unmeasured") test.skip(true, `${row.artboard}: ${result.note ?? ""}`);
    expect(result.status, `${row.artboard}: ${JSON.stringify(result)}`).not.toBe("failed");
  });
}

async function measure(
  page: import("@playwright/test").Page,
  row: ScreenRow,
  testInfo: import("@playwright/test").TestInfo,
) {
  if (row.tier === "D") return judge(row, null, 0, "computed styles: e2e/visual/tier-d.spec.ts");
  const name = `${row.baselineKey.replaceAll(".", "-")}.png`;
  if (parity[row.baselineKey] === undefined)
    return judge(row, null, 0, `no parity-manifest entry ${row.baselineKey}`);
  if (!existsSync(testInfo.snapshotPath(name)))
    return judge(row, null, 0, "no baseline: run pnpm visual:baselines");
  await page.clock.setFixedTime(FIXED_TIME);
  await page.goto(screenUrl(`screens/${row.screen}?st=${row.state}`));
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  // The entry's selector names the window inside the artboard when the board draws more than it
  // (a portal frame on its presentation ground, R-01-T31); otherwise the board is the window.
  const selector = parity[row.baselineKey]?.selector ?? `[data-artboard="${row.state}"]`;
  const board = page.locator(selector).first();
  // Masks paint the same boxes out of the render and its baseline (chapter 04's harness masks).
  const shot = await masked(
    page,
    board,
    parity[row.baselineKey]?.mask,
    await shootWhole(page, board),
    name,
    (n) => testInfo.snapshotPath(n),
  );
  const { width, height } = pngSize(shot.actual);
  const tier = TIERS[row.tier];
  const counted = diffPixels(shot.actual, shot.name, tier.threshold);
  // A different size fails a blocking row at any tier, as in parity.spec.ts.
  if (typeof counted === "string") return judge(row, 100, 0, counted);
  const percent = Math.round((counted / (width * height)) * 10_000) / 100;
  return judge(row, percent, tier.maxDiffPixelRatio * 100);
}
