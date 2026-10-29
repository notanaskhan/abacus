// F-06-T12: independent acceptance tests for the portal mobile specimen (ADR-078), written from
// the F-06 row and docs/screens/TPL-19.md, not from the builder's tests. "Tests prove 44 by 44
// targets, no firm-shell imports in portal specimens, no Accrued text or blue, and zero serious axe
// findings at 390 px." Geometry (44 × 44) and axe need a browser: apps/web/e2e/screens/TPL-19.spec.ts.
// Here: white label, the import boundary, Approvals for households, and the 44 classes on the
// capture kit's own targets.
import { cleanup, render, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { portalNav } from "../templates/portal-layout";
import { Tpl19Specimen } from "./tpl19";

afterEach(cleanup);

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..");

/** The portal mobile specimen and the kit it draws, by path under packages/ui/src. */
const PORTAL_FILES = [
  "specimens/tpl19.tsx",
  "requests/capture.tsx",
  "requests/binder.tsx",
  "templates/portal-layout.tsx",
  "templates/portal-mobile-home.tsx",
  "layout/mobile-tab-bar.tsx",
];

/** The firm shell: the toolbar, the record header and cockpit, the firm nav and the screens. */
const FIRM_SHELL = [
  /(^|\/)toolbar$/u,
  /(^|\/)record-header$/u,
  /(^|\/)record-cockpit$/u,
  /(^|\/)firm(\/|$)/u,
  /(^|\/)nav-areas$/u,
  /(^|\/)screens(\/|$)/u,
  /^@abacus\/web/u,
];

function importsOf(file: string): string[] {
  const text = readFileSync(join(SRC, file), "utf8");
  return [...text.matchAll(/^\s*import\s[^;]*?from\s+"([^"]+)";/gmu)].map((m) => m[1] ?? "");
}

describe("F-06-T12 portal import boundary", () => {
  it("no portal mobile file imports the firm shell or a firm screen", () => {
    const crossings = PORTAL_FILES.flatMap((f) =>
      importsOf(f)
        .filter((source) => FIRM_SHELL.some((re) => re.test(source)))
        .map((source) => `${f} → ${source}`),
    );
    expect(crossings).toEqual([]);
  });

  it("the boundary check sees imports at all (guards against a vacuous pass)", () => {
    expect(importsOf("specimens/tpl19.tsx").length).toBeGreaterThan(3);
  });
});

describe("F-06-T12 white label", () => {
  it("no frame says Accrued", () => {
    const { container } = render(<Tpl19Specimen />);
    expect(container.textContent).not.toMatch(/Accrued/iu);
  });

  it("no frame draws blue (no blue class, the typed-form blue or a blue hex)", () => {
    const { container } = render(<Tpl19Specimen />);
    expect(container.innerHTML).not.toMatch(/blue|#6A98E8|#0000FF|#00F\b|rgb\(0,\s*0,\s*255\)/iu);
  });

  it("the portal kit sources name no product mark", () => {
    for (const f of ["specimens/tpl19.tsx", "requests/capture.tsx"]) {
      expect([f, readFileSync(join(SRC, f), "utf8")]).not.toEqual([
        f,
        expect.stringMatching(/["'`][^"'`]*Accrued[^"'`]*["'`]/u),
      ]);
    }
  });
});

describe("F-06-T12 Approvals hidden for households", () => {
  it("a household's nav has no Approvals; an entity's has it", () => {
    expect(portalNav("individual").map((i) => i.label)).not.toContain("Approvals");
    expect(portalNav("entity").map((i) => i.label)).toContain("Approvals");
  });

  it("frame 7's More sheet over Claire's home lists no Approvals", () => {
    const { container } = render(<Tpl19Specimen />);
    const sheet = container.querySelector<HTMLElement>(
      '[data-artboard="tpl-19-7"] [data-shell="more-sheet"]',
    );
    expect(sheet).not.toBeNull();
    const items = within(sheet as HTMLElement)
      .getAllByRole("menuitem")
      .map((i) => i.textContent);
    expect(items).not.toContain("Approvals");
  });
});

describe("F-06-T12 hit areas declared on the capture kit", () => {
  it("every control in frames 5 and 6 declares at least 44 px of height", () => {
    const { container } = render(<Tpl19Specimen />);
    const short: string[] = [];
    for (const id of ["tpl-19-5", "tpl-19-6", "tpl-19-6-ring"]) {
      const board = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
      const controls = board?.querySelectorAll<HTMLElement>(
        "[data-capture] button, [data-capture] label[for], [data-request] button",
      );
      for (const el of controls ?? []) {
        const h = /\bh-\[(\d+)px\]|min-h-\[(\d+)px\]/u.exec(el.className);
        const px = Number(h?.[1] ?? h?.[2] ?? 0);
        if (px < 44) short.push(`${id}: ${el.getAttribute("aria-label") ?? el.textContent}`);
      }
    }
    expect(short).toEqual([]);
  });
});
