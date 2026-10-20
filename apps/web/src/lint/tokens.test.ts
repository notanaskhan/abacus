// @vitest-environment node
// SPEC-048 (F-05-T03, SU-24): the shipped tokens in packages/ui/src/theme.css. The AA ink ladder
// meets 4.5:1 for small text on every surface, match text and the focus outline follow the plan,
// Tailwind's default palette and shadows compile to nothing, and the body is 13px Geist with
// tabular figures on the shell colour.
import { compile } from "tailwindcss";
import { beforeAll, describe, expect, it } from "vitest";

// Vitest stubs CSS imports (even `?raw`), so the stylesheets are read from disk. Node's fs is
// loaded at run time and typed here, without pulling Node's types into the SPA's build.
type Fs = { readFileSync: (path: string, encoding: "utf8") => string };
const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
let THEME = "";
let TAILWIND = "";
beforeAll(async () => {
  const fsModule = "node:fs";
  const fs = (await import(/* @vite-ignore */ fsModule)) as Fs;
  const ui = `${cwd}/../../packages/ui/src`;
  // The base layer (body, focus outline) moved from theme.css to base.css in F-05-T05.
  THEME = `${fs.readFileSync(`${ui}/theme.css`, "utf8")}\n${fs.readFileSync(`${ui}/base.css`, "utf8")}`;
  TAILWIND = fs.readFileSync(`${cwd}/node_modules/tailwindcss/index.css`, "utf8");
});

function token(name: string): string {
  const match = new RegExp(`--${name}:\\s*([^;]+);`).exec(THEME);
  if (match?.[1] === undefined) throw new Error(`token --${name} not found`);
  return match[1].trim();
}

function hex(value: string): [number, number, number] {
  const m = /^#([0-9a-f]{6})$/i.exec(value);
  if (m?.[1] === undefined) throw new Error(`not a hex colour: ${value}`);
  const n = Number.parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function luminance([r, g, b]: [number, number, number]): number {
  const channel = (v: number): number => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(alpha: number, ground: [number, number, number]): number {
  const ink: [number, number, number] = [43, 31, 23];
  const fg = ink.map((c, i) => Math.round(c * alpha + (ground[i] ?? 0) * (1 - alpha))) as [
    number,
    number,
    number,
  ];
  const [hi, lo] = [luminance(fg), luminance(ground)].sort((a, b) => b - a) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const alpha = (name: string): number => {
  const m = /rgba\(43,\s*31,\s*23,\s*([0-9.]+)\)/.exec(token(name));
  if (m?.[1] === undefined) throw new Error(`--${name} is not on the espresso ladder`);
  return Number(m[1]);
};

const SURFACES = ["color-card", "color-surface", "color-shell", "color-nav-fill", "color-nested"];

async function compiled(candidates: string[]): Promise<string> {
  const source = `@import "tailwindcss";\n${THEME.replace(/^@import "@fontsource[^\n]*\n/gm, "")}`;
  const compiler = await compile(source, {
    loadStylesheet: async (id: string, base: string) => {
      if (id !== "tailwindcss") throw new Error(`unexpected stylesheet ${id}`);
      return Promise.resolve({ path: "tailwindcss/index.css", base, content: TAILWIND });
    },
  });
  return compiler.build(candidates);
}

describe("SPEC-048 design tokens", () => {
  it("puts ink-2 at .70 and ink-3 at .66, the plan's AA ladder", () => {
    expect(alpha("color-ink-2")).toBe(0.7);
    expect(alpha("color-ink-3")).toBe(0.66);
  });

  it.each(SURFACES)("meets 4.5:1 for small ink-2 and ink-3 text on %s", (surface) => {
    const ground = hex(token(surface));
    expect(contrast(alpha("color-ink-2"), ground)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(alpha("color-ink-3"), ground)).toBeGreaterThanOrEqual(4.5);
  });

  it("uses the plan's match text colour and focus outline", () => {
    expect(token("color-match-ink").toLowerCase()).toBe("#7e4590");
    const focus = /:focus-visible\s*\{([^}]*)\}/.exec(THEME)?.[1] ?? "";
    expect(focus).toMatch(/outline:\s*2px solid rgba\(43, 31, 23, 0\.55\)/);
  });

  it("compiles Tailwind's default palette and shadows to nothing", async () => {
    const css = await compiled([
      "bg-red-500",
      "text-gray-700",
      "shadow-lg",
      "bg-card",
      "shadow-pop",
    ]);
    expect(css).not.toMatch(/\.bg-red-500\b/);
    expect(css).not.toMatch(/\.text-gray-700\b/);
    expect(css).not.toMatch(/\.shadow-lg\b/);
    expect(css).toMatch(/\.bg-card\b/);
    expect(css).toMatch(/\.shadow-pop\b/);
  });

  it("sets the body in 13px Geist with tabular figures on the shell colour", () => {
    const body = /\bbody\s*\{([^}]*)\}/.exec(THEME)?.[1] ?? "";
    const page = /\bhtml\s*\{([^}]*)\}/.exec(THEME)?.[1] ?? "";
    expect(body).toMatch(/font:\s*400 13px\/[0-9.]+(px)? var\(--font-ui\)/);
    expect(body).toMatch(/font-variant-numeric:\s*tabular-nums/);
    expect(page).toMatch(/background:\s*var\(--color-shell\)/);
    expect(token("color-shell").toLowerCase()).toBe("#f8f8f6");
    expect(token("font-ui")).toMatch(/^"Geist"/);
  });
});
