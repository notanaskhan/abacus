// P-02-T03 (TASK-7503): SHL-02's screen contract lists the seven artboard states, records the e
// deviation (DEC-43, DF-14) and the clock decision (OQ-6), and its Links table names every outbound
// target, so the link-contract test knows each one.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { MANIFEST } from "./manifest";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const WEB = process.cwd();
const REPO = join(WEB, "..", "..");
const GRAPH = JSON.parse(
  readFileSync(join(WEB, "src", "routes", "handoff-links.json"), "utf8"),
) as { links: { from: string; to: string }[] };
const DOC = readFileSync(join(REPO, "docs", "screens", "SHL-02.md"), "utf8");

// The targets the handoff spec's INTERACTIONS name (the canvas link graph holds none for SHL-02).
const SPEC_TARGETS = [
  "CLI-02",
  "TAX-02",
  "TXP-00",
  "AUD-02",
  "CLS-02",
  "BND-02",
  "FIL-01",
  "INB-01",
  "WB-01",
  "WB-06",
  "SHL-17",
  "ENG-03",
  "CLI-06",
  "ENG-10",
];

function section(heading: string): string[] {
  const start = DOC.indexOf(`## ${heading}`);
  expect(start, heading).toBeGreaterThan(-1);
  const rest = DOC.slice(start + heading.length + 3);
  const end = rest.indexOf("\n## ");
  return (end === -1 ? rest : rest.slice(0, end)).split("\n");
}

describe("SHL-02 screen contract", () => {
  it("marks each of the seven artboards live, fixture-only or deferred", () => {
    const rows = section("States").filter((l) => l.startsWith("| "));
    for (const letter of ["a", "b", "c", "d", "e", "f", "g"]) {
      const row = rows.find((r) => r.startsWith(`| ${letter} |`));
      expect(row, letter).toBeDefined();
      expect(row).toMatch(/\| (live|fixture-only|deferred)[^|]*\|$/);
    }
  });

  it("records the e deviation and no wall count anywhere in the states", () => {
    const deviations = section("Deviations").join("\n");
    expect(deviations).toContain("DEC-43");
    expect(deviations).toContain("DF-14");
    const e = section("States").find((r) => r.startsWith("| e |"));
    expect(e).toContain("No footer note, lock glyph or count");
  });

  it("records the clock decision (a–e on E0, f–g on Sep 28)", () => {
    expect(DOC).toContain("a–e run on E0, Mon Sep 14, 2026 9:24 AM CT; f–g on Mon Sep 28, 2026");
    expect(section("Deviations").join("\n")).toContain("OQ-6");
  });

  it("names every outbound target, each a manifest screen", () => {
    const links = section("Links").join("\n");
    const targets = new Set([
      ...SPEC_TARGETS,
      ...GRAPH.links.filter((l) => l.from === "SHL-02").map((l) => l.to),
    ]);
    for (const target of targets) {
      expect(links, `SHL-02 → ${target}`).toContain(`| ${target} |`);
      expect(MANIFEST, target).toHaveProperty(target);
    }
  });

  it("keeps the canonical group order", () => {
    expect(section("Groups").join("\n")).toContain(
      "**Clients · Returns · Audits · Closes · Binders · Files ·\nInbox · Sessions · To-dos · Saved prompts · Actions**",
    );
  });
});
