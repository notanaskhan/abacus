// Test helper (SPEC-048 AC-2): compiles Tailwind over the design system's theme.css for a list of
// candidate classes, so a test can see which rules a class emits (or that it emits none).
import { compile } from "tailwindcss";
import { UI, WEB, read } from "./ui-files";

/** theme.css without the Fontsource imports (they point at node_modules, not at a stylesheet). */
export async function themeSource(): Promise<string> {
  const theme = await read(`${UI}/theme.css`);
  return theme.replace(/^@import "@fontsource[^\n]*\n/gm, "");
}

export async function compiled(candidates: string[]): Promise<string> {
  const tailwind = await read(`${WEB}/node_modules/tailwindcss/index.css`);
  const source = `@import "tailwindcss";\n${await themeSource()}`;
  const compiler = await compile(source, {
    loadStylesheet: async (id: string, base: string) => {
      if (id !== "tailwindcss") throw new Error(`unexpected stylesheet ${id}`);
      return Promise.resolve({ path: "tailwindcss/index.css", base, content: tailwind });
    },
  });
  return compiler.build(candidates);
}
