// F-05-T39 (INV-4; DEC-59, ADR-163; F-05 exit criterion 2): the white-label crawl over the portal
// specimens in a browser, at 1400, 720 and 390. "Portal specimens show no Accrued text unless
// secured_footer is on": the product's name may appear only inside the "Secured by" footer, in the
// rendered text (innerText, so CSS-generated and hidden text count as a person reads them) and in
// the attributes a person or assistive technology meets. The gallery calls no API: only the dev
// server is needed (`make dev-fixtures`).
import { expect, test } from "@playwright/test";

const WIDTHS = [1400, 720, 390] as const;

for (const width of WIDTHS) {
  test(`portal specimens show no product name outside the Secured by footer at ${String(width)}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/components");
    await expect(page.getByRole("heading", { name: "Components", level: 1 })).toBeVisible();
    const report = await page.evaluate(() => {
      const PRODUCT = /accrued/i;
      const ATTRIBUTES = ["aria-label", "aria-description", "title", "alt", "placeholder"];
      const sections = [
        ...document.querySelectorAll<HTMLElement>('section[data-surface="portal"]'),
      ];
      const leaks: string[] = [];
      for (const section of sections) {
        const clone = section.cloneNode(true) as HTMLElement;
        for (const footer of clone.querySelectorAll('[data-shell="portal-footer"]'))
          footer.remove();
        // innerText needs layout: measure the live section with its footers hidden instead.
        const hidden = [...section.querySelectorAll<HTMLElement>('[data-shell="portal-footer"]')];
        for (const f of hidden) f.style.setProperty("display", "none");
        const text = section.innerText;
        for (const f of hidden) f.style.removeProperty("display");
        if (PRODUCT.test(text)) leaks.push(`${section.id}: text`);
        for (const el of clone.querySelectorAll<HTMLElement>("*")) {
          for (const name of ATTRIBUTES) {
            const value = el.getAttribute(name);
            if (value !== null && PRODUCT.test(value))
              leaks.push(`${section.id}: ${name}="${value}"`);
          }
        }
        for (const input of section.querySelectorAll<HTMLInputElement>("input, textarea")) {
          if (
            input.closest('[data-shell="portal-footer"]') === null &&
            PRODUCT.test(input.value)
          ) {
            leaks.push(`${section.id}: value`);
          }
        }
      }
      return { count: sections.length, leaks };
    });
    expect(report.count, "portal specimens on the page").toBeGreaterThanOrEqual(7);
    expect(report.leaks).toEqual([]);
  });
}
