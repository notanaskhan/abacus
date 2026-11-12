// Tier D for the T4 Workbench chat template and the TPL-04 specimen (F-07-T09; SPEC-652 AC-1;
// handoff T4): exact computed sizes, not pixels, so it needs no baseline and blocks wherever the
// visual project runs. Tabsbar 60 with a −10 margin, panes y106–848 (742 tall), the list 358 (320
// on WB-06) at x12 and the chat 1008 at x380; pane headers 46; the composer 50; the ask card's
// header 36 above it.
import { type Locator, expect, test } from "@playwright/test";
import { openGallery } from "./support";

async function box(target: Locator): Promise<{ x: number; y: number; w: number; h: number }> {
  const b = await target.first().boundingBox();
  if (b === null) throw new Error("no box");
  return {
    x: Math.round(b.x),
    y: Math.round(b.y),
    w: Math.round(b.width),
    h: Math.round(b.height),
  };
}

const BOARDS = [
  ...(["a", "b", "c", "d", "e", "f"] as const).map((st) => ({ screen: "T4", st })),
  ...(["a", "b", "c", "d", "e"] as const).map((st) => ({ screen: "TPL-04", st })),
];

for (const { screen, st } of BOARDS) {
  test(`${screen}${st}: tabsbar 60, panes y106–848, list ${st === "f" && screen === "T4" ? 320 : 358}`, async ({
    page,
  }) => {
    await openGallery(page, `screens/${screen}?st=${st}`);
    const frame = page.locator(`[data-artboard='${st}']`);
    await expect(frame.locator("[data-template='T4']")).toBeVisible();
    const shell = await box(frame.locator("[data-shell='app']"));
    expect((await box(frame.locator("[data-tabsbar]"))).h).toBe(60);
    const panes = frame.locator("[data-panes] > *");
    const list = await box(panes.nth(0));
    const chat = await box(panes.nth(1));
    const agentDetail = screen === "T4" && st === "f";
    expect(list.y - shell.y).toBe(106);
    expect(list.h).toBe(742);
    expect(list.x - shell.x).toBe(12);
    expect(list.w).toBe(agentDetail ? 320 : 358);
    expect(chat.y + chat.h - shell.y).toBe(848);
    if (!agentDetail) {
      expect(chat.x - shell.x).toBe(380);
      expect(chat.w).toBe(1008);
      expect((await box(frame.locator("[data-kit='ChatHeader']"))).h).toBe(46);
      expect((await box(frame.locator("[data-kit='Composer']"))).h).toBe(50);
    }
    const ask = frame.locator("[data-kit='QuestionCard']");
    if ((await ask.count()) > 0) {
      expect((await box(ask.locator("> div").first())).h).toBe(36);
      const composer = await box(frame.locator("[data-kit='Composer']"));
      const card = await box(ask);
      expect(composer.y - (card.y + card.h)).toBe(9);
    }
  });
}
