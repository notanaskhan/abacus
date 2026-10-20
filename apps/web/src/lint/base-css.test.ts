// @vitest-environment node
// SPEC-048 AC-8 (F-05-T05): base.css, motion.css and utilities.css. The body is 13px Geist with
// tabular figures on the shell colour; the focus outline is an outline (it survives
// forced-colors); reduced motion and forced colors have their own blocks; the utilities (hairline,
// pane, well, tabular, doc-scope) emit the token values. The computed-style run in a browser
// follows with the gallery (F-05-T09).
import { beforeAll, describe, expect, it } from "vitest";
import { compiled } from "./tailwind-probe";
import { UI, read } from "./ui-files";

let BASE = "";
let MOTION = "";
let UTILITIES = "";
let THEME = "";
let STYLES = "";
let DECISIONS = "";
beforeAll(async () => {
  BASE = await read(`${UI}/base.css`);
  MOTION = await read(`${UI}/motion.css`);
  UTILITIES = await read(`${UI}/utilities.css`);
  THEME = await read(`${UI}/theme.css`);
  STYLES = await read(`${UI}/styles.css`);
  DECISIONS = await read(`${UI}/tokens/DECISIONS.md`);
});

const flat = (css: string): string => css.replace(/\s+/g, " ");

describe("AC-8 base.css", () => {
  it("sets the body in 13px Geist, tabular figures, on the shell colour", () => {
    const body = /\bbody\s*\{([^}]*)\}/.exec(BASE)?.[1] ?? "";
    const html = /\bhtml\s*\{([^}]*)\}/.exec(BASE)?.[1] ?? "";
    expect(body).toMatch(/font:\s*400 13px\/[0-9.]+ var\(--font-ui\)/);
    expect(body).toMatch(/font-variant-numeric:\s*tabular-nums/);
    expect(body).toMatch(/-webkit-font-smoothing:\s*antialiased/);
    expect(html).toMatch(/background:\s*var\(--color-shell\)/);
    expect(html).toMatch(/color-scheme:\s*light/);
  });

  it("keeps the 1.45 body line height as a recorded open decision, not the plan's 15.6px", () => {
    expect(/\bbody\s*\{([^}]*)\}/.exec(BASE)?.[1]).toMatch(/13px\/1\.45 /);
    expect(DECISIONS).toMatch(/body line height[^\n]*1\.45[^\n]*open/i);
  });

  it("draws focus as an outline, and keeps it in forced-colors mode", () => {
    expect(/:focus-visible\s*\{([^}]*)\}/.exec(BASE)?.[1]).toMatch(
      /outline:\s*2px solid rgba\(43, 31, 23, 0\.55\)/,
    );
    const forced = /@media \(forced-colors: active\)\s*\{([\s\S]*?)\n\}/.exec(BASE)?.[1] ?? "";
    expect(forced).toMatch(/:focus-visible/);
    expect(forced).toMatch(/outline:\s*2px solid/);
    expect(forced).not.toMatch(/outline:\s*(none|0)/);
  });

  it("moves the base layer out of theme.css", () => {
    expect(THEME).not.toMatch(/@layer base/);
    expect(THEME).not.toMatch(/@keyframes/);
    for (const file of ["base", "motion", "utilities"]) {
      expect(STYLES).toContain(`@import "./${file}.css";`);
    }
  });
});

describe("AC-8 motion.css", () => {
  it("defines the keyframes the components use and the plan's loops", () => {
    for (const name of [
      "drawer-in",
      "sheet-in",
      "pop-in",
      "toast-in",
      "ac-spin",
      "ac-pulse",
      "ac-reveal",
      "ac-typing",
    ]) {
      expect(MOTION, name).toContain(`@keyframes ${name}`);
    }
  });

  it("cuts animation and transition to 1ms under reduced motion", () => {
    const reduced = /@media \(prefers-reduced-motion: reduce\)\s*\{([\s\S]*?)\n\}/.exec(
      MOTION,
    )?.[1];
    expect(reduced).toMatch(/animation-duration:\s*0\.01ms !important/);
    expect(reduced).toMatch(/transition-duration:\s*0\.01ms !important/);
  });
});

describe("AC-8 utilities.css", () => {
  it("emits the pane, well, hairline, tabular and doc-scope utilities with token values", async () => {
    const css = flat(
      await compiled(["pane", "well", "hairline-t", "hairline-b", "tabular", "doc-scope"]),
    );
    expect(css).toMatch(/\.pane \{[^}]*background-color: var\(--color-card\)/);
    expect(css).toMatch(/\.pane \{[^}]*border-radius: var\(--radius-pane\)/);
    expect(css).toMatch(/\.pane \{[^}]*box-shadow: var\(--shadow-e2\)/);
    expect(css).toMatch(/\.well \{[^}]*background-color: var\(--color-shell\)/);
    expect(css).toMatch(/\.well \{[^}]*box-shadow: var\(--inset-shadow-hair\)/);
    expect(css).toMatch(/\.hairline-t \{[^}]*border-top: var\(--hairline\)/);
    expect(css).toMatch(/\.hairline-b \{[^}]*border-bottom: var\(--hairline\)/);
    expect(css).toMatch(/\.tabular \{[^}]*font-variant-numeric: tabular-nums/);
    expect(css).toMatch(/\.doc-scope \{[^}]*font-family: var\(--font-doc\)/);
  });

  it("gives panes, wells and cards a CanvasText edge under forced colors", () => {
    expect(flat(UTILITIES)).toMatch(
      /@media \(forced-colors: active\) \{[^}]*border: 1px solid CanvasText/,
    );
  });

  it("allows 600 and 700 weights only inside [data-doc]", () => {
    for (const [name, css] of [
      ["base", BASE],
      ["motion", MOTION],
      ["utilities", UTILITIES],
    ] as const) {
      const outside = css.replace(/\[data-doc\][^{]*\{[^}]*\}/g, "");
      expect(outside, name).not.toMatch(/font-weight:\s*(600|700)/);
    }
    expect(UTILITIES).toMatch(/\[data-doc\][^{]*\{[^}]*font-weight:\s*700/);
  });
});
