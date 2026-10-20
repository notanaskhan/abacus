// @vitest-environment node
// SPEC-048 AC-6 (F-05-T07): the compiled-CSS check scans dist/*/assets/*.css after a production
// build. Any 600/700 weight outside [data-doc], or any colour literal that is not a design token,
// fails stage 1. Here it runs over fixture stylesheets, including one shaped like minified
// Tailwind output; `make check-fast` runs it over the real build (apps/web/scripts).
import { beforeAll, describe, expect, it } from "vitest";

type Fs = { readFileSync: (path: string, encoding: "utf8") => string };
interface Checker {
  tokenColours: (themeCss: string) => string[];
  checkCss: (css: string, tokenColours: string[]) => string[];
}
const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
let check: Checker;
let tokens: string[] = [];

beforeAll(async () => {
  const fsModule = "node:fs";
  const fs = (await import(/* @vite-ignore */ fsModule)) as Fs;
  const path = `${cwd}/scripts/check-compiled-css.js`;
  check = (await import(/* @vite-ignore */ path)) as Checker;
  tokens = check.tokenColours(fs.readFileSync(`${cwd}/../../packages/ui/src/theme.css`, "utf8"));
});

describe("SPEC-048 ac6 compiled-CSS check", () => {
  it("reads the colour literals of theme.css as the tokens", () => {
    expect(tokens.length).toBeGreaterThan(30);
  });

  it("fails a seeded 700 weight", () => {
    const found = check.checkCss(".h{font-weight:700}", tokens);
    expect(found).toHaveLength(1);
    expect(found[0]).toContain("700");
  });

  it.each(["600", "800", "900", "bold", "bolder", "semibold"])(
    "fails a seeded weight of %s",
    (weight) => {
      expect(check.checkCss(`.h{font-weight:${weight}}`, tokens)).toHaveLength(1);
    },
  );

  it("fails a 600/700 weight in the font shorthand and in nested at-rules", () => {
    expect(check.checkCss(".h{font:700 13px Geist}", tokens)).toHaveLength(1);
    expect(check.checkCss("@media (min-width:40rem){.h{font-weight:600}}", tokens)).toHaveLength(
      1,
    );
    expect(
      check.checkCss("@layer utilities{@media print{.h{font-weight: 700 !important}}}", tokens),
    ).toHaveLength(1);
  });

  it("passes 400 and 500 and weights through variables", () => {
    const css =
      ".a{font-weight:400}.b{font-weight:500}.c{font-weight:var(--font-weight-semibold)}.d{font-weight:normal}";
    expect(check.checkCss(css, tokens)).toEqual([]);
  });

  it("passes 600/700 inside [data-doc], in any nesting", () => {
    const css =
      '[data-doc] h1{font-weight:700}[data-doc="statement"] td{font-weight:600}@layer components{[data-doc] .t{font-weight:bold}}';
    expect(check.checkCss(css, tokens)).toEqual([]);
  });

  it("does not let [data-doc] on one rule excuse the next", () => {
    expect(
      check.checkCss("[data-doc] a{font-weight:700}.b{font-weight:700}", tokens),
    ).toHaveLength(1);
  });

  it("fails a seeded colour literal that is not a token", () => {
    for (const literal of [
      "#7a4e12",
      "#abc",
      "rgb(1,2,3)",
      "rgba(1,2,3,.5)",
      "hsl(10 10% 10%)",
      "oklch(.5 .1 20)",
    ]) {
      const found = check.checkCss(`.x{color:${literal}}`, tokens);
      expect(found, literal).toHaveLength(1);
      expect(found[0]).toContain(literal);
    }
  });

  it("finds a literal inside a longer value, such as a shadow or gradient", () => {
    expect(
      check.checkCss(".x{box-shadow:0 1px 2px #123456,0 0 0 1px var(--color-hair)}", tokens),
    ).toHaveLength(1);
    expect(
      check.checkCss(".x{background:linear-gradient(#7a4e12,var(--color-card))}", tokens),
    ).toHaveLength(1);
  });

  it("passes the token values however the minifier writes them", () => {
    const css =
      ":root{--color-card:#fff;--color-shell:#f8f8f6;--color-ink:#2b1f17f2;--color-hair:#2b1f171a}" +
      ".a{color:rgba(43,31,23,.95);background:#ffffff;border-color:rgb(43 31 23/.1)}" +
      ".b{box-shadow:0 0 0 .5px #2b1f1712,0 1px 2px #2b1f170d}";
    expect(check.checkCss(css, tokens)).toEqual([]);
  });

  it("passes a token with an opacity modifier, and fully transparent", () => {
    const css =
      ".a{background-color:#2b1f171f}.b{background-color:#fefefe24}.c{background-color:#0000}" +
      ".d{--tw-shadow:0 0 #0000}";
    expect(check.checkCss(css, tokens)).toEqual([]);
  });

  it("passes the weight Tailwind's preflight gives <optgroup>", () => {
    const css = "@layer base{:where(select:is([multiple],[size])) optgroup{font-weight:bolder}}";
    expect(check.checkCss(css, tokens)).toEqual([]);
  });

  it("passes keywords, variables and colour mixes of variables", () => {
    const css =
      ".a{color:currentColor;background:transparent;border-color:var(--color-hair)}" +
      ".b{background:color-mix(in oklab,var(--color-ink) 50%,transparent)}";
    expect(check.checkCss(css, tokens)).toEqual([]);
  });

  it("does not mistake ids, urls or hashes in selectors for colours", () => {
    const css =
      '#main-content{margin:0}a[href="#abc"]{x:y}.f{src:url(/assets/geist-latin-400-abcdef12.woff2)}';
    expect(check.checkCss(css, tokens)).toEqual([]);
  });

  it("ignores comments", () => {
    expect(check.checkCss("/* font-weight:700 #7a4e12 */.a{font-weight:500}", tokens)).toEqual([]);
  });
});
