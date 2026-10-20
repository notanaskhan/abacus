// DS-06 codemod CLI (SPEC-048, F-05-T06): Tailwind's default type sizes to the plan's type roles.
//
//   node apps/web/scripts/ds06-codemod.ts            report only (a dry run), default roots
//   node apps/web/scripts/ds06-codemod.ts --write    rewrite the files in place
//   node apps/web/scripts/ds06-codemod.ts --write path/to/dir other/file.tsx
//
// Default roots: apps/web/src and packages/ui/src (*.ts, *.tsx). Prints `path: n` per changed
// file and a total. The rules live in src/lint/ds06-codemod.ts, where Vitest covers them.
import { resolve } from "node:path";
import { runCodemod } from "../src/lint/ds06-codemod.ts";

const args = (globalThis as unknown as { process: { argv: string[] } }).process.argv.slice(2);
const given = args.filter((a) => !a.startsWith("--"));
const here = (relative: string): string =>
  decodeURIComponent(new URL(relative, import.meta.url).pathname);
const roots =
  given.length > 0
    ? given.map((p) => resolve(p))
    : [here("../src"), here("../../../packages/ui/src")];

runCodemod(roots, {
  write: args.includes("--write"),
  log: (line) => {
    console.log(line);
  },
});
