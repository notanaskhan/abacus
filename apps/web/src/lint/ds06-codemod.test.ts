// @vitest-environment node
// ds06-codemod: keep (this file holds the old class names on purpose)
// SPEC-048 (F-05-T06): the DS-06 codemod from Tailwind's default type sizes to the plan's type
// roles, and the proof that no role changes a screen's text size: every role utility compiles to
// the same font-size and line-height as the Tailwind class it replaces.
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { compile } from "tailwindcss";
import { beforeAll, describe, expect, it } from "vitest";
import { ROLE_FOR, rewriteSource, runCodemod } from "./ds06-codemod";

describe("ds06 codemod: rewriteSource", () => {
  it("rewrites each default size to its role", () => {
    const source =
      '<p className="text-xs text-sm text-base text-lg text-xl text-2xl text-3xl">x</p>';
    expect(rewriteSource(source)).toEqual({
      output:
        '<p className="text-meta text-body text-nav text-pane text-title text-dashboard text-dashboard">x</p>',
      count: 7,
    });
  });

  it("keeps variant prefixes, stacked variants, arbitrary variants and the important flag", () => {
    const source =
      '"md:text-sm hover:text-xs md:hover:text-lg !text-sm text-xs! [&>svg]:text-sm data-[size=sm]:text-xs"';
    expect(rewriteSource(source).output).toBe(
      '"md:text-body hover:text-meta md:hover:text-pane !text-body text-meta! [&>svg]:text-body data-[size=sm]:text-meta"',
    );
  });

  it("keeps a line-height modifier", () => {
    expect(rewriteSource('"text-sm/6 text-xs/[18px]"').output).toBe(
      '"text-body/6 text-meta/[18px]"',
    );
  });

  it("rewrites inside cn(), cva() and template strings", () => {
    const source = [
      'const a = cn("text-sm", open && "text-xs", { "text-lg": big });',
      'const v = cva("text-sm", { variants: { size: { sm: "text-xs", lg: "text-xl" } } });',
      "const t = `px-3 ${x ? 'text-sm' : 'text-xs'} text-sm`;",
    ].join("\n");
    const { output, count } = rewriteSource(source);
    expect(count).toBe(9);
    expect(output).not.toMatch(/text-(xs|sm|base|lg|xl|2xl|3xl)\b/);
    expect(output).toContain('cn("text-body", open && "text-meta", { "text-pane": big })');
    expect(output).toContain("`px-3 ${x ? 'text-body' : 'text-meta'} text-body`");
  });

  it("leaves other text-* utilities and look-alikes alone", () => {
    const source =
      '"text-ink-2 text-left text-center text-ellipsis text-smooth context-sm text-sm-x text-xsm text-meta text-body"';
    expect(rewriteSource(source)).toEqual({ output: source, count: 0 });
  });

  it("skips a file that keeps old names on purpose", () => {
    const source = '// ds06-codemod: keep\n"text-sm"';
    expect(rewriteSource(source)).toEqual({ output: source, count: 0 });
  });

  it("is idempotent", () => {
    const once = rewriteSource('"text-sm md:text-xs text-2xl"').output;
    expect(rewriteSource(once)).toEqual({ output: once, count: 0 });
  });
});

describe("ds06 codemod: runCodemod", () => {
  it("prints a count per changed file, writes only when asked, and skips other files", () => {
    const root = mkdtempSync(join(tmpdir(), "ds06-"));
    const dir = join(root, "a");
    try {
      mkdirSync(join(dir, "node_modules"), { recursive: true });
      writeFileSync(join(dir, "One.tsx"), '<i className="text-sm text-xs"/>', "utf8");
      writeFileSync(join(dir, "two.ts"), 'export const c = "text-lg";', "utf8");
      writeFileSync(join(dir, "clean.ts"), 'export const c = "text-body";', "utf8");
      writeFileSync(join(dir, "style.css"), ".x{} /* text-sm */", "utf8");
      writeFileSync(join(dir, "node_modules", "dep.ts"), '"text-sm"', "utf8");

      const lines: string[] = [];
      const dry = runCodemod([dir], { write: false, log: (l) => lines.push(l) });
      expect(dry.map((r) => [r.file, r.count])).toEqual([
        [join(dir, "One.tsx"), 2],
        [join(dir, "two.ts"), 1],
      ]);
      expect(lines).toEqual([
        `${join(dir, "One.tsx")}: 2`,
        `${join(dir, "two.ts")}: 1`,
        "2 files, 3 uses",
      ]);
      expect(readFileSync(join(dir, "One.tsx"), "utf8")).toContain("text-sm");

      runCodemod([dir], { write: true, log: () => undefined });
      expect(readFileSync(join(dir, "One.tsx"), "utf8")).toBe(
        '<i className="text-body text-meta"/>',
      );
      expect(readFileSync(join(dir, "two.ts"), "utf8")).toBe('export const c = "text-pane";');
      expect(readFileSync(join(dir, "style.css"), "utf8")).toContain("text-sm");
      expect(readFileSync(join(dir, "node_modules", "dep.ts"), "utf8")).toBe('"text-sm"');
      expect(runCodemod([dir], { write: true, log: () => undefined })).toEqual([]);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});

// What Tailwind's classes compiled to before the reset: the size and line height the mapped
// class had in theme.css. The role utilities must reproduce each pair exactly.
const OLD_MAPPING: Record<string, { size: string; lineHeight: string }> = {
  xs: { size: "11.5px", lineHeight: "1.3" },
  sm: { size: "13px", lineHeight: "1.45" },
  base: { size: "13.5px", lineHeight: "1.45" },
  lg: { size: "14.5px", lineHeight: "1.3" },
  xl: { size: "15px", lineHeight: "1.3" },
  "2xl": { size: "20px", lineHeight: "1.2" },
  "3xl": { size: "20px", lineHeight: "1.2" },
};

let THEME = "";
let TAILWIND = "";
beforeAll(() => {
  const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
  THEME = readFileSync(`${cwd}/../../packages/ui/src/theme.css`, "utf8");
  TAILWIND = readFileSync(`${cwd}/node_modules/tailwindcss/index.css`, "utf8");
});

async function declarations(candidate: string): Promise<{ size: string; lineHeight: string }> {
  const source = `@import "tailwindcss";\n${THEME.replace(/^@import "@fontsource[^\n]*\n/gm, "")}`;
  const compiler = await compile(source, {
    loadStylesheet: async (id: string, base: string) => {
      if (id !== "tailwindcss") throw new Error(`unexpected stylesheet ${id}`);
      return Promise.resolve({ path: "tailwindcss/index.css", base, content: TAILWIND });
    },
  });
  const css = compiler.build([candidate]);
  const rule = new RegExp(`\\.${candidate}\\s*\\{([^}]*)\\}`).exec(css)?.[1] ?? "";
  // A role that only sets size and line height changes nothing else on a screen.
  expect(rule).not.toMatch(/letter-spacing|font-weight/);
  const value = (name: string): string =>
    new RegExp(`${name}:\\s*([0-9.]+(?:px)?);`).exec(css)?.[1] ?? "";
  return {
    size: value(`--${candidate}`),
    lineHeight: value(`--${candidate}--line-height`),
  };
}

describe("ds06 type roles keep every screen's text size", () => {
  it.each(Object.entries(OLD_MAPPING))(
    "text-%s -> its role has the same size and line height",
    async (old, want) => {
      const role = ROLE_FOR[old];
      if (role === undefined) throw new Error(`no role for text-${old}`);
      expect(await declarations(`text-${role}`)).toEqual(want);
    },
  );
});
