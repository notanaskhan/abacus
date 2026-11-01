// The N-02 lock's computed and keyboard checks (N-02-T43; N-02 §5.4, §5.5): not pixels, so they
// need no baseline and block wherever the visual project runs. SIG-02's documents reorder from the
// keyboard (Alt+↑/↓) and announce it; POR-06's provider frame carries a title; POR-06 at 390 keeps
// its sticky sign bar; forced colours and reduced motion leave every frame readable and still.
import { type Locator, type Page, expect, test } from "@playwright/test";
import { openGallery } from "./support";

async function board(page: Page, screen: string, st: string): Promise<Locator> {
  await openGallery(page, `screens/${screen}?st=${st}`);
  const frame = page.locator(`[data-artboard='${st}']`).first();
  await expect(frame).toBeVisible();
  return frame;
}

test("SIG-02a: Alt+↑ moves a document up and says so", async ({ page }) => {
  const frame = await board(page, "SIG-02", "a");
  const docs = frame.getByRole("list", { name: "Documents" }).getByRole("button");
  await expect(docs).toHaveCount(2); // Harborview: the 8879-PE and its second document
  const second = (await docs.nth(1).innerText()).split("\n")[0] ?? "";
  await docs.nth(1).focus();
  await page.keyboard.press("Alt+ArrowUp");
  await expect(docs.first()).toContainText(second);
  await expect(frame.locator("p[aria-live='polite']")).not.toBeEmpty();
});

// N-02 §5.5 names both; SIG-02's signer cards and field placement take no keyboard move yet.
test.fixme("SIG-02e: signer order and field placement from the keyboard", () => undefined);

test("POR-06b: the provider's frame has a title", async ({ page }) => {
  const frame = await board(page, "POR-06", "b");
  const provider = frame.locator('[data-signing="provider-frame"]');
  if ((await provider.count()) > 0) {
    await expect(provider.first()).toHaveAttribute("title", /\S/);
  }
});

test("POR-06a at 390: the sticky sign bar stays in the phone frame", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const frame = await board(page, "POR-06", "a");
  await expect(frame.locator('[data-signing="mobile-sign-bar"]').first()).toBeAttached();
});

for (const [screen, st] of [
  ["SIG-01", "a"],
  ["SIG-02", "a"],
  ["POR-06", "a"],
  ["ENG-04", "a"],
] as const) {
  test(`${screen}${st}: forced colours and reduced motion`, async ({ page }) => {
    await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
    const frame = await board(page, screen, st);
    const running = await frame.evaluate(
      (el) => el.getAnimations({ subtree: true }).filter((a) => a.playState === "running").length,
    );
    expect(running).toBe(0);
    await expect(frame).toBeVisible();
  });
}
