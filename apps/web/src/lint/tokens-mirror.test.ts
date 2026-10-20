// @vitest-environment node
// SPEC-048 AC-1, AC-2, AC-4, AC-14 (F-05-T03): packages/ui/src/tokens/tokens.ts is the typed
// mirror of theme.css and root.css. Every value is exactly equal in both directions, the counts
// match design-foundations §1, Tailwind emits the token values and nothing else, and
// contrast.css restores the handoff ladder under data-contrast="reference".
import {
  colors,
  fonts,
  insetShadows,
  layout,
  motion,
  radii,
  referenceLadder,
  resets,
  rootVariables,
  scrims,
  shadows,
  textRoles,
  themeVariables,
  zIndex,
} from "@abacus/ui/tokens";
import { beforeAll, describe, expect, it } from "vitest";
import { compiled } from "./tailwind-probe";
import { UI, read } from "./ui-files";

let THEME = "";
let ROOT = "";
let CONTRAST = "";
beforeAll(async () => {
  THEME = await read(`${UI}/theme.css`);
  ROOT = await read(`${UI}/root.css`);
  CONTRAST = await read(`${UI}/contrast.css`);
});

const strip = (css: string): string => css.replace(/\/\*[\s\S]*?\*\//g, "");

/** The text between the braces that follow `opener` (first match), nested braces balanced. */
function block(css: string, opener: RegExp): string {
  const start = opener.exec(css);
  if (start === null) throw new Error(`${String(opener)} not found`);
  let depth = 0;
  for (let i = start.index + start[0].length - 1; i < css.length; i += 1) {
    if (css[i] === "{") depth += 1;
    if (css[i] === "}") {
      depth -= 1;
      if (depth === 0) return css.slice(start.index + start[0].length, i);
    }
  }
  throw new Error(`${String(opener)} is not closed`);
}

const normal = (value: string): string => value.replace(/\s+/g, " ").trim().toLowerCase();

/** Every custom property declared at the top level of a block (nested blocks are skipped). */
function declarations(body: string): Record<string, string> {
  const flat = body.replace(/\{[^{}]*\}/g, "");
  const found: Record<string, string> = {};
  for (const m of flat.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    found[m[1] ?? ""] = normal(m[2] ?? "");
  }
  return found;
}

const lowered = (vars: Readonly<Record<string, string>>): Record<string, string> =>
  Object.fromEntries(Object.entries(vars).map(([k, v]) => [k, normal(v)]));

describe("AC-1 tokens.ts mirrors theme.css and root.css exactly", () => {
  it("lists every theme.css value, and theme.css holds nothing tokens.ts lacks", () => {
    const theme = declarations(block(strip(THEME), /@theme static\s*\{/));
    expect(theme).toEqual(lowered(themeVariables));
  });

  it("lists every root.css value, and root.css holds nothing tokens.ts lacks", () => {
    const root = declarations(block(strip(ROOT), /:root\s*\{/));
    expect(root).toEqual(lowered(rootVariables));
  });

  it("resets each Tailwind namespace the plan retires", () => {
    const theme = block(strip(THEME), /@theme static\s*\{/);
    for (const namespace of resets) {
      expect(theme, namespace).toMatch(new RegExp(`--${namespace}-\\*:\\s*initial;`));
    }
    expect([...resets]).toEqual(expect.arrayContaining(["color", "shadow"]));
  });

  it("has the counts design-foundations §1 lists", () => {
    expect(Object.keys(colors.surfaces)).toHaveLength(9);
    expect(Object.keys(colors.inks)).toHaveLength(7);
    expect(Object.keys(colors.dark)).toHaveLength(4); // plus shadow-cta, the fifth dark-fill token
    expect(Object.keys(colors.status)).toEqual(
      expect.arrayContaining(["green", "green-ink", "green-tint", "green-hover"]),
    );
    expect(Object.keys(colors.match)).toHaveLength(8);
    expect(Object.keys(colors.viz)).toHaveLength(8);
    expect(Object.keys(colors.doc)).toHaveLength(10);
    expect(colors.clay).toBe("#a45f3d");
    expect(Object.keys(textRoles).length).toBeGreaterThanOrEqual(22);
    expect(Object.keys(radii)).toHaveLength(13);
    expect(Object.keys(shadows).length + Object.keys(insetShadows).length).toBeGreaterThanOrEqual(
      14,
    );
    expect(Object.keys(scrims)).toHaveLength(3);
    expect(Object.keys(zIndex)).toHaveLength(5);
    expect(Object.keys(layout).length).toBeGreaterThanOrEqual(25);
    expect(Object.keys(motion).length).toBeGreaterThan(0);
    expect(fonts.mono).toMatch(/^"Geist Mono"/);
  });
});

describe("AC-2 Tailwind emits the plan's tokens and nothing from its defaults", () => {
  it("compiles Tailwind's default palette and shadows to no rules", async () => {
    const css = await compiled(["bg-red-500", "text-gray-700", "shadow-lg", "border-blue-600"]);
    expect(css).not.toMatch(/\.bg-red-500\b/);
    expect(css).not.toMatch(/\.text-gray-700\b/);
    expect(css).not.toMatch(/\.shadow-lg\b/);
    expect(css).not.toMatch(/\.border-blue-600\b/);
  });

  it("emits the token utilities with the exact token values", async () => {
    const css = await compiled(["bg-green-tint", "text-body", "shadow-e2", "rounded-pane"]);
    const flat = normal(css);
    expect(flat).toMatch(/\.bg-green-tint \{ background-color: var\(--color-green-tint\);/);
    expect(flat).toMatch(/\.text-body \{ font-size: var\(--text-body\);/);
    expect(flat).toMatch(/\.rounded-pane \{ border-radius: var\(--radius-pane\);/);
    expect(flat).toContain(`--color-green-tint: ${colors.status["green-tint"]};`);
    expect(flat).toContain(`--text-body: ${textRoles.body.size};`);
    expect(flat).toContain(`--radius-pane: ${radii.pane};`);
    expect(flat).toContain(`--shadow-e2: ${normal(shadows.e2)};`);
  });
});

describe("AC-14 the pill is a token and the controls' radius", () => {
  it("has --radius-pill at 999px in tokens.ts and theme.css", () => {
    expect(radii.pill).toBe("999px");
    expect(declarations(block(strip(THEME), /@theme static\s*\{/))["--radius-pill"]).toBe("999px");
  });
});

describe("AC-4 contrast.css restores the handoff ladder", () => {
  it("overrides the ladder exactly under data-contrast=reference", () => {
    const reference = declarations(block(strip(CONTRAST), /\[data-contrast="reference"\]\s*\{/));
    expect(reference).toEqual(lowered(referenceLadder));
    expect(referenceLadder["--color-ink-2"]).toBe("rgba(43, 31, 23, 0.62)");
    expect(referenceLadder["--color-ink-3"]).toBe("rgba(43, 31, 23, 0.54)");
    expect(referenceLadder["--color-match-ink"]).toBe("#9253a2");
  });

  it("keeps the shipped ladder at the AA values when the attribute is absent", () => {
    expect(colors.inks["ink-2"]).toBe("rgba(43, 31, 23, 0.7)");
    expect(colors.inks["ink-3"]).toBe("rgba(43, 31, 23, 0.66)");
    expect(colors.match["match-ink"]).toBe("#7e4590");
  });
});
