// J10 month-end close (P-06-T25; blueprint §7.10): Raj Malhotra's August close intake for
// Copperleaf Coffee Roasters, hosted on BND-02 until C-01 builds CLS-03. Raj adds the ad hoc
// Sound Electric invoice to the eight recurring requests and sends it, so the binder holds nine.
// Each step runs axe and INV-1 to INV-5. No project walks it yet: SHL-14d's close fixture already
// holds the invoice (adding it again reads "7 of 10") and answers no binder rows, so the step
// waits for the BND-02 live swap or CLS-03 (C-01).
import { expect, test } from "../harness";

const INVOICE = "Sound Electric invoice — Aug 18 ($3,200)";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J10", () => {
  test.fixme(
    "j10 2: Raj adds the Sound Electric invoice and publishes 9 requests",
    owner(
      "P-06 · P-06-T16 BND-02 live swap (or C-01 CLS-03): SHL-14d's fixture is the post-add state and serves no binder rows · S6, Fri Jan 22, 2027",
    ),
    async ({ journey }) => {
      await journey.as("raj-malhotra", "/binders/_binderId_?ov=request:new:_binderId_", {
        scenario: "SHL-14:d",
        flags: ["binders.engine"],
      });
      await journey.step("J10 step 2: the composer on the August close intake", async (page) => {
        await expect(page.getByRole("heading", { name: "New request" })).toBeVisible();
      });
      await journey.step(
        "J10 step 2: Raj writes the ad hoc request and sends it",
        async (page) => {
          const drawer = page.getByRole("dialog");
          await drawer.getByLabel("Request", { exact: true }).fill(INVOICE);
          await drawer.getByLabel("Due").fill("2026-09-18");
          await drawer.getByRole("button", { name: /^Save & send/ }).click();
          await expect(page.getByText(/^Request sent/).first()).toBeVisible();
        },
      );
      await journey.step("J10 step 2: the close intake holds nine requests", async (page) => {
        await expect(page.getByRole("tab", { name: /Requests\s*9/ })).toBeVisible();
        await expect(page.getByText(INVOICE).first()).toBeVisible();
      });
    },
  );
});
