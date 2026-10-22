// F-05-T24: the accessibility harness over the /components gallery (plan 04 sections 3.8 and 9;
// SPEC-048 AC-3). DEC-11 is recorded (the AA ink ladder), so every serious or critical axe finding
// blocks. The gallery calls no API: only the dev server is needed (`make dev-fixtures`).
//
// - axe on every specimen (scoped to its section, so a failure names the specimen) and on every
//   overlay the specimens open;
// - forced-colors emulation: axe again, and panes, pills and dialogs keep a CanvasText edge;
// - reduced motion with an overlay open: nothing animates;
// - keyboard: every focus stop shows a focus outline, and Tab is never stuck;
// - target size (SC 2.5.8): every control is 24px, or its hit area or spacing gives it 24px.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

/** Let one-off entrance animations finish (a Reveal rising word by word is mid-fade otherwise, and
 * axe measures the fade); looping ones (spinners) keep running. */
async function settle(page: Page): Promise<void> {
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every(
        (a) => a.playState !== "running" || a.effect?.getComputedTiming().iterations === Infinity,
      ),
  );
}

async function seriousViolations(page: Page, include?: string): Promise<string[]> {
  await settle(page);
  let builder = new AxeBuilder({ page });
  if (include !== undefined) builder = builder.include(include);
  const { violations } = await builder.analyze();
  return violations
    .filter((v) => SERIOUS.has(v.impact ?? ""))
    .map((v) => `${v.id} (${v.impact ?? "?"}): ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
}

async function openGallery(page: Page): Promise<string[]> {
  await page.goto("/components");
  await expect(page.getByRole("heading", { name: "Components", level: 1 })).toBeVisible();
  return page
    .locator("section[id][aria-label]")
    .evaluateAll((sections) => sections.map((s) => s.id));
}

// The specimens that open overlays (O1 to O6, C-22 dialogs, C-23 drawer).
const OVERLAY_SPECIMENS = /^(o[1-6]-|c-22-|c-23-drawer)/;
const OPEN_LAYER = '[role="dialog"], [role="alertdialog"], [role="complementary"][data-overlay]';

test.describe("axe", () => {
  test("every specimen is clean, each on its own", async ({ page }) => {
    const ids = await openGallery(page);
    expect(ids.length).toBeGreaterThan(50);
    const found: string[] = [];
    for (const id of ids) {
      for (const v of await seriousViolations(page, `#${id}`)) found.push(`${id}: ${v}`);
    }
    expect(found, "serious or critical findings by specimen").toEqual([]);
  });

  test("every overlay a specimen opens is clean while open", async ({ page }) => {
    const ids = (await openGallery(page)).filter((id) => OVERLAY_SPECIMENS.test(id));
    expect(ids.length).toBeGreaterThan(5);
    const found: string[] = [];
    let opened = 0;
    for (const id of ids) {
      const triggers = page.locator(`#${id} button[aria-haspopup], #${id} button[data-opens]`);
      const count = await triggers.count();
      for (let i = 0; i < count; i += 1) {
        const trigger = triggers.nth(i);
        if (!(await trigger.isVisible()) || (await trigger.isDisabled())) continue;
        await trigger.click();
        const layer = page.locator(OPEN_LAYER).last();
        if (!(await layer.isVisible().catch(() => false))) continue;
        opened += 1;
        for (const v of await seriousViolations(page)) found.push(`${id} #${String(i)}: ${v}`);
        for (let n = 0; n < 4 && (await page.locator(OPEN_LAYER).count()) > 0; n += 1) {
          await page.keyboard.press("Escape");
        }
      }
    }
    expect(opened, "overlays opened").toBeGreaterThan(3);
    expect(found, "serious or critical findings with an overlay open").toEqual([]);
  });
});

test.describe("forced colors", () => {
  test.use({ forcedColors: "active" });

  test("axe stays clean, and panes, pills and dialogs keep an edge", async ({ page }) => {
    await openGallery(page);
    expect(await seriousViolations(page)).toEqual([]);
    const edges = await page.evaluate(() => {
      const pick = (selector: string): string[] =>
        [...document.querySelectorAll<HTMLElement>(selector)].slice(0, 20).map((el) => {
          const style = getComputedStyle(el);
          return `${style.outlineStyle} ${style.outlineWidth}`;
        });
      return {
        panes: pick("section[id] .rounded-pane"),
        pills: pick('section[id] .rounded-pill:not([role="img"])'),
      };
    });
    expect(edges.panes.length).toBeGreaterThan(0);
    expect(edges.pills.length).toBeGreaterThan(0);
    for (const edge of [...edges.panes, ...edges.pills]) expect(edge).toBe("solid 1px");
  });

  test("status discs keep their colours", async ({ page }) => {
    await openGallery(page);
    const adjust = await page
      .locator('section[id] [role="img"].rounded-pill')
      .first()
      .evaluate((el) => getComputedStyle(el).forcedColorAdjust);
    expect(adjust).toBe("none");
  });
});

/**
 * What is visibly animating, named by its animation (or transition) and where it sits. Reduced
 * motion clamps every CSS transition and animation to 0.01ms (motion.css), and Chromium lists such
 * a clamped one as running for a frame; those move nothing, so they are left out.
 */
