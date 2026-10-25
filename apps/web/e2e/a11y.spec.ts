// F-05-T24: the accessibility harness over the /components gallery (plan 04 sections 3.8 and 9;
// SPEC-048 AC-3). DEC-11 is recorded (the AA ink ladder), so every serious or critical axe finding
// blocks. The gallery calls no API: only the dev server is needed (`make dev-fixtures`).
//
// - axe on every specimen (scoped to its section, so a failure names the specimen) and on every
//   overlay the specimens open. The sweep is one test per chunk of specimens, generated from the
//   registry the gallery renders, so it parallelises and no test outgrows its timeout as the
//   gallery grows; a guard test proves the page shows exactly the registry's specimens;
// - forced-colors emulation: axe again, and panes, pills and dialogs keep a CanvasText edge;
// - reduced motion with an overlay open: nothing animates;
// - keyboard: every focus stop shows a focus outline, and Tab is never stuck;
// - target size (SC 2.5.8): every control is 24px, or its hit area or spacing gives it 24px.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

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

/** The specimen ids in the registry's order (packages/ui/src/specimens/index.ts, `SPECIMENS`):
 * the list the gallery renders, read when the tests are collected so each chunk is its own test. */
function registryIds(): readonly string[] {
  const source = readFileSync("../../packages/ui/src/specimens/index.ts", "utf8");
  const start = source.indexOf("export const SPECIMENS");
  const body = source.slice(start, source.indexOf("\n];", start));
  return [...body.matchAll(/\bid: "([a-z0-9-]+)"/g)].flatMap((m) =>
    m[1] === undefined ? [] : [m[1]],
  );
}

const SPECIMEN_IDS = registryIds();
const OVERLAY_IDS = SPECIMEN_IDS.filter((id) => OVERLAY_SPECIMENS.test(id));
/** Overlay tests per overlay specimen (its triggers dealt round-robin). */
const OVERLAY_PARTS = 4;
/** Specimens per axe test: about 3 s of axe each on the full gallery page, well under the timeout. */
const CHUNK = 8;
const CHUNKS = Array.from({ length: Math.ceil(SPECIMEN_IDS.length / CHUNK) }, (_, i) =>
  SPECIMEN_IDS.slice(i * CHUNK, (i + 1) * CHUNK),
);

test.describe("axe", () => {
  // The chunks are independent: with more than one worker they run side by side.
  test.describe.configure({ mode: "parallel" });

  test("the gallery renders exactly the registry's specimens", async ({ page }) => {
    expect(SPECIMEN_IDS.length).toBeGreaterThan(50);
    expect(OVERLAY_IDS.length).toBeGreaterThan(5);
    expect(new Set(SPECIMEN_IDS).size, "registry ids are unique").toBe(SPECIMEN_IDS.length);
    expect([...(await openGallery(page))].sort()).toEqual([...SPECIMEN_IDS].sort());
  });

  for (const [n, ids] of CHUNKS.entries()) {
    test(`every specimen is clean, each on its own: ${String(n + 1)} of ${String(CHUNKS.length)} (${ids.join(", ")})`, async ({
      page,
    }) => {
      const shown = new Set(await openGallery(page));
      const found: string[] = [];
      for (const id of ids) {
        expect(shown.has(id), `${id} is on the gallery page`).toBe(true);
        for (const v of await seriousViolations(page, `#${id}`)) found.push(`${id}: ${v}`);
      }
      expect(found, "serious or critical findings by specimen").toEqual([]);
    });
  }

  // Axe runs page-wide with an overlay open (a modal hides the rest of the page, which is where
  // its findings land), about 30 s each, so each overlay specimen's triggers are split over
  // OVERLAY_PARTS tests (trigger i goes to part i mod OVERLAY_PARTS): every trigger is checked.
  for (const id of OVERLAY_IDS) {
    for (let part = 0; part < OVERLAY_PARTS; part += 1) {
      test(`every overlay a specimen opens is clean while open: ${id} (${String(part + 1)} of ${String(OVERLAY_PARTS)})`, async ({
        page,
      }) => {
        await openGallery(page);
        const found: string[] = [];
        await eachOverlay(
          page,
          id,
          async (i) => {
            for (const v of await seriousViolations(page)) found.push(`${id} #${String(i)}: ${v}`);
          },
          (i) => i % OVERLAY_PARTS === part,
        );
        expect(found, "serious or critical findings with an overlay open").toEqual([]);
      });
    }
  }

  // What the single sweep also proved: the overlay specimens really open overlays (no axe here).
  test("the overlay specimens open more than three overlays", async ({ page }) => {
    await openGallery(page);
    let opened = 0;
    for (const id of OVERLAY_IDS) {
      await eachOverlay(page, id, () => {
        opened += 1;
        return Promise.resolve();
      });
    }
    expect(opened, "overlays opened").toBeGreaterThan(3);
  });
});

/** Open each of a specimen's overlay triggers in turn, run `check` while it is open (with the
 * trigger's index), and close it again. */
async function eachOverlay(
  page: Page,
  id: string,
  check: (index: number) => Promise<void>,
  take: (index: number) => boolean = () => true,
): Promise<void> {
  const triggers = page.locator(`#${id} button[aria-haspopup], #${id} button[data-opens]`);
  const count = await triggers.count();
  for (let i = 0; i < count; i += 1) {
    if (!take(i)) continue;
    const trigger = triggers.nth(i);
    if (!(await trigger.isVisible()) || (await trigger.isDisabled())) continue;
    await trigger.click();
    const layer = page.locator(OPEN_LAYER).last();
    if (!(await layer.isVisible().catch(() => false))) continue;
    await check(i);
    for (let n = 0; n < 4 && (await page.locator(OPEN_LAYER).count()) > 0; n += 1) {
      await page.keyboard.press("Escape");
    }
  }
}

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

/** Wait `n` animation frames: any transition a click or a key started has begun by then. */
async function frames(page: Page, n: number): Promise<void> {
  await page.evaluate(
    (count) =>
      new Promise<void>((done) => {
        let left = count;
        const tick = (): void => {
          left -= 1;
          if (left <= 0) done();
          else requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }),
    n,
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
    // Reduced motion clamps any CSS transition to 0.01ms, which `running` leaves out; a real
    // animation (the shortest the kit draws is 160ms) is still running two frames after it
    // starts. One sample after two frames, not a wall-clock poll: `getAnimations()` over the
    // whole gallery can take longer than a 100ms poll budget on a loaded runner, which failed
    // the poll before it sampled anything.
    await frames(page, 2);
    expect(await running(page), "animations with the layer open").toEqual([]);
    await page.keyboard.press("Escape");
    await frames(page, 2);
    expect(await running(page), "animations after closing it").toEqual([]);
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
