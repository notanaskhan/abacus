// POR-06 · Sign (N-02-T40; N-02 §10.1) on the harness, through the portal's real `/sign` route:
// on each state's own scenario in the fixture project (the portal entry's `?screen=POR-06`), and
// on the seeded stack in the full-stack project (the fake provider in CI, the demo account
// nightly), where Tess Moreno reads her Sign area. The provider's own view is never scripted.
import { expect, test } from "../harness";
import { M13, skipUnhosted } from "./support";

test.describe("POR-06 sign, full stack (N-02-T40)", () => {
  test.beforeEach(({ journey }) => {
    skipUnhosted(journey.project);
  });

  test("Tess's Sign area lists what is hers to sign", async ({ journey }) => {
    test.fixme(journey.project === "staging" || journey.project === "canary", M13);
    await journey.as(
      "tess-moreno",
      "/sign",
      journey.project === "fixture" ? { scenario: "POR-06:list" } : {},
    );
    await journey.step("POR-06 list: the Sign area", async (page) => {
      await expect(page.getByRole("heading", { name: /Sign/ }).first()).toBeVisible();
      await expect(page.getByText(/Accrued/)).toHaveCount(0); // white-labelled (D2)
    });
  });

  test("a declined envelope reads as declined, with nothing left to sign (POR-06 g)", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", M13);
    await journey.as("tess-moreno", "/sign", { scenario: "POR-06:g" });
    await journey.step("POR-06 g: declined", async (page) => {
      await expect(page.getByText(/[Dd]eclined/).first()).toBeVisible();
    });
  });
});
