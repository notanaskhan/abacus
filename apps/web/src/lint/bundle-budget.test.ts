// @vitest-environment node
// F-05-T17: the bundle budgets (firm 250 KB, portal 150 KB, route chunk 120 KB, gzip). The script
// reads the build manifest; here it runs over synthetic manifests with chosen sizes, and
// `make check-fast` runs it over the real build (apps/web/scripts/bundle-budget.mjs).
import { beforeAll, describe, expect, it } from "vitest";

interface Chunk {
  file: string;
  isEntry?: boolean;
  isDynamicEntry?: boolean;
  imports?: string[];
}
interface Line {
  name: string;
  bytes: number;
  budget: number;
}
interface Budget {
  BUDGETS: { firm: number; portal: number; route: number };
  staticClosure: (manifest: Record<string, Chunk>, key: string) => Set<string>;
  budgetLines: (
    manifest: Record<string, Chunk>,
    size: (file: string) => number,
  ) => { lines: Line[]; portal: boolean };
}
const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
let budget: Budget;

beforeAll(async () => {
  const path = `${cwd}/scripts/bundle-budget.mjs`;
  budget = (await import(/* @vite-ignore */ path)) as Budget;
});

const KB = 1000;
const MANIFEST: Record<string, Chunk> = {
  "index.html": { file: "assets/index.js", isEntry: true, imports: ["_vendor.js"] },
  "_vendor.js": { file: "assets/vendor.js" },
  "_shared.js": { file: "assets/shared.js", imports: ["_vendor.js"] },
  "src/legacy/Board.tsx": {
    file: "assets/Board.js",
    isDynamicEntry: true,
    imports: ["_shared.js", "_vendor.js"],
  },
  "src/portal.html": { file: "assets/portal.js", isEntry: true, imports: ["_vendor.js"] },
};

function over(sizes: Record<string, number>): string[] {
  const { lines } = budget.budgetLines(MANIFEST, (file) => sizes[file] ?? 0);
  return lines.filter((l) => l.bytes > l.budget).map((l) => l.name);
}

describe("F-05-T17 bundle budgets", () => {
  it("states the plan's budgets", () => {
    expect(budget.BUDGETS).toEqual({ firm: 250 * KB, portal: 150 * KB, route: 120 * KB });
  });

  it("follows static imports, not dynamic ones", () => {
    expect([...budget.staticClosure(MANIFEST, "index.html")].sort()).toEqual([
      "_vendor.js",
      "index.html",
    ]);
  });

  it("passes a build inside every budget", () => {
    expect(
      over({
        "assets/index.js": 100 * KB,
        "assets/vendor.js": 100 * KB,
        "assets/portal.js": 40 * KB,
        "assets/Board.js": 119 * KB,
      }),
    ).toEqual([]);
  });

  it("fails a firm entry over 250 KB, counting its vendor chunk", () => {
    const names = over({ "assets/index.js": 100 * KB, "assets/vendor.js": 151 * KB });
    expect(names.some((n) => n.startsWith("firm initial"))).toBe(true);
  });

  it("fails a portal entry over 150 KB", () => {
    const names = over({ "assets/portal.js": 100 * KB, "assets/vendor.js": 51 * KB });
    expect(names.some((n) => n.startsWith("portal initial"))).toBe(true);
  });

  it("fails a route chunk over 120 KB, counting what it adds to the initial load", () => {
    const names = over({
      "assets/Board.js": 60 * KB,
      "assets/shared.js": 61 * KB,
      "assets/vendor.js": 10 * KB,
    });
    expect(names).toEqual(["route src/legacy/Board.tsx"]);
  });

  it("does not charge a route for chunks the initial load already has", () => {
    // vendor.js is in the firm's initial closure, so the route adds only its own and shared.js.
    const { lines } = budget.budgetLines(MANIFEST, (file) =>
      file === "assets/vendor.js" ? 200 * KB : 1,
    );
    expect(lines.find((l) => l.name.startsWith("route"))?.bytes).toBe(2);
  });

  it("reports a build with one entry as having no portal yet", () => {
    const single = { ...MANIFEST };
    delete single["src/portal.html"];
    expect(budget.budgetLines(single, () => 0).portal).toBe(false);
  });
});
