// @vitest-environment node
// SPEC-048 AC-7 (F-05-T04): fonts are self-hosted. Geist and Geist Mono are eager (fonts.css,
// preloaded in the production page); Arimo and Gelasio sit in fonts-doc.css and are imported
// only by a document chunk; nothing references Google's font hosts; the CSP is unchanged. The
// browser half (request log, document.fonts.check) is e2e/ds-fonts.spec.ts (F-05-T08).
import { beforeAll, describe, expect, it } from "vitest";
import { UI, WEB, list, read } from "./ui-files";

const imports = (css: string): string[] =>
  [...css.matchAll(/^@import\s+"([^"]+)";/gm)].map((m) => m[1] ?? "");

let FONTS = "";
let FONTS_DOC = "";
let THEME = "";
let STYLES = "";
let VITE = "";
beforeAll(async () => {
  FONTS = await read(`${UI}/fonts.css`);
  FONTS_DOC = await read(`${UI}/fonts-doc.css`);
  THEME = await read(`${UI}/theme.css`);
  STYLES = await read(`${UI}/styles.css`);
  VITE = await read(`${WEB}/vite.config.ts`);
});

describe("AC-7 self-hosted fonts", () => {
  it("loads Geist and Geist Mono at 400 and 500 from Fontsource, eagerly", () => {
    expect(imports(FONTS)).toEqual([
      "@fontsource/geist/latin-400.css",
      "@fontsource/geist/latin-500.css",
      "@fontsource/geist-mono/latin-400.css",
      "@fontsource/geist-mono/latin-500.css",
    ]);
    expect(STYLES).toMatch(/@import "\.\/fonts\.css";/);
  });

  it("keeps fonts out of theme.css", () => {
    expect(imports(THEME).filter((i) => i.startsWith("@fontsource"))).toEqual([]);
  });

  it("puts Arimo (400, 600, 700) and Gelasio (400, 500, 700) in fonts-doc.css", () => {
    expect(imports(FONTS_DOC)).toEqual([
      "@fontsource/arimo/latin-400.css",
      "@fontsource/arimo/latin-600.css",
      "@fontsource/arimo/latin-700.css",
      "@fontsource/gelasio/latin-400.css",
      "@fontsource/gelasio/latin-500.css",
      "@fontsource/gelasio/latin-700.css",
    ]);
  });

  it("never imports the document fonts from the shared stylesheet", async () => {
    expect(STYLES).not.toMatch(/fonts-doc/);
    expect(THEME).not.toMatch(/fonts-doc/);
    expect(await read(`${WEB}/src/index.css`)).not.toMatch(/fonts-doc/);
    expect(await read(`${WEB}/src/main.tsx`)).not.toMatch(/fonts-doc/);
  });

  it("references no Google font host anywhere in the app or the design system", async () => {
    const roots = [`${WEB}/src`, UI];
    for (const root of roots) {
      for (const file of await list(root)) {
        if (!/\.(css|tsx?|html)$/.test(file) || file.includes("lint/")) continue;
        expect(await read(`${root}/${file}`), file).not.toMatch(
          /fonts\.(googleapis|gstatic)\.com/,
        );
      }
    }
    expect(await read(`${WEB}/index.html`)).not.toMatch(/fonts\.(googleapis|gstatic)\.com/);
  });

  it("leaves the abacus-csp policy unchanged", () => {
    const policy = [
      "\"default-src 'self'\"",
      "\"script-src 'self'\"",
      "\"style-src 'self'\"",
      "\"img-src 'self' data:\"",
      "\"connect-src 'self'\"",
      "\"frame-ancestors 'none'\"",
      "\"object-src 'none'\"",
      "\"base-uri 'none'\"",
      "\"form-action 'self'\"",
    ].join(",\n    ");
    expect(VITE).toContain(`const policy = [\n    ${policy},\n  ].join("; ");`);
    expect(VITE).toContain('name: "abacus-csp"');
  });

  it("preloads the eager fonts in the production page", () => {
    expect(VITE).toContain('name: "abacus-font-preload"');
    expect(VITE).toMatch(/rel: "preload"/);
    expect(VITE).toMatch(/as: "font"/);
    expect(VITE).toMatch(/type: "font\/woff2"/);
  });
});
