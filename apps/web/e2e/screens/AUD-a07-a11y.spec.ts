// A-07-T48 (A-07 §5.4, §5.5): accessibility and keyboard for the frame-driven A-07 canvases on the
// gallery (AUD-22 a–c, AUD-23 a–j, AUD-24 a–f, AUD-25 a–e with b2). Every serious or critical axe
// finding blocks (DEC-11); every O3 sheet traps focus, Escape closes it and focus returns to its
// opener; Tab never gets stuck on the canvas.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.use({ reducedMotion: "reduce" });

const SERIOUS = new Set(["serious", "critical"]);
const SCREENS: Record<string, string[]> = {
  "AUD-22": ["a", "b", "c"],
  "AUD-23": ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"],
  "AUD-24": ["a", "b", "c", "d", "e", "f"],
  "AUD-25": ["a", "b", "b2", "c", "d", "e"],
};
// The O3 sheets each screen opens from its primary control, and the opener's accessible name.
const SHEETS: Record<string, { st: string; opener: RegExp }> = {
  "AUD-22": { st: "a", opener: /Approve & send/ },
  "AUD-24": { st: "a", opener: /Release report/ },
  "AUD-25": { st: "b", opener: /Lock archive/ },
};

async function open(
  page: import("@playwright/test").Page,
  screen: string,
  st: string,
): Promise<void> {
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1&static=1`);
  await expect(page.locator(`[data-artboard='${st}']`)).toBeVisible();
}

for (const [screen, states] of Object.entries(SCREENS)) {
  for (const st of states) {
    test(`${screen}${st}: no serious or critical axe finding`, async ({ page }) => {
      await open(page, screen, st);
      const results = await new AxeBuilder({ page }).include(`[data-artboard='${st}']`).analyze();
      const blocking = results.violations.filter((v) => SERIOUS.has(v.impact ?? ""));
      expect(blocking.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
    });
  }

  test(`${screen}: Tab moves through the canvas without getting stuck`, async ({ page }) => {
    await open(page, screen, states[0] ?? "a");
    const seen = new Set<string>();
    for (let i = 0; i < 25; i += 1) {
      await page.keyboard.press("Tab");
      const id = await page.evaluate(() => {
        const el = document.activeElement;
        return el ? `${el.tagName}:${el.textContent?.slice(0, 30) ?? ""}` : "none";
      });
      seen.add(id);
    }
    expect(seen.size).toBeGreaterThan(3);
  });
}

for (const [screen, { st, opener }] of Object.entries(SHEETS)) {
  test(`${screen}: the O3 sheet traps focus, Escape closes it, focus returns`, async ({
    page,
  }) => {
    await open(page, screen, st);
    const trigger = page.getByRole("button", { name: opener }).first();
    test.skip(!(await trigger.isEnabled()), "the opener is disabled in this frame");
    await trigger.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    for (let i = 0; i < 12; i += 1) {
      await page.keyboard.press("Tab");
      const inside = await dialog.evaluate((d) => d.contains(document.activeElement));
      expect(inside).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
  });
}
