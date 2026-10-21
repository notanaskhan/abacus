// F-05-T13 (SPEC-048 B3): every handoff icon name resolves on lucide-react@1.52.0, strokes stay in
// viewBox units at sizes 12 to 22, and the custom glyphs carry no brand colours. The gallery lists
// every name at /components/icons (apps/web/src/gallery/icons.test.tsx).
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import dynamicIconImports from "lucide-react/dynamicIconImports";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  AgentMonogram,
  AtomMark,
  HalfDisc,
  HANDOFF_IN_KITS,
  HANDOFF_MISSING,
  HANDOFF_SET,
  ICON_NAMES,
  ICON_SIZES,
  ICON_STROKE,
  ICON_SUBSTITUTES,
  ICONS,
  Icon,
  type IconName,
  VENDOR_TONES,
  VendorTile,
  vendorMonogram,
} from "./icons";

const LUCIDE = new Set(Object.keys(dynamicIconImports));

const pascal = (kebab: string): string =>
  kebab
    .split("-")
    .map((p) => p.slice(0, 1).toUpperCase() + p.slice(1))
    .join("");

const render = (name: IconName, size: number, extra: Record<string, unknown> = {}): string =>
  renderToStaticMarkup(createElement(Icon, { name, size: size as never, ...extra }));

// handoff/design-tokens.md "Icons used but missing from the set" (22 rows), DF-37.
const DF37_TABLE = [
  "arrow-right-left",
  "book-marked",
  "circle-dashed",
  "circle-dot",
  "circle-plus",
  "copy-plus",
  "file-down",
  "file-output",
  "gantt-chart",
  "git-branch",
  "git-compare",
  "layout-template",
  "link-2-off",
  "list-plus",
  "message-square-text",
  "mountain",
  "network",
  "package-check",
  "refresh-ccw",
  "rows-3",
  "scan-search",
  "ticket",
];

describe("ac1 the handoff names", () => {
  it("has the 212 names accrued-ui.js ships and the 22 it lacks (234 in all)", () => {
    expect(HANDOFF_SET).toHaveLength(212);
    expect(HANDOFF_MISSING).toHaveLength(22);
    expect([...HANDOFF_MISSING].sort()).toEqual(DF37_TABLE);
    expect(HANDOFF_SET.length + HANDOFF_MISSING.length).toBe(234);
  });

  it("names DF-37's five by hand among the missing", () => {
    for (const n of ["ticket", "link-2-off", "layout-template", "git-branch", "network"]) {
      expect(HANDOFF_MISSING as readonly string[]).toContain(n);
    }
  });

  it("registers the 18 more that kits use, with no name twice", () => {
    expect(HANDOFF_IN_KITS).toHaveLength(18);
    expect(ICON_NAMES).toHaveLength(252);
    expect(new Set(ICON_NAMES).size).toBe(ICON_NAMES.length);
    expect([...ICON_NAMES]).toEqual([...ICON_NAMES].sort());
  });

  it("uses kebab-case lowercase names only", () => {
    for (const n of ICON_NAMES) expect(n, n).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/u);
  });
});

describe("ac2 every mapped name resolves on lucide-react 1.52.0", () => {
  it("has a component for every name", () => {
    for (const name of ICON_NAMES) expect(ICONS[name], name).toBeDefined();
    expect(Object.keys(ICONS).sort()).toEqual([...ICON_NAMES]);
  });

  it("maps each name to the lucide icon it says: the name itself or its recorded substitute", () => {
    for (const name of ICON_NAMES) {
      const target = ICON_SUBSTITUTES[name] ?? name;
      expect(LUCIDE.has(target), `${name} -> ${target} is not in lucide`).toBe(true);
      expect(ICONS[name].displayName, name).toBe(pascal(target));
    }
  });

  it("records a real change for every substitute, and DF-37's gantt-chart", () => {
    for (const [name, target] of Object.entries(ICON_SUBSTITUTES)) {
      expect(target, name).not.toBe(name);
      expect(LUCIDE.has(name), `${name} is the handoff's name`).toBe(true);
    }
    expect(ICON_SUBSTITUTES["gantt-chart"]).toBe("chart-gantt");
  });

  it("renders a drawn shape for every name, not an empty box", () => {
    for (const name of ICON_NAMES) {
      expect(render(name, 14), name).toMatch(
        /<(path|circle|rect|line|polyline|polygon|ellipse)\b/u,
      );
    }
  });
});

