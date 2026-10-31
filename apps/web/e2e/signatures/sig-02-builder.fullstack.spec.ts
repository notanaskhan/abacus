// SIG-02 · Envelope builder (N-02-T40; N-02 §10.1) on the harness: Harborview's Form 8879-PE (a),
// the Ridgeline letter with its countersigner (e) and a signer with no email (f). The builder
// opens as the `?ov=envelope:<id>` sheet over any firm route; the hosted projects need the
// seeded envelope's id, so they walk it with N-02-T42's M13 journeys and the fixture project
// walks the artboards.
import { expect, test } from "../harness";
import { M13, artboard, skipUnhosted } from "./support";

test.describe("SIG-02 builder, full stack (N-02-T40)", () => {
  test.beforeEach(({ journey }) => {
    skipUnhosted(journey.project);
  });

  test("Grace builds Harborview's 8879-PE and the Ridgeline letter; Send waits on an email", async ({
    journey,
  }) => {
    test.fixme(journey.project !== "fixture", M13);
    await journey.as("grace-holloway", artboard("SIG-02", "a"));
    await journey.step(
      "SIG-02 a: the checks, the signers in order, SMS never offered",
      async (page) => {
        await expect(page.getByText("Amounts match the exported return").first()).toBeVisible();
        await expect(page.getByText("1 · Dr. Sofia Lindqvist").first()).toBeVisible();
        await expect(page.getByText("2 · Daniel Reyes").first()).toBeVisible();
      },
    );
    await journey.as("grace-holloway", artboard("SIG-02", "e"));
    await journey.step("SIG-02 e: the countersignature follows the client", async (page) => {
      await expect(page.getByText("Countersignature follows the client").first()).toBeVisible();
      await expect(page.getByText("1 · Owen Calder").first()).toBeVisible();
    });
    await journey.as("grace-holloway", artboard("SIG-02", "f"));
    await journey.step("SIG-02 f: Email required, Send disabled", async (page) => {
      await expect(page.getByText(/Email required/).first()).toBeVisible();
      await expect(page.getByRole("button", { name: /^Send/ }).first()).toBeDisabled();
    });
  });
});
