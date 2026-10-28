// R-01-T31: the portal's keyboard-only paths, in the portal entry on fixtures (journey harness:
// axe and INV-1 to INV-5 after each step). Claire Feld, with no pointer:
//
// - the drop path (POR-03): Tab reaches the Documents drop zone, Enter opens the file picker, and
//   the chosen file is sorted and shows as uploading;
// - the sheet path (POR-04 over POR-03): Tab reaches a request, Enter opens its sheet with focus
//   inside it, Tab stays inside the sheet, Escape closes it and focus returns to the request.
//
// Full stack and staging walk these once the portal BFF answers there (P-08-T10's), as J12 does.
import { expect, test } from "../harness";
import { DEMO_INSTANT } from "../harness";

const REQUEST = "Form 1095-C From Mercer Hill Health";
const FILE =
  "../../backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/files/cch-axcess-client-list.csv";

async function tabTo(
  page: import("@playwright/test").Page,
  matches: (el: { label: string; text: string }) => boolean,
  most = 300,
): Promise<void> {
  const seen: string[] = [];
  for (let i = 0; i < most; i += 1) {
    await page.keyboard.press("Tab");
    const here = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      return {
        label: el?.getAttribute("aria-label") ?? "",
        text: (el?.innerText ?? "").replace(/\s+/g, " ").trim(),
      };
    });
    if (matches(here)) return;
    seen.push(here.label || here.text.slice(0, 40));
  }
  throw new Error(`Tab never reached the control: ${seen.slice(0, 30).join(" · ")}`);
}

test.describe("portal keyboard-only paths (R-01-T31)", () => {
  test.beforeEach(({ journey }) => {
    test.fixme(journey.project !== "fixture", "the portal sign-in BFF is P-08-T10's (S6)");
  });

  test("POR-03: Tab to the drop zone, Enter, choose a file", async ({ journey }) => {
    await journey.as("claire-feld", "/documents", { clock: DEMO_INSTANT });
    const page = journey.page;
    await journey.step("POR-03a by keyboard: the documents", async () => {
      await expect(page.getByText(REQUEST).first()).toBeVisible();
    });
    await journey.step("POR-03 by keyboard: Enter on the drop zone opens the picker", async () => {
      await tabTo(page, (el) => el.label.startsWith("Upload documents"));
      const chooser = page.waitForEvent("filechooser");
      await page.keyboard.press("Enter");
      const picker = await chooser;
      // Any small synthetic file the portal takes (a CSV), from the repository (Playwright's cwd):
      // the drop sorts it, and the upload shows in flight.
      await picker.setFiles(FILE);
      await expect(page.getByText(/^Uploading \d+ files?…$/).first()).toBeVisible();
    });
  });

  test("POR-04: Tab to a request, Enter opens its sheet, Escape returns focus", async ({
    journey,
  }) => {
    await journey.as("claire-feld", "/documents", { clock: DEMO_INSTANT });
    const page = journey.page;
    await expect(page.getByText(REQUEST).first()).toBeVisible();
    // The title is the request's own button (not Upload… or Ignore); matched on its words, which the
    // screen may join with a non-breaking hyphen.
    const isRequest = (t: string): boolean =>
      t.includes("1095") && t.includes("Mercer Hill Health") && !t.startsWith("Ignore");
    await tabTo(page, (el) => isRequest(el.label) || isRequest(el.text));
    await page.keyboard.press("Enter");
    const sheet = page.getByRole("dialog");
    await journey.step(
      "POR-04a by keyboard: the sheet opens with focus inside it",
      async () => {
        await expect(sheet.getByText("To do · requested Feb 3")).toBeVisible();
        expect(
          await sheet.evaluate((el) => el.contains(document.activeElement)),
          "focus moves into the sheet",
        ).toBe(true);
        for (let i = 0; i < 25; i += 1) {
          await page.keyboard.press("Tab");
          expect(
            await sheet.evaluate((el) => el.contains(document.activeElement)),
            "Tab stays inside the sheet",
          ).toBe(true);
        }
      },
      { include: "[role='dialog']" },
    );
    await journey.step(
      "POR-04 by keyboard: Escape closes; focus returns to the request",
      async () => {
        await page.keyboard.press("Escape");
        await expect(sheet).toHaveCount(0);
        // POR-03 draws again behind the closed sheet; focus lands on the request's title once it does.
        await expect
          .poll(() =>
            page.evaluate(() => {
              const el = document.activeElement as HTMLElement | null;
              return el?.hasAttribute("data-open-title") === true
                ? (el.innerText || "").replace(/\s+/g, " ")
                : `not a request title: ${el?.tagName ?? "none"}`;
            }),
          )
          .toContain("Mercer Hill Health");
      },
    );
  });
});
