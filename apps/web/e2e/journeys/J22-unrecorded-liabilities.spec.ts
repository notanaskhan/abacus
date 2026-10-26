// J22 search for unrecorded liabilities (P-06-T25; blueprint §7.22): Granite Peak's SURL request.
// The agent drafted it in the BH-FS-430 procedure session; Cole Hart approves and sends it to Luis
// Ferrante (SHL-14f). After the uploads are screened, two files are flagged and Cole sends the
// drafted follow-up, a person's click (SHL-20b). Each step runs axe and INV-1 to INV-5. In the
// fixture project step 3 walks SHL-14's own scenario (`?screen=`, G-01-T16); step 4 and
// the other projects wait for `binders.engine` on in E0 and the BND-02 and SHL-20 live swaps.
import { expect, test } from "../harness";

const LIVE =
  "binders.engine is off in E0; the BND-02, SHL-14 and SHL-20 live swaps are P-06-T16's";
const FLAGS = ["binders.engine"];

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J22", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", LIVE);
  });

  test("j22 3: Cole approves and sends the drafted SURL request", async ({ journey }) => {
    await journey.as("cole-hart", "/binders/_binderId_?ov=request:_requestId_:_binderId_", {
      scenario: "SHL-14:f",
      flags: FLAGS,
    });
    await journey.step("J22 step 3: the agent's Draft, owners only (SHL-14f)", async (page) => {
      const drawer = page.getByRole("dialog");
      await expect(drawer.getByLabel("Request", { exact: true })).toHaveValue(
        "Support for 40 subsequent disbursements (SURL)",
      );
      await expect(drawer.getByText("Owners only").first()).toBeVisible();
      await drawer.getByRole("tab", { name: "Activity" }).click();
      await expect(
        drawer.getByText("Drafted by Accrued Agent in the BH-FS-430 procedure session"),
      ).toBeVisible();
    });
    await journey.step("J22 step 3: Cole approves and sends, a person's click", async (page) => {
      const drawer = page.getByRole("dialog");
      await drawer.getByRole("button", { name: "Approve & send to Luis Ferrante" }).click();
      await expect(page.getByText(/Luis Ferrante/).first()).toBeVisible();
    });
  });

  test.fixme(
    "j22 4: screening flags two files, Cole sends the follow-up and both read Returned",
    owner(
      "P-06 · P-06-T16 BND-02 live swap: the SHL-20 card sits in BND-02's dock, and no fixture serves Granite Peak's binder rows with the screening routes · S6, Fri Jan 22, 2027",
    ),
    async ({ journey }) => {
      await journey.as("cole-hart", "/binders/_binderId_?request=_requestId_", {
        scenario: "SHL-20:b",
        flags: FLAGS,
      });
      await journey.step(
        "J22 step 4: the screening card flags two files (SHL-20)",
        async (page) => {
          await expect(page.getByText("Screening · 2 flagged").first()).toBeVisible();
        },
      );
      await journey.step("J22 step 4: the drafted follow-up, sent by Cole", async (page) => {
        await page.getByRole("button", { name: "Draft follow-up" }).click();
        const sheet = page.getByRole("dialog", { name: "Follow-up to Luis Ferrante" });
        await expect(
          sheet.getByText("Drafted by Accrued Agent · edit before sending"),
        ).toBeVisible();
        await expect(
          sheet.getByText("Returning: Granite Rock Logistics — August statement.pdf"),
        ).toBeVisible();
        await expect(sheet.getByText("Returning: Invoice 40117.pdf")).toBeVisible();
        await sheet.getByRole("button", { name: "Send to Luis Ferrante" }).click();
        await expect(sheet).toHaveCount(0);
      });
    },
  );
});
