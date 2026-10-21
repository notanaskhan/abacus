// Gallery screenshot regression (F-05-T17; chapter 04 §9.3): every specimen section on /components
// against the same specimen rendered from the baseline revision, at the Tier A tolerance.
//
// The baselines are written by `pnpm visual:update` (`--update-snapshots`) into
// .visual/regression.spec.ts, which git ignores. In CI, scripts/visual-ci.mjs writes them from the
// pull request's base commit on the same runner, so fonts and anti-aliasing match and no
// platform-specific PNG is committed. A specimen with no baseline is new: it is skipped and listed.
import { existsSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { TIERS, openGallery } from "./support";

test("every specimen renders as it did at the baseline (tier A)", async ({ page }, testInfo) => {
  await openGallery(page);
  const ids = await page
    .locator("section[id][aria-label]")
    .evaluateAll((sections) => sections.map((s) => s.id));
  expect(ids.length, "the gallery lists its specimens").toBeGreaterThan(0);

  const fresh: string[] = [];
  const updating = testInfo.config.updateSnapshots === "all";
  for (const id of ids) {
    const name = `${id}.png`;
    if (!updating && !existsSync(testInfo.snapshotPath(name))) {
      fresh.push(id);
      continue;
    }
    const section = page.locator(`section[id="${id}"]`);
    await section.scrollIntoViewIfNeeded();
    expect
      .soft(await section.screenshot({ animations: "disabled", caret: "hide" }), id)
      .toMatchSnapshot(name, TIERS.A);
  }
  testInfo.annotations.push({
    type: "new specimens",
    description: fresh.length === 0 ? "none" : fresh.join(", "),
  });
});