async function running(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    document
      .getAnimations()
      .filter((a) => {
        const d = a.effect?.getComputedTiming().duration;
        return typeof d !== "number" || d > 1;
      })
      .map((a) => {
        const named = a as Animation & { animationName?: string; transitionProperty?: string };
        const el = (a.effect as KeyframeEffect | null)?.target as Element | null;
        const where = el?.closest("section[id]")?.id ?? el?.tagName.toLowerCase() ?? "?";
        return `${named.animationName ?? named.transitionProperty ?? "?"} @ ${where}`;
      }),
  );
}

test.describe("reduced motion with an overlay open", () => {
  test.use({ reducedMotion: "reduce" });

  test("opening and closing a layer runs no animation", async ({ page }) => {
    const ids = (await openGallery(page)).filter((id) => OVERLAY_SPECIMENS.test(id));
    const trigger = page
      .locator(
        ids.map((id) => `#${id} button[aria-haspopup], #${id} button[data-opens]`).join(", "),
      )
      .first();
    await trigger.click();
    await expect(page.locator(OPEN_LAYER).last()).toBeVisible();
    // Reduced motion clamps any CSS transition to 0.01ms, which a sample can still catch for a
    // frame; a real animation (the shortest the kit draws is 160ms) is still running at 100ms.
    await expect
      .poll(() => running(page), { message: "animations with the layer open", timeout: 100 })
      .toEqual([]);
    await page.keyboard.press("Escape");
    await expect
      .poll(() => running(page), { message: "animations after closing it", timeout: 100 })
      .toEqual([]);
  });
});

test.describe("keyboard", () => {
  test("every focus stop shows the outline, and Tab always moves on", async ({ page }) => {
    await openGallery(page);
    const missing: string[] = [];
    let last = "";
    let stuck = 0;
    for (let i = 0; i < 60; i += 1) {
      await page.keyboard.press("Tab");
      const stop = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (el === null || el === document.body) return null;
        const style = getComputedStyle(el);
        const ring =
          (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) >= 2) ||
          /rgba?\(/.test(style.boxShadow);
        const name = el.getAttribute("aria-label") ?? el.textContent.trim().slice(0, 40);
        const path = `${el.closest("section[id]")?.id ?? "?"} › ${el.tagName.toLowerCase()} "${name}"`;
        return { ring, path };
      });
      if (stop === null) continue;
      if (!stop.ring) missing.push(stop.path);
      stuck = stop.path === last ? stuck + 1 : 0;
      last = stop.path;
      expect(stuck, `Tab is stuck on ${stop.path}`).toBeLessThan(3);
    }
    expect(missing, "focus stops without a visible outline").toEqual([]);
  });
});

test.describe("target size (SC 2.5.8)", () => {
  test("every control is 24px, or its hit area or spacing makes it so", async ({ page }) => {
    await openGallery(page);
    const small = await page.evaluate(() => {
      const MIN = 24;
      const R = MIN / 2;
      const selector = [
        "button",
        "a[href]",
        '[role="button"]',
        '[role="tab"]',
        '[role="switch"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="menuitem"]',
        'input:not([type="hidden"])',
      ].join(", ");
      const targets = [
        ...document.querySelectorAll<HTMLElement>(
          selector
            .split(", ")
            .map((one) => `section[id] ${one}`)
            .join(", "),
        ),
      ].filter((el) => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
      });
      const rects = targets.map((el) => el.getBoundingClientRect());
      const problems: string[] = [];
      targets.forEach((el, i) => {
        const r = rects[i];
        if (r === undefined || (r.width >= MIN && r.height >= MIN)) return;
        // Inline text links in a sentence are exempt (SC 2.5.8 "inline").
        if (el.tagName === "A" && getComputedStyle(el).display === "inline") return;
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        // A hit area: the points 11.5px out from the centre still land on the control.
        const offsets = [
          [R - 0.5, 0],
          [-(R - 0.5), 0],
          [0, R - 0.5],
          [0, -(R - 0.5)],
        ];
        el.scrollIntoView({ block: "center", inline: "center" });
        const box = el.getBoundingClientRect();
        const ox = box.left + box.width / 2;
        const oy = box.top + box.height / 2;
        const lands = offsets.every(([dx = 0, dy = 0]) => {
          const hit = document.elementFromPoint(ox + dx, oy + dy);
          return hit !== null && (hit === el || el.contains(hit));
        });
        if (lands) return;
        // Spacing: a 24px circle on the centre meets no other target.
        const clear = rects.every((o, j) => {
          if (j === i) return true;
          const nx = Math.max(o.left, Math.min(cx, o.right));
          const ny = Math.max(o.top, Math.min(cy, o.bottom));
          return Math.hypot(nx - cx, ny - cy) >= R;
        });
        if (clear) return;
        const name = el.getAttribute("aria-label") ?? el.textContent.trim().slice(0, 30);
        problems.push(
          `${el.closest("section[id]")?.id ?? "?"} › ${el.tagName.toLowerCase()} "${name}" ${String(Math.round(r.width))}×${String(Math.round(r.height))}`,
        );
      });
      return { checked: targets.length, problems };
    });
    expect(small.checked, "controls checked").toBeGreaterThan(200);
    expect(small.problems, "controls under 24px with no hit area and no spacing").toEqual([]);
  });
});
