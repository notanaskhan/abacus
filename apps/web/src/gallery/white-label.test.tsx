// F-05-T39 acceptance (INV-4; DEC-59, ADR-163): "Portal specimens show no Accrued text unless
// secured_footer is on." Every specimen the registry marks `surface: "portal"` renders here, and
// the product's name may appear only inside the "Secured by" footer, which the firm turns on. The
// crawl reads text and every attribute a person or assistive technology meets (aria-label, title,
// alt, placeholder, value). The Playwright twin (e2e/ds-white-label.spec.ts) runs the same crawl
// in a browser at 1400, 720 and 390.
import { SPECIMENS } from "@abacus/ui/specimens";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

const PRODUCT = /accrued/i;
const ATTRIBUTES = ["aria-label", "aria-description", "title", "alt", "placeholder", "value"];

/** Every place the product's name shows outside the Secured by footer. */
function leaks(root: HTMLElement): string[] {
  const out: string[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    const text = node.textContent ?? "";
    if (!PRODUCT.test(text)) continue;
    if (node.parentElement?.closest('[data-shell="portal-footer"]') !== null) continue;
    out.push(`text: ${text.trim()}`);
  }
  for (const el of root.querySelectorAll<HTMLElement>("*")) {
    if (el.closest('[data-shell="portal-footer"]') !== null) continue;
    for (const name of ATTRIBUTES) {
      const value = el.getAttribute(name);
      if (value !== null && PRODUCT.test(value)) out.push(`${name}: ${value}`);
    }
  }
  return out;
}

const PORTAL = SPECIMENS.filter((s) => s.surface === "portal");

describe("the crawl bites", () => {
  it("finds the name in text, in an attribute, and not inside the footer", () => {
    const { container } = render(
      <div>
        <p>Powered by Accrued</p>
        <button type="button" aria-label="Open accrued help" />
        <footer data-shell="portal-footer">
          <span>Secured by</span>
          <span aria-label="Accrued">accrued·</span>
        </footer>
      </div>,
    );
    expect(leaks(container)).toEqual([
      "text: Powered by Accrued",
      "aria-label: Open accrued help",
    ]);
  });
});

describe("white label: portal specimens", () => {
  it("the registry marks the portal's specimens", () => {
    expect(PORTAL.map((s) => s.id)).toEqual(
      expect.arrayContaining([
        "c-00-portal-toolbar",
        "t7-portal-layout",
        "c-16-request-rows",
        "t7-client-portal",
        "tpl-07",
        "t15-auth-card",
        "tpl-15",
      ]),
    );
  });

  for (const s of PORTAL) {
    it(`${s.id} shows no product name outside the Secured by footer`, () => {
      const { container } = render(<s.Component />);
      expect(leaks(container)).toEqual([]);
    });
  }

  it("the footer is the firm's choice: shown only where a frame turned it on", () => {
    const layout = PORTAL.find((s) => s.id === "t7-portal-layout");
    if (layout === undefined) throw new Error("t7-portal-layout is not registered");
    const { container } = render(<layout.Component />);
    const footers = [...container.querySelectorAll('[data-shell="portal-footer"]')];
    expect(footers).toHaveLength(1);
    expect(footers[0]?.closest('[data-artboard="t7-secured"]')).not.toBeNull();
  });
});
