// ac-test-author: ayushkbhatia
// F-06-T13 (F-06.md §10 item 1; Stories 1.1 to 1.8): the f06-signing specimen walk in fixture mode
// on the /components gallery, the demo clock fixed at E0, axe on every step (serious and critical
// block) and INV-1 to INV-5 asserted for Mira Kapoor. Provider mode TPL-16b → a (the provider's
// view) → the return, pending → d; e (DF-11 copy, no retry); f (a reason is required); g at 390;
// the native artboards T16a, TPL-16a and TPL-16c as screenshots only; signer separation.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/specimens/f06-signing.spec.ts`.
import { type Page, expect, test } from "@playwright/test";
import { axeStep } from "../harness/axe";
import { assertInvariants } from "../harness/invariants";
import { persona } from "../harness/personas";

const MIRA = persona("mira-kapoor");
const E0 = new Date("2026-09-14T09:24:00-05:00");

async function board(page: Page, st: string): Promise<void> {
  await page.clock.setFixedTime(E0);
  await page.goto(`/components/screens/TPL-16?st=${st}&frame=1&static=1`);
  await expect(page.locator(`[data-artboard='${st}'] [data-template='t16']`)).toBeVisible();
}

async function step(page: Page, name: string): Promise<void> {
  await axeStep(page, `f06-signing ${name}`, { include: "[data-artboard]" });
  await assertInvariants(page, { step: `f06-signing ${name}`, persona: MIRA });
}

test.describe("f06-signing at 1440", () => {
  test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });

  test("test_ac1_provider_mode_walk_b_a_pending_d", async ({ page }) => {
    // b: Mira reviews; Dev signed Sep 9, Mira's two fields are open.
    await board(page, "b");
    const header = page.locator("[data-signing='envelope-header']");
    await expect(header).toContainText("1 of 2 signed");
    await expect(page.locator("[data-signing='documents']")).toContainText("Dev · Sep 9");
    await expect(page.locator("[data-signing='steps']")).toContainText("$2,296");
    await expect(page.locator("[data-signing='steps']")).toContainText("$410");
    await step(page, "TPL-16b");

    // a: the provider's view, titled and sandboxed; nothing of the provider is our markup.
    await board(page, "a");
    const frame = page.locator("[data-signing='provider-frame']");
    await expect(frame).toHaveAttribute("title", "Verify your identity and sign: Form 8879");
    await expect(frame).toHaveAttribute(
      "sandbox",
      "allow-scripts allow-same-origin allow-forms allow-popups",
    );
    await expect(frame).toHaveAttribute("referrerpolicy", "no-referrer");
    await expect(page.locator("[data-signing='well'] [data-signing='page']")).toHaveCount(0);
    await expect(page.getByText(/DocuSign/i)).toHaveCount(0);
    await step(page, "TPL-16a provider view");

    // The provider returned with an event: a hint. The server still says unsigned: never Completed.
    await board(page, "pending");
    await expect(page.locator("[data-signing='pending-confirmation']")).toContainText(
      "Checking your signature",
    );
    await expect(page.getByText("Completed", { exact: true })).toHaveCount(0);
    await step(page, "return, pending");

    // d: the server reports both signed: completion card, six evidence rows, Completed.
    await board(page, "d");
    await expect(header).toContainText("Completed");
    const completion = page.locator("[data-signing='completion']");
    await expect(completion).toContainText("Signed. Thank you, Mira.");
    await expect(completion.locator("[data-signing='evidence'] dt")).toHaveCount(6);
    await expect(completion).toContainText("SHA-256 recorded");
    await step(page, "TPL-16d");
  });

  test("test_ac2_signer_separation_only_the_viewers_fields_act", async ({ page }) => {
    await board(page, "b");
    const fields = page.getByRole("button", { name: /^Sign here:/ });
    // Mira's spouse signature on the shown document: Dev's field is never a control.
    for (const field of await fields.all()) {
      await expect(field).toHaveAccessibleName(/spouse signature/);
    }
    await expect(page.getByText("Dev Kapoor · signed electronically Sep 9, 2026")).toBeVisible();
    await expect(page.getByRole("button", { name: /taxpayer signature/ })).toHaveCount(0);
  });

  test("test_ac4_e_verification_failed_df11_without_retry", async ({ page }) => {
    await board(page, "e");
    const card = page.locator("[data-signing='verification-failed']");
    await expect(card).toContainText("We couldn't verify your identity.");
    await expect(card).toContainText("paper form");
    await expect(card).toContainText("Dina Sato");
    await expect(card.locator("button")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /try again|retry|text me|sms/i })).toHaveCount(
      0,
    );
    await step(page, "TPL-16e");
  });

  test("test_ac5_f_decline_waits_for_a_reason", async ({ page }) => {
    await board(page, "f");
    // The specimen holds the dialog open in place (`declineForceState`): a named group, not a
    // modal layer; a click on "Decline…" opens the same content as a dialog.
    const dialog = page
      .getByRole("dialog", { name: "Decline to sign?" })
      .or(page.getByRole("group", { name: "Decline to sign?" }));
    await expect(dialog).toBeVisible();
    const confirm = dialog.locator("[data-signing='decline-confirm']");
    await expect(confirm).toBeDisabled();
    for (const reason of [
      "The amounts look wrong",
      "I have a question first",
      "Someone else should sign",
      "Other",
    ]) {
      await expect(dialog.getByRole("radio", { name: reason })).toBeVisible();
    }
    await dialog.getByRole("radio", { name: "I have a question first" }).check();
    await expect(confirm).toBeEnabled();
    await axeStep(page, "f06-signing TPL-16f", { include: "[data-artboard]" });
  });

  test("test_ac7_native_artboards_are_screenshots_only", async ({ page }) => {
    // T16a is a placeholder that points at the handoff screenshot; no native identity part exists.
    await page.clock.setFixedTime(E0);
    await page.goto("/components?frame=1&static=1");
    const t16a = page.locator("section[id='t16-signing-ceremony'] [data-artboard='t16a']");
    await expect(t16a).toContainText("Tier C screenshot only");
    // TPL-16a in production is the provider's view: no KBA question, no timer, no adopt dialog.
    await board(page, "a");
    await expect(page.getByText(/Question \d of \d/)).toHaveCount(0);
    await expect(page.getByText(/Answer within/)).toHaveCount(0);
    await expect(page.getByRole("dialog", { name: "Adopt your signature" })).toHaveCount(0);
  });

  test("test_ac8_no_agent_and_the_signers_own_name", async ({ page }) => {
    for (const st of ["b", "d"]) {
      await board(page, st);
      await expect(page.locator("[data-actor='agent']")).toHaveCount(0);
      await expect(page.getByText(/Accrued/)).toHaveCount(0);
    }
    // The completion names the signer; the evidence record never names the firm or the product.
    await expect(page.locator("[data-signing='completion']")).toContainText("Mira");
    await expect(page.locator("[data-signing='evidence']")).not.toContainText("Brightwater Hale");
  });
});

test.describe("f06-signing at 390", () => {
  test.use({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    reducedMotion: "reduce",
  });

  test("test_ac6_g_fits_the_phone", async ({ page }) => {
    await board(page, "g");
    await expect(page.locator("[data-signing='step-chips']")).toBeVisible();
    await expect(page.locator("[data-signing='mobile-sign-bar']")).toHaveAttribute(
      "data-height",
      "64",
    );
    const wide = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(wide).toBe(false);
    await step(page, "TPL-16g");
  });
});
