// Test helper (SPEC-048 AC-2): compiles Tailwind over the design system's theme.css for a list of
// candidate classes, so a test can see which rules a class emits (or that it emits none).
import { compile } from "tailwindcss";
import { UI, WEB, exists, read } from "./ui-files";

/** The design system's stylesheets (theme, root, base, motion, utilities) without the Fontsource imports. */
export async function themeSource(): Promise<string> {
  const files = ["theme.css", "root.css", "base.css", "motion.css", "utilities.css"];
  const parts: string[] = [];
  for (const file of files) {
    if (await exists(`${UI}/${file}`)) parts.push(await read(`${UI}/${file}`));
  }
  return parts.join("\n").replace(/^@import "@fontsource[^\n]*\n/gm, "");
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
