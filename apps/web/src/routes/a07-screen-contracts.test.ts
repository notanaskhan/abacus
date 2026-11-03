// A-07-T02 (SPEC-644 AC-2; TASK-3252): every A-07 screen contract marks each artboard letter
// live, fixture-only or deferred, and its Links table names every outbound target the handoff's
// link graph holds, so the link-contract test knows each one.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const WEB = process.cwd();
const REPO = join(WEB, "..", "..");
const GRAPH = JSON.parse(
  readFileSync(join(WEB, "src", "routes", "handoff-links.json"), "utf8"),
) as { links: { from: string; to: string }[] };

const ARTBOARDS: Record<string, string[]> = {
  "AUD-18": ["a", "b", "b2", "c", "d", "e"],
  "AUD-19": ["a", "a2", "b", "c", "d", "e", "f"],
  "AUD-21": ["a", "a2", "b", "c", "d", "e", "f"],
  "AUD-22": ["a", "a2", "a3", "b", "c", "d", "e"],
  "AUD-23": ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"],
  "AUD-24": ["a", "b", "c", "d", "e", "f"],
  "AUD-25": ["a", "b", "b2", "c", "d", "e"],
};

function section(doc: string, heading: string): string[] {
  const start = doc.indexOf(`## ${heading}`);
  const rest = doc.slice(start + heading.length + 3);
  const end = rest.indexOf("\n## ");
  return (end === -1 ? rest : rest.slice(0, end)).split("\n");
}

describe("A-07 screen contracts", () => {
  it("covers 49 artboards", () => {
    expect(Object.values(ARTBOARDS).flat()).toHaveLength(49);
  });

  for (const [id, letters] of Object.entries(ARTBOARDS)) {
    const doc = readFileSync(join(REPO, "docs", "screens", `${id}.md`), "utf8");

    it(`${id} marks every artboard live, fixture-only or deferred`, () => {
      const rows = section(doc, "States").filter((l) => l.startsWith("| "));
      for (const letter of letters) {
        const row = rows.find((r) => r.startsWith(`| ${letter} |`));
        expect(row, `${id} ${letter}`).toBeDefined();
        expect(row).toMatch(/\| (live|fixture-only|deferred)[^|]*\|$/);
      }
    });

    it(`${id} names every outbound target of the handoff link graph`, () => {
      const links = section(doc, "Links").join("\n");
      const targets = new Set(GRAPH.links.filter((l) => l.from === id).map((l) => l.to));
      for (const target of targets) expect(links, `${id} → ${target}`).toContain(`| ${target} |`);
    });
  }
});
