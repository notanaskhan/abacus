// SPEC-048 AC-6 (F-05-T07): the compiled-CSS check. After a production build it scans
// dist/**/assets/*.css and fails on
//   - a font-weight of 600 or above (600, 700, 800, 900, bold, bolder) outside a [data-doc] rule,
//   - a colour literal (hex, rgb(), rgba(), hsl(), oklch(), …) that is not a design token.
// A token is a colour literal that theme.css defines. Minifiers rewrite colours (rgba(43,31,23,.95)
// becomes #2b1f17f2) and Tailwind's opacity modifiers (bg-ink/50) change the alpha, so colours are
// compared by red, green and blue, not as text; fully transparent is always allowed.
//
//   node scripts/check-compiled-css.js [distDir]      (stage 1: `make check-fast`, after vite build)
//
// TODO(F-05-T03): also read the typed tokens.ts mirror once it lands; theme.css is its source.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";

const WEIGHT = /(?:^|\s)(?:600|700|800|900|bold|bolder|semibold)(?=\s|$)/i;
const COLOUR_FUNCTION = /\b(?:hsla?|hwb|oklch|oklab|lab|lch|color)\(/i;
const HEX = /#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{4}|[0-9a-f]{3})(?![0-9a-z])/gi;
const DATA_DOC = /\[data-doc(?:[~|^$*]?=[^\]]*)?\]/;
const RGB = /\brgba?\(([^)]*)\)/gi;

/** @param {string} hex @returns {string} */
function hexKey(hex) {
  let h = hex.slice(1);
  if (h.length <= 4) h = [...h].map((c) => c + c).join("");
  const n = (i) => Number.parseInt(h.slice(i, i + 2), 16);
  return [n(0), n(2), n(4), h.length === 8 ? n(6) : 255].join(",");
}

/** @param {string} args the inside of rgb( … ) @returns {string | null} */
function rgbKey(args) {
  const parts = args
    .trim()
    .split(/[\s,/]+/)
    .filter(Boolean);
  if (parts.length < 3 || parts.length > 4) return null;
  const channel = (p) =>
    Math.round(p.endsWith("%") ? Number.parseFloat(p) * 2.55 : Number.parseFloat(p));
  const [r, g, b] = parts.slice(0, 3).map(channel);
  const alpha = parts[3] ?? "1";
  const a = alpha.endsWith("%") ? Number.parseFloat(alpha) / 100 : Number.parseFloat(alpha);
  if ([r, g, b, a].some((v) => Number.isNaN(v))) return null;
  return [r, g, b, Math.round(a * 255)].join(",");
}

/** The colour literals in a value, as `{ text, key }` (`key` is null when it cannot be compared). */
function colourLiterals(value) {
  const bare = value.replace(/url\([^)]*\)/gi, "");
  const found = [];
  for (const m of bare.matchAll(HEX)) found.push({ text: m[0], key: hexKey(m[0]) });
  for (const m of bare.matchAll(RGB)) found.push({ text: m[0], key: rgbKey(m[1] ?? "") });
  const fn = COLOUR_FUNCTION.exec(bare);
  if (fn) found.push({ text: fn[0], key: null });
  return found;
}

/**
 * The colour literals of theme.css, as comparable keys.
 * @param {string} themeCss
 * @returns {string[]}
 */
export function tokenColours(themeCss) {
  const css = themeCss.replace(/\/\*[\s\S]*?\*\//g, "");
  return colourLiterals(css).flatMap((c) => (c.key === null ? [] : [c.key]));
}

/**
 * Walk a stylesheet into declarations with the rules that enclose them. Handles nesting
 * (@media, @layer, @supports), strings and parentheses; it is not a general CSS parser.
 * @param {string} css
 * @returns {{ context: string[]; prop: string; value: string }[]}
 */
function declarations(css) {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const out = [];
  const stack = [];
  let buffer = "";
  let depth = 0;
  let quote = "";
  const flush = () => {
    const i = buffer.indexOf(":");
    if (stack.length > 0 && i > 0) {
      out.push({
        context: [...stack],
        prop: buffer.slice(0, i).trim().toLowerCase(),
        value: buffer
          .slice(i + 1)
          .replace(/!important\s*$/i, "")
          .trim(),
      });
    }
    buffer = "";
  };
  for (const ch of text) {
    if (quote) {
      buffer += ch;
      if (ch === quote) quote = "";
    } else if (ch === '"' || ch === "'") {
      quote = ch;
      buffer += ch;
    } else if (ch === "(") {
      depth += 1;
      buffer += ch;
    } else if (ch === ")") {
      depth -= 1;
      buffer += ch;
    } else if (depth > 0) {
      buffer += ch;
    } else if (ch === "{") {
      stack.push(buffer.trim());
      buffer = "";
    } else if (ch === "}") {
      flush();
      stack.pop();
    } else if (ch === ";") {
      flush();
    } else {
      buffer += ch;
    }
  }
  return out;
}

/**
 * @param {string} css one compiled stylesheet
 * @param {string[]} tokens `tokenColours(theme.css)`
 * @returns {string[]} one message per violation
 */
export function checkCss(css, tokens) {
  // A token with an opacity modifier (bg-ink/50, bg-espresso/22) compiles to the token's colour
  // with another alpha, and fully transparent is `#0000`; both are the system's own colours.
  const rgbOf = (key) => key.split(",").slice(0, 3).join(",");
  const allowed = new Set(tokens.map(rgbOf));
  const isToken = (key) => key.endsWith(",0") || allowed.has(rgbOf(key));
  const messages = [];
  for (const { context, prop, value } of declarations(css)) {
    const where = context.join(" ");
    // Tailwind's preflight makes <optgroup> bolder inside a multi-select: native UI, not a style.
    const weightsAllowed = context.some((c) => DATA_DOC.test(c) || /\boptgroup\b/.test(c));
    if (!weightsAllowed && (prop === "font-weight" || prop === "font") && WEIGHT.test(value)) {
      messages.push(`${where} { ${prop}: ${value} }: weights above 500 belong in [data-doc]`);
    }
    for (const { text, key } of colourLiterals(value)) {
      if (key === null || !isToken(key)) {
        messages.push(
          `${where} { ${prop}: ${value} }: colour literal ${text} is not a design token`,
        );
      }
    }
  }
  return messages;
}

/** @param {string} dir @returns {string[]} the .css files in every `assets` folder under `dir` */
function stylesheets(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((name) => {
    const path = `${dir}/${name}`;
    if (statSync(path).isDirectory()) return stylesheets(path);
    return dir.endsWith("/assets") && name.endsWith(".css") ? [path] : [];
  });
}

// Run as a script, not when imported by the tests.
if (import.meta.url === `file://${process.argv[1]}`) {
  const dist = process.argv[2] ?? "dist";
  const files = stylesheets(dist);
  if (files.length === 0) {
    console.error(`check-compiled-css: no ${dist}/**/assets/*.css; run vite build first`);
    process.exit(1);
  }
  const tokens = tokenColours(
    readFileSync(`${import.meta.dirname}/../../../packages/ui/src/theme.css`, "utf8"),
  );
  let failed = 0;
  for (const file of files) {
    for (const message of checkCss(readFileSync(file, "utf8"), tokens)) {
      console.error(`${file}: ${message}`);
      failed += 1;
    }
  }
  if (failed > 0) {
    console.error(
      `check-compiled-css: ${String(failed)} violation(s) in ${String(files.length)} file(s)`,
    );
    process.exit(1);
  }
  console.log(`check-compiled-css: ${String(files.length)} stylesheet(s) clean`);
}
