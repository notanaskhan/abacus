// TPL-19's parity lock (F-06-T11): the handoff has no screenshots for TPL-19 (gaps.md: "no lettered
// artboards and no screenshots"), so the lock is Tier D, computed geometry against the spec rather
// than pixels, blocking where the visual project runs. Every phone frame on the specimen section:
// 390 × 844; the T7-M shell's 56 header and 64 tab bar at the foot (frames 1, 2, 6, 7); frame 5's
// sheet flush with the phone's foot, its two page previews 150 × 194 and a 48-high Upload; the
// deferred frames (3, 4, 8, permission off) are placeholders; every target at least 44 × 44.
import { type Locator, expect, test } from "@playwright/test";
import { openGallery, specimen } from "./support";

test.use({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
});

async function box(target: Locator): Promise<{ x: number; y: number; w: number; h: number }> {
  const b = await target.boundingBox();
  if (b === null) throw new Error("no box");
  return {
    x: Math.round(b.x),
    y: Math.round(b.y),
    w: Math.round(b.width),
    h: Math.round(b.height),
  };
}

function board(page: import("@playwright/test").Page, id: string): Locator {
  return specimen(page, "tpl-19", `[data-artboard="${id}"]`);
}

test.beforeEach(async ({ page }) => {
  await openGallery(page);
});

test("every TPL-19 frame is a 390 × 844 phone", async ({ page }) => {
  for (const id of [
    "tpl-19-1",
    "tpl-19-2",
    "tpl-19-3",
    "tpl-19-4",
    "tpl-19-5",
    "tpl-19-6",
    "tpl-19-7",
    "tpl-19-8",
  ]) {
    const phone = board(page, id)
      .locator("[data-frame='phone'], [data-capture='deferred']")
      .first();
    const b = await box(phone);
    expect([id, b.w, b.h]).toEqual([id, 390, 844]);
  }
});

test("frames 1, 2, 6, 7: header 56 at the top and the 64 tab bar at the foot", async ({
  page,
}) => {
  for (const id of ["tpl-19-1", "tpl-19-2", "tpl-19-6", "tpl-19-7"]) {
    const phone = await box(board(page, id).locator("[data-frame='phone']").first());
    const header = await box(board(page, id).locator("[data-shell='mobile-header']"));
    const tabs = await board(page, id).locator("[data-shell='mobile-tab-bar']").boundingBox();
    const top = await board(page, id).locator("[data-frame='phone']").first().boundingBox();
    if (tabs === null || top === null) throw new Error("no box");
    expect([id, header.y - phone.y, header.h]).toEqual([id, 0, 56]);
    // The foot from unrounded boxes: rounding y and height apart can lose a pixel.
    expect([id, Math.round(tabs.height), Math.round(tabs.y + tabs.height - top.y)]).toEqual([
      id,
      64,
      844,
    ]);
  }
});

test("frame 5: the review sheet at the foot, previews 150 × 194, Upload 48 high", async ({
  page,
}) => {
  const phone = await box(board(page, "tpl-19-5").locator("[data-frame='phone']"));
  const sheet = await box(board(page, "tpl-19-5").locator("[data-capture='review-sheet']"));
  expect(sheet.y + sheet.h - phone.y).toBe(844);
  expect(sheet.w).toBe(390);
  for (const n of [1, 2]) {
    const preview = await box(board(page, "tpl-19-5").locator(`[data-page='${String(n)}']`));
    expect([preview.w, preview.h]).toEqual([150, 194]);
  }
  const upload = await box(
    board(page, "tpl-19-5").getByRole("button", { name: "Upload", exact: true }),
  );
  expect(upload.h).toBe(48);
});

test("frames 5 and 6: every target at least 44 × 44", async ({ page }) => {
  for (const id of ["tpl-19-5", "tpl-19-6"]) {
    const small = await board(page, id).evaluate((root) =>
      [...root.querySelectorAll("button, a[href], select, label[for]")]
        .filter((el) => (el as HTMLElement).offsetParent !== null)
        .map((el) => ({ el, b: el.getBoundingClientRect() }))
        .filter(({ b }) => b.width > 0 && (b.width < 44 || b.height < 44))
        .filter(({ el }) => el.closest("[data-shell='mobile-header']") === null)
        .map(({ el }) => (el.getAttribute("aria-label") ?? (el as HTMLElement).innerText).trim()),
    );
    expect([id, small]).toEqual([id, []]);
  }
});

test("frames 3, 4, 8 and permission off are Deferred (DEC-97) placeholders", async ({ page }) => {
  for (const id of ["tpl-19-3", "tpl-19-4", "tpl-19-8", "tpl-19-perm"]) {
    await expect(board(page, id).locator("[data-capture='deferred']")).toHaveText(
      "Deferred (DEC-97)",
    );
  }
});
