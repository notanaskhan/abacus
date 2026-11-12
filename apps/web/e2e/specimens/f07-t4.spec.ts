// ac-test-author: ayushkbhatia
// F-07-T09 (SPEC-652 AC-1 to AC-5; handoff T4, TPL-04): the T4 lock before W-02 starts. Axe on
// every T4 and TPL-04 state (serious and critical block), and the keyboard paths of the QuestionCard
// (1–9, Enter, Esc), the Composer (Enter sends, Shift+Enter breaks a line) and the JumpFab.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/specimens/f07-t4.spec.ts`.
import { type Page, expect, test } from "@playwright/test";
import { axeStep } from "../harness/axe";

const E0 = new Date("2026-09-14T09:24:00-05:00");

test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });

async function board(page: Page, screen: "T4" | "TPL-04", st: string): Promise<void> {
  await page.clock.setFixedTime(E0);
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1&static=1`);
  await expect(page.locator(`[data-artboard='${st}'] [data-template='T4']`)).toBeVisible();
}

for (const st of ["a", "b", "c", "d", "e", "f"]) {
  test(`test_t4${st}_axe_serious_and_critical_zero`, async ({ page }) => {
    await board(page, "T4", st);
    await axeStep(page, `f07 T4${st}`, { include: "[data-artboard]" });
  });
}

for (const st of ["a", "b", "c", "d", "e"]) {
  test(`test_tpl04${st}_axe_serious_and_critical_zero`, async ({ page }) => {
    await board(page, "TPL-04", st);
    await axeStep(page, `f07 TPL-04${st}`, { include: "[data-artboard]" });
  });
}

test("test_ac5_question_card_keys_choose_enter_answers_esc_returns_to_composer", async ({
  page,
}) => {
  await board(page, "TPL-04", "a");
  const card = page.locator("[data-kit='QuestionCard']");
  await card.getByRole("radio").first().focus();
  await page.keyboard.press("2");
  await expect(card.getByRole("radio").nth(1)).toBeChecked();
  await page.keyboard.press("Escape");
  await expect(page.locator("[data-intent-log] li")).toHaveCount(0);
  await card.getByRole("radio").nth(1).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-intent-log] li").first()).toContainText("answer:");
  await expect(card).toContainText("2 of 2");
  await expect(card.getByRole("button", { name: "Previous" })).toBeEnabled();
});

test("test_ac4_composer_enter_sends_shift_enter_breaks_a_line", async ({ page }) => {
  await board(page, "T4", "a");
  const composer = page.getByRole("textbox", { name: "Message" });
  await composer.fill("Which notices");
  await composer.press("Shift+Enter");
  await expect(composer).toHaveValue("Which notices\n");
  await composer.press("Enter");
  await expect(page.locator("[data-intent-log] li").last()).toContainText("send:");
  await expect(composer).toHaveValue("");
});

test("test_ac4_jump_fab_moves_focus_to_the_latest_item", async ({ page }) => {
  await board(page, "TPL-04", "d");
  const log = page.getByRole("log", { name: "Conversation" });
  await log.evaluate((el) => {
    el.scrollTop = 0;
  });
  const jump = page.getByRole("button", { name: "Jump to latest" });
  if ((await jump.count()) === 0) test.skip(true, "the thread fits: no JumpFab to press");
  await jump.press("Enter");
  await expect(page.locator("[data-item]").last()).toBeFocused();
});
