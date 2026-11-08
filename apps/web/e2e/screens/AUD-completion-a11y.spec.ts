// A-06-T36 (TASK-6122): accessibility and keyboard for the completion screens' 27 artboards on
// fixtures (AUD-15 a-f, AUD-16 a-g, AUD-17 a-f, AUD-20 a-f plus a2, b2 and the flag-off states).
// Every serious or critical axe finding blocks (DEC-11); Escape closes what a screen opens and
// focus returns to its opener; Tab never gets stuck. Parity's Tier C report runs in e2e/parity.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.use({ reducedMotion: "reduce" });

const SERIOUS = new Set(["serious", "critical"]);
const SCREENS: Record<string, { path: string; states: string[] }> = {
  "AUD-15": { path: "findings", states: ["a", "b", "c", "d", "e", "f"] },
  "AUD-16": { path: "misstatements", states: ["a", "b", "c", "d", "e", "f", "g"] },
  "AUD-17": { path: "review-notes", states: ["a", "b", "c", "d", "e", "f"] },
  "AUD-20": { path: "fs-disclosure", states: ["a", "a2", "b", "c", "d", "e", "f", "off"] },
};

for (const [screen, { path, states }] of Object.entries(SCREENS)) {
  for (const st of states) {
    test(`${screen}${st}: no serious or critical axe finding`, async ({ page }) => {
      await page.goto(`/audits/_auditId_/${path}?screen=${screen}&st=${st}`);
      await page.waitForLoadState("networkidle");
      const results = await new AxeBuilder({ page }).analyze();
      const blocking = results.violations.filter((v) => SERIOUS.has(v.impact ?? ""));
      expect(blocking.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
    });
  }

  test(`${screen}: Escape closes a dialog and focus returns`, async ({ page }) => {
    await page.goto(`/audits/_auditId_/${path}?screen=${screen}&st=a`);
    const opener = page.locator("button[aria-haspopup='dialog']:not([disabled])").first();
    test.skip((await opener.count()) === 0, "this artboard opens nothing");
    await opener.click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(opener).toBeFocused();
  });

  test(`${screen}: Tab moves forward and is never stuck`, async ({ page }) => {
    await page.goto(`/audits/_auditId_/${path}?screen=${screen}&st=a`);
    await page.waitForLoadState("networkidle");
    const seen = new Set<string>();
    for (let tab = 0; tab < 25; tab += 1) {
      await page.keyboard.press("Tab");
      const id = await page.evaluate(() => {
        const el = document.activeElement;
        return el === null ? "" : `${el.tagName}:${el.getAttribute("aria-label") ?? ""}`;
      });
      seen.add(id);
    }
    expect(seen.size).toBeGreaterThan(3);
  });
}
