// ac-test-author: ayushkbhatia
// F-06-T14 (F-06.md §10 item 1, Stories 4.1 to 4.3; SPEC-400 AC-19, AC-21): the T10 steps of the
// f06-document-on-well walk in fixture mode on the gallery at E0, axe on each step (serious and
// critical block). F-06-T22 adds T10c–e (approved, locked, email) and TPL-10a–d.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/specimens/f06-document-on-well.spec.ts`.
import { type Page, expect, test } from "@playwright/test";
import { axeStep } from "../harness/axe";
import { assertInvariants } from "../harness/invariants";
import { persona } from "../harness/personas";

const SAMUEL = persona("samuel-ito");
const E0 = new Date("2026-09-14T09:24:00-05:00");

test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });

async function board(page: Page, st: string): Promise<void> {
  await page.clock.setFixedTime(E0);
  await page.goto(`/components/screens/T10?st=${st}&frame=1&static=1`);
  await expect(page.locator(`[data-artboard='${st}'] [data-template='t10']`)).toBeVisible();
}

test("test_ac19_t10a_drafting_three_skeletons_no_approval_enabled", async ({ page }) => {
  await board(page, "a");
  await expect(page.locator("[data-document='drafting'] > div")).toHaveCount(3);
  await expect(page.getByText("Accrued Agent is drafting the memo")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve…" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Regenerate…" })).toBeDisabled();
  await axeStep(page, "f06-document-on-well T10a", { include: "[data-artboard]" });
  await assertInvariants(page, { step: "f06-document-on-well T10a", persona: SAMUEL });
});

test("test_ac19_t10b_draft_watermark_and_citation_markers", async ({ page }) => {
  await board(page, "b");
  const mark = page.locator("[data-document='watermark']");
  await expect(mark).toHaveText("DRAFT");
  await expect(mark).toHaveAttribute("aria-hidden", "true");
  const paper = page.locator("[data-document='paper']");
  const first = paper.getByText("1", { exact: true }).first();
  await expect(first).toBeVisible();
  // A marker lights the structure row it cites (E1).
  await first.hover();
  await expect(page.locator("[data-match='t10:prior-year'][data-lit]")).toBeVisible();
  await axeStep(page, "f06-document-on-well T10b", { include: "[data-artboard]" });
  await assertInvariants(page, { step: "f06-document-on-well T10b", persona: SAMUEL });
});

test("test_ac21_t10b_approve_is_a_named_persons_control", async ({ page }) => {
  await board(page, "b");
  const approve = page.getByRole("button", { name: "Approve…" });
  await expect(approve).toBeEnabled();
  await expect(approve).toHaveAttribute("data-human-verb", "Approve");
  await expect(page.locator("[data-actor='agent'] [data-human-verb]")).toHaveCount(0);
});

// ---- F-06-T22: T10c–e and TPL-10a–d, axe on every state ----------------------------------------

test("test_t22_t10c_approved_letter_shows_who_and_no_approve", async ({ page }) => {
  await board(page, "c");
  await expect(page.getByText("Samuel Ito · Sep 12")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve…" })).toHaveCount(0);
  await expect(page.locator("[data-document='paper'] [data-actor='agent']")).toHaveCount(0);
  await axeStep(page, "f06-document-on-well T10c", { include: "[data-artboard]" });
  await assertInvariants(page, { step: "f06-document-on-well T10c", persona: SAMUEL });
});

test("test_t22_t10d_locked_letter_says_why_and_edits_nothing", async ({ page }) => {
  await board(page, "d");
  // The visible note; its sr-only twin describes the disabled controls.
  await expect(page.getByText("Out for signature since Sep 10").first()).toBeVisible();
  await expect(page.locator("[data-document='clauses'] [role='switch']").first()).toBeDisabled();
  await axeStep(page, "f06-document-on-well T10d", { include: "[data-artboard]" });
  await assertInvariants(page, { step: "f06-document-on-well T10d", persona: SAMUEL });
});

test("test_t22_t10e_email_draft_one_dark_call_to_action", async ({ page }) => {
  await board(page, "e");
  await expect(page.locator("[data-document='watermark']")).toHaveText("DRAFT");
  await expect(page.locator("[data-email='cta']")).toHaveCount(1);
  await expect(page.locator("[data-document='paper'] [data-actor='agent']")).toHaveCount(0);
  await axeStep(page, "f06-document-on-well T10e", { include: "[data-artboard]" });
  await assertInvariants(page, { step: "f06-document-on-well T10e", persona: SAMUEL });
});

for (const st of ["a", "b", "c", "d"] as const) {
  test(`test_t22_tpl10${st}_axe_and_invariants`, async ({ page }) => {
    await page.clock.setFixedTime(E0);
    await page.goto(`/components/screens/TPL-10?st=${st}&frame=1&static=1`);
    await expect(page.locator(`[data-artboard='${st}'] [data-template='t10']`)).toBeVisible();
    await expect(page.locator("[data-actor='agent'] [data-human-verb]")).toHaveCount(0);
    await axeStep(page, `f06-document-on-well TPL-10${st}`, { include: "[data-artboard]" });
    await assertInvariants(page, { step: `f06-document-on-well TPL-10${st}`, persona: SAMUEL });
  });
}
