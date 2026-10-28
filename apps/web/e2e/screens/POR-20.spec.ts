// POR-20 a–l in fixture mode (R-01-T25 built them; R-01-T31 tests them): every artboard at
// 1440×900, DPR 2, from the /components gallery on fixtures, with axe at zero serious or critical
// findings; and the L7 white-label crawl extended to the email itself (DEC-01, ADR-133): every
// template's rendered HTML (the preview frame's document, as a client's mail program draws it) and
// its plain-text part, read at 600 and at 390, carry no "Accrued" anywhere: not in the text a
// person reads, not in an attribute, not in the markup. POR-20 is a firm screen; the email it
// previews is the client's.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/POR-20.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const PRODUCT = /accrued/i;

const ARTBOARDS = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"] as const;

// The template each artboard opens on (fixtures/scenarios/POR-20.ts OPENS): one per template.
const TEMPLATES = [
  { st: "a", template: "reminder" },
  { st: "e", template: "invitation" },
  { st: "f", template: "signature_request" },
  { st: "g", template: "deliverable_ready" },
  { st: "h", template: "confirmation_request" },
  { st: "i", template: "reconnect_request" },
] as const;

const FRAME = "iframe[title='Email preview']";

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

async function open(page: Page, st: string): Promise<void> {
  await page.goto(`/components/screens/POR-20?st=${st}&frame=1`);
  await expect(page.locator(`[data-artboard='${st}']`)).toBeVisible();
}

for (const st of ARTBOARDS) {
  test(`POR-20${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await open(page, st);
    await expect(page.locator("[data-screen='POR-20']").first()).toBeVisible();
    // The email's frame is sandboxed with no scripts, so axe cannot run inside it (it would wait
    // for the frame until the test times out); its words are the crawl's below.
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .exclude(FRAME)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}

for (const { st, template } of TEMPLATES) {
  test(`POR-20 ${template}: the rendered email and its plain text never say Accrued, at 600 and 390`, async ({
    page,
  }) => {
    await open(page, st);
    const frame = page.locator(FRAME).first();
    await expect(frame).toBeVisible();
    // The markup as the mail program receives it (the frame's srcdoc), then as it lays out.
    const markup = (await frame.getAttribute("srcdoc")) ?? "";
    expect(markup.length).toBeGreaterThan(200);
    expect(markup).not.toMatch(PRODUCT);
    for (const width of [600, 390] as const) {
      await frame.evaluate((el, w) => {
        (el as HTMLElement).style.width = `${String(w)}px`;
      }, width);
      const body = frame.contentFrame().locator("body");
      await expect(body).toBeVisible();
      const read = await body.evaluate((el) => {
        const attributes = ["alt", "title", "aria-label", "href", "src"];
        const values = [...el.querySelectorAll("*")].flatMap((n) =>
          attributes.map((a) => n.getAttribute(a) ?? ""),
        );
        return { text: (el as HTMLElement).innerText, attributes: values.join(" ") };
      });
      expect(read.text.trim().length, `${template} at ${String(width)}`).toBeGreaterThan(20);
      expect(read.text, `${template} text at ${String(width)}`).not.toMatch(PRODUCT);
      expect(read.attributes, `${template} attributes at ${String(width)}`).not.toMatch(PRODUCT);
    }
    // The plain-text part, as a text-only mail program shows it.
    await page.getByRole("button", { name: "Show plain text" }).first().click();
    const plain = page.locator(`[data-artboard='${st}'] pre`).first();
    await expect(plain).toBeVisible();
    const text = await plain.innerText();
    expect(text.trim().length).toBeGreaterThan(20);
    expect(text).not.toMatch(PRODUCT);
  });
}
