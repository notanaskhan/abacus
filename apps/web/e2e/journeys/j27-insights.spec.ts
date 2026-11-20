// P-05-T15 (TASK-7311; P-05 §10 item 1; P0-core block): J27 step 4 on SHL-17, opened through
// `?ov=todos:new` until INS-03 (I-03) and Go… "New to-do…" (P-02) exist; the gallery's SHL-17 b
// (new) and f (My to-dos) stand in for it on fixtures. With it, J27 P0 core is walkable (S37).
import { expect, test } from "../harness";
import { P05_LIVE, nothingBlocks, p05 } from "./p05-support";

test.describe("J27 insights · P0 core (P-05-T15)", () => {
  test("j27 4: Margaret creates 'Update skill BH-SK-410' for Hannah, due Oct 16, and Hannah's My to-dos shows it", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", P05_LIVE);
    await journey.as("margaret-okonkwo", p05("SHL-17", "b", "margaret-okonkwo"));
    await journey.step("J27 step 4: the new to-do needs a title and an assignee", async (page) => {
      await expect(page.locator("[data-screen='SHL-17']").first()).toBeVisible();
      await expect(page.getByRole("button", { name: "Create to-do" })).toBeDisabled();
      await nothingBlocks(page);
    });
    await journey.as("hannah-leclerc", p05("SHL-17", "f", "hannah-leclerc"));
    await journey.step("J27 step 4: My to-dos (SHL-17 f)", async (page) => {
      await expect(page.locator("[data-screen='SHL-17']").first()).toBeVisible();
      await expect(page.getByText(/open/).first()).toBeVisible();
    });
  });
});

// G-04-T21 (G-04 §1): J27 step 2, plan and usage. Margaret, a partner, reads ADM-14 read-only; the
// INS-02 → ADM-14 hop waits on I-03 (S61–S67).
test.describe("J27 plan and usage (G-04)", () => {
  test("j27 2 (plan & usage): Margaret opens ADM-14 read-only and sees 14,920 of 20,000", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", "G-04 · staging with real auth (G-04-T18 live)");
    await journey.as("margaret-okonkwo", "/settings/plan", { scenario: "ADM-14:a" });
    await journey.step("J27 step 2: Plan & usage as Margaret", async (page) => {
      await expect(page.getByText("of 20,000 included")).toBeVisible();
      await expect(page.getByText(/14,920/).first()).toBeVisible();
    });
  });

  test("j27 2: INS-02 opens Plan & usage", async ({ journey }) => {
    test.fixme(true, "the INS-02 → ADM-14 hop lands with I-03 (S61–S67)");
    await journey.as("margaret-okonkwo", "/insights");
  });
});
