// Tier A to C: gallery specimens against the cropped handoff PNGs (F-05-T16; chapter 04 §9.3).
// One test per manifest entry. The baselines are the handoff's own pixels, cropped by
// `python -m abacus_tools.parity.crop_handoff` and fetched by `pnpm visual:baselines`; they are
// never committed (D-DS-12), so an entry with no baseline on disk is skipped and says so. Each run
// records `artboard -> diff % -> tier` in parity-report/parity.json (parity-reporter.ts).
//
// Gate: Tier A blocks; Tier B blocks once the entry is `locked`; Tier C is report-only; an entry
// with a recorded `deviation` is report-only too, and says why.
import { existsSync } from "node:fs";
import { expect, test } from "@playwright/test";
import {
  TIERS,
  openGallery,
  pngSize,
  readManifest,
  masked,
  shootWhole,
  specimen,
  specimenOf,
} from "./support";

const manifest = readManifest();

/** Playwright's own comparator, run strictly so its report carries the exact pixel count. */
function diffPixels(
  actual: Uint8Array,
  name: string,
  threshold: number,
): { pixels: number } | { sizeMismatch: string } {
  try {
    expect(actual).toMatchSnapshot(name, { threshold, maxDiffPixelRatio: 0 });
    return { pixels: 0 };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    // A different size is reported before the pixel count, and is a failure at any tier.
    const sizes = /Expected an image \d+px by \d+px, received \d+px by \d+px/.exec(message);
    if (sizes !== null) return { sizeMismatch: sizes[0] };
    const counted = /(\d+) pixels \(ratio/.exec(message);
    if (counted?.[1] !== undefined) return { pixels: Number(counted[1]) };
    throw error;
  }
}

for (const [key, entry] of Object.entries(manifest)) {
  if (entry.tier === "D") continue;
  const tier = entry.tier;

  test(`${key} at tier ${tier}`, async ({ page }, testInfo) => {
    const name = `${key.replaceAll(".", "-")}.png`; // as Playwright names the file
    test.skip(
      testInfo.config.updateSnapshots === "all",
      "parity baselines come from the handoff; never rewrite them from the app",
    );
    test.skip(
      !existsSync(testInfo.snapshotPath(name)),
      `no baseline for ${key} at ${testInfo.snapshotPath(name)}: run pnpm visual:baselines`,
    );

    await openGallery(page, entry.page);
    const target = (
      entry.page === undefined
        ? specimen(page, specimenOf(key), entry.selector)
        : page.locator(entry.selector ?? "body")
    ).first();
    await target.scrollIntoViewIfNeeded();
    // A whole frame (a window or phone) is shot at its exact box; a part keeps the element shot its
    // crop was cut for (the C-06 and FND-01 crops include the outward pixel).
    const shot = await masked(
      page,
      target,
      entry.mask,
      entry.selector?.includes('[data-shell="app"]')
        ? await shootWhole(page, target)
        : await target.screenshot({ animations: "disabled", caret: "hide" }),
      name,
      (n) => testInfo.snapshotPath(n),
    );
    const actual = shot.actual;

    const gate =
      entry.deviation !== undefined
        ? "deviation"
        : tier === "A" || (tier === "B" && entry.locked === true)
          ? "blocking"
          : "report-only";
    const { width, height } = pngSize(actual);
    const result = diffPixels(actual, shot.name, TIERS[tier].threshold);
    const record = {
      artboard: key,
      tier,
      gate,
      deviation: entry.deviation ?? null,
      size: `${String(width)}x${String(height)}`,
      diffPercent:
        "pixels" in result ? Math.round((result.pixels / (width * height)) * 10_000) / 100 : null,
      note: "sizeMismatch" in result ? result.sizeMismatch : null,
    };
    testInfo.annotations.push({ type: "parity", description: JSON.stringify(record) });

    if (gate !== "blocking") return;
    expect(result, `${key}: ${JSON.stringify(record)}`).toHaveProperty("pixels");
    expect(record.diffPercent, `${key} diff % at tier ${tier}`).toBeLessThanOrEqual(
      TIERS[tier].maxDiffPixelRatio * 100,
    );
  });
}