describe("ac3 strokes stay in viewBox units at sizes 12 to 22", () => {
  const SIZES = [...ICON_SIZES];

  it("offers 12 to 22", () => {
    expect(SIZES[0]).toBe(12);
    expect(SIZES.at(-1)).toBe(22);
  });

  it("draws every name on the 24 grid, scaled by its box, with a 1.5 stroke that scales with it", () => {
    for (const name of ICON_NAMES) {
      for (const size of SIZES) {
        const html = render(name, size);
        expect(html, `${name} ${String(size)}`).toContain('viewBox="0 0 24 24"');
        expect(html).toContain(`width="${String(size)}"`);
        expect(html).toContain(`height="${String(size)}"`);
        expect(html).toContain(`stroke-width="${String(ICON_STROKE)}"`);
        expect(html).toContain('stroke="currentColor"');
        expect(html).toContain('stroke-linecap="round"');
        // A pixel stroke would not scale: no vector-effect, no unit on the width, no absolute width.
        expect(html).not.toContain("vector-effect");
        expect(html).not.toMatch(/stroke-width="[^"]*(px|em|%)"/u);
      }
    }
  });

  it("takes a stroke in viewBox units for disc and pill checks, and fills on request", () => {
    expect(render("check", 10 + 4, { strokeWidth: 1.9 })).toContain('stroke-width="1.9"');
    expect(render("check", 14, { filled: true })).toContain('fill="currentColor"');
    expect(render("check", 14)).toContain('fill="none"');
  });
});

describe("ac4 accessibility", () => {
  it("hides an icon by default and names one only when asked", () => {
    const hidden = render("bell", 14);
    expect(hidden).toContain('aria-hidden="true"');
    expect(hidden).not.toContain("aria-label");
    const named = render("bell", 14, { label: "Notifications" });
    expect(named).toContain('aria-label="Notifications"');
    expect(named).toContain('role="img"');
    expect(named).not.toContain("aria-hidden");
  });
});

describe("ac5 custom glyphs", () => {
  const SIZES = [...ICON_SIZES];
  const html = (c: unknown, props: Record<string, unknown>): string =>
    renderToStaticMarkup(createElement(c as never, props));
  const BRAND = /#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/iu;

  it("draws the atom mark and the half disc on a 24 viewBox with a stroke in its units", () => {
    for (const size of SIZES) {
      for (const [Glyph, id] of [
        [AtomMark, "atom-mark"],
        [HalfDisc, "half-disc"],
      ] as const) {
        const out = html(Glyph, { size });
        expect(out, id).toContain('viewBox="0 0 24 24"');
        expect(out).toContain(`width="${String(size)}"`);
        expect(out).toContain(`stroke-width="${String(ICON_STROKE)}"`);
        expect(out).toContain('stroke="currentColor"');
        expect(out).not.toContain("vector-effect");
        expect(out).not.toMatch(BRAND);
        expect(out).toContain('aria-hidden="true"');
      }
    }
  });

  it("fills the left half of the half disc with the current colour", () => {
    const out = html(HalfDisc, { size: 15 });
    expect(out).toContain('fill="currentColor"');
    expect(out).toContain("M12 0.75a11.25 11.25 0 0 0 0 22.5Z");
  });

  it("draws the Agent monogram as the espresso tile with the posted dot, by token", () => {
    const out = html(AgentMonogram, { size: 16 });
    expect(out).toContain('viewBox="0 0 100 100"');
    expect(out).toContain('rx="28"');
    for (const token of ["fill-espresso", "fill-on-dark", "fill-green"]) {
      expect(out).toContain(token);
    }
    expect(out).not.toMatch(BRAND);
    expect(html(AgentMonogram, { size: 16, label: "Accrued Agent" })).toContain(
      'aria-label="Accrued Agent"',
    );
  });

  it("derives vendor monograms from the name and never draws a vendor's own colours", () => {
    expect(vendorMonogram("Xero")).toBe("X");
    expect(vendorMonogram("QuickBooks Online")).toBe("QO");
    expect(vendorMonogram("  drata ")).toBe("D");
    expect(vendorMonogram("Tax & Audit Suite Pro")).toBe("TA");
    expect(vendorMonogram("")).toBe("?");
    for (const tone of VENDOR_TONES) {
      const out = html(VendorTile, { name: "Pell", tone, size: 32 });
      expect(out).toContain(`fill-${tone}`);
      expect(out).toContain('data-monogram="P"');
      expect(out).toContain('viewBox="0 0 32 32"');
      expect(out).not.toMatch(BRAND);
    }
  });

  it("keeps colour literals out of the icon sources", () => {
    const dir = join(dirname(fileURLToPath(import.meta.url)), "icons");
    for (const file of readdirSync(dir)) {
      expect(readFileSync(join(dir, file), "utf8"), file).not.toMatch(BRAND);
    }
  });
});
