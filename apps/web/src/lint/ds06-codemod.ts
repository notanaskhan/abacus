// DS-06 codemod (SPEC-048, F-05-T06): Tailwind's default type sizes to the plan's type roles. The
// CLI is apps/web/scripts/ds06-codemod.ts. Each size maps onto the role whose size and line height
// equal the Tailwind class's today, so no screen changes size. The rewrite keeps variant prefixes
// (md:, hover:, [&>svg]:), the important flag and a line-height modifier (text-sm/6), and works
// inside cn(), cva() and template strings because it rewrites the class token wherever it stands.
// It is idempotent: a role name never matches a Tailwind size.
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

/** Tailwind size name (the part after `text-`) to the plan's type role. */
export const ROLE_FOR: Readonly<Record<string, string>> = {
  xs: "meta", // 11.5px / 1.3
  sm: "body", // 13px / 1.45
  base: "nav", // 13.5px / 1.45
  lg: "pane", // 14.5px / 1.3
  xl: "title", // 15px / 1.3
  "2xl": "dashboard", // 20px / 1.2
  "3xl": "dashboard", // 20px / 1.2 (the same size as 2xl today)
};

// `text-<size>` as a whole class token: not part of a longer word or name (text-smooth, text-sm-x),
// whatever precedes it (a variant prefix, `!`, a quote, a space). A `/` line-height modifier may follow.
const SIZE = /(?<![\w-])text-(xs|sm|base|lg|xl|2xl|3xl)(?![\w-])/g;

/** A file that holds old class names on purpose (this codemod's test, the token test) says so. */
export const KEEP_MARKER = "ds06-codemod: keep";

export function rewriteSource(source: string): { output: string; count: number } {
  if (source.includes(KEEP_MARKER)) return { output: source, count: 0 };
  let count = 0;
  const output = source.replace(SIZE, (_match, size: string) => {
    count += 1;
    return `text-${ROLE_FOR[size] ?? size}`;
  });
  return { output, count };
}

const SOURCE_FILE = /\.(ts|tsx)$/;
const SKIP_DIRS = new Set(["node_modules", "dist", ".git"]);

function collect(path: string, into: string[]): void {
  if (SOURCE_FILE.test(path)) {
    into.push(path);
    return;
  }
  let entries;
  try {
    entries = readdirSync(path, { withFileTypes: true });
  } catch {
    return; // a file of another type, or a missing path
  }
  for (const entry of [...entries].sort((a, b) => (a.name < b.name ? -1 : 1))) {
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) collect(join(path, entry.name), into);
    } else if (SOURCE_FILE.test(entry.name)) {
      into.push(join(path, entry.name));
    }
  }
}

export interface FileResult {
  file: string;
  count: number;
}

/** Rewrites (or, without `write`, only counts) every *.ts / *.tsx under the roots; logs `path: n`. */
export function runCodemod(
  roots: readonly string[],
  options: { write: boolean; log: (line: string) => void },
): FileResult[] {
  const files: string[] = [];
  for (const root of roots) collect(root, files);
  const results: FileResult[] = [];
  for (const file of files) {
    const { output, count } = rewriteSource(readFileSync(file, "utf8"));
    if (count === 0) continue;
    if (options.write) writeFileSync(file, output, "utf8");
    results.push({ file, count });
    options.log(`${file}: ${String(count)}`);
  }
  const uses = results.reduce((sum, r) => sum + r.count, 0);
  options.log(`${String(results.length)} files, ${String(uses)} uses`);
  return results;
}
