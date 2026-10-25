// F-04-T33 (F-04.34): the local screen parity report's rows come from the route registry and each
// screen contract's Parity table; Tier A and D block, B blocks once locked, C is report-only.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  contractRows,
  gateOf,
  isLocked,
  judge,
  renderHtml,
  screenRows,
  statesOf,
  statusesFromSource,
} from "../../e2e/parity/screen-rows";
import { MANIFEST } from "./manifest";

const CONTRACT = `# CLI-01

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, d, f | C (locked before M8) | not run | P0 lock at Tier C |
| c | B (locked) | not run | mask the footer |
| e | A | not run | |
| h, i | — | — | deferred |
| host | D | — | toolbar 46 |

## Deviations
| x | y |
`;

describe("screen parity rows (F-04-T33)", () => {
  it("reads the states a cell names", () => {
    expect(statesOf("a–d")).toEqual(["a", "b", "c", "d"]);
    expect(statesOf("a, b, d, f")).toEqual(["a", "b", "d", "f"]);
    expect(statesOf("a b c g")).toEqual(["a", "b", "c", "g"]);
    expect(statesOf("a2")).toEqual(["a2"]);
    expect(statesOf("host")).toEqual(["host"]);
  });

  it("counts a lock only once it holds", () => {
    expect(isLocked("C (locked)")).toBe(true);
    expect(isLocked("C (locked before M8)")).toBe(false);
    expect(isLocked("locked by Fri Apr 30, 2027 (A-01-T28)")).toBe(false);
    expect(isLocked("P0 lock before M8")).toBe(false);
  });

  it("blocks on Tier A and D, on B once locked, never on C", () => {
    expect(gateOf("A", false)).toBe("blocking");
    expect(gateOf("D", false)).toBe("blocking");
    expect(gateOf("B", false)).toBe("report-only");
    expect(gateOf("B", true)).toBe("blocking");
    expect(gateOf("C", true)).toBe("report-only");
  });

  it("turns a contract's Parity table into rows, leaving deferred artboards out", () => {
    const rows = contractRows("CLI-01", CONTRACT);
    expect(rows.map((r) => [r.artboard, r.tier, r.locked, r.gate])).toEqual([
      ["CLI-01a", "C", false, "report-only"],
      ["CLI-01b", "C", false, "report-only"],
      ["CLI-01d", "C", false, "report-only"],
      ["CLI-01f", "C", false, "report-only"],
      ["CLI-01c", "B", true, "blocking"],
      ["CLI-01e", "A", false, "blocking"],
      ["CLI-01 host", "D", false, "blocking"],
    ]);
    expect(rows[0]?.baselineKey).toBe("cli-01a.window");
    expect(rows[6]?.baselineKey).toBe("cli-01.window");
  });

  it("covers every fixture and live screen of the registry, and only those", () => {
    const contract = (id: string): string | null => {
      const path = `../../docs/screens/${id}.md`;
      return existsSync(path) ? readFileSync(path, "utf8") : null;
    };
    const { rows, missing } = screenRows(MANIFEST, contract);
    const built = Object.entries(MANIFEST)
      .filter(([, e]) => e.status === "fixture" || e.status === "live")
      .map(([id]) => id);
    expect(new Set([...rows.map((r) => r.screen), ...missing])).toEqual(new Set(built));
    expect(rows.some((r) => r.artboard === "CLI-01a")).toBe(true);
  });

  it("reads the registry's statuses from its source exactly as the registry holds them", () => {
    const dir = "src/routes/manifest";
    const sources = readdirSync(dir)
      .filter((f) => f.endsWith(".ts") && !["index.ts", "types.ts"].includes(f))
      .map((f) => readFileSync(`${dir}/${f}`, "utf8"));
    const expected = Object.fromEntries(
      Object.entries(MANIFEST).map(([id, e]) => [id, { status: e.status }]),
    );
    expect(statusesFromSource(sources)).toEqual(expected);
  });

  it("fails only a blocking row over its tier, and never an unmeasured one", () => {
    const [c, , , , locked, a] = contractRows("CLI-01", CONTRACT);
    if (c === undefined || locked === undefined || a === undefined) throw new Error("rows");
    expect(judge(c, 9, 3).status).toBe("passed");
    expect(judge(locked, 2.5, 2).status).toBe("failed");
    expect(judge(a, 0.4, 0.5).status).toBe("passed");
    expect(judge(a, null, 0.5, "no baseline").status).toBe("unmeasured");
  });

  it("renders the HTML with artboard, diff, tier and lock, escaping text", () => {
    const [row] = contractRows("CLI-01", CONTRACT);
    if (row === undefined) throw new Error("rows");
    const html = renderHtml([judge(row, 1.234, 3, "<mask>")], "v1");
    expect(html).toContain("<td>CLI-01a</td><td>1.23 %</td><td>C</td><td>—</td>");
    expect(html).toContain("&lt;mask&gt;");
    expect(html).not.toMatch(/\.png/);
    expect(renderHtml([], "v1", ["SHL-01"])).toContain("no Parity table (not measured): SHL-01");
  });
});
