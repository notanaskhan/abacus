// F-07-T25 (TASK-7507, DEC-4507): tier 4's status words are C2's. `filing_deadline` is in the
// generated registry with every code T13's deadline chip draws, all derived (never stored), and no
// kit-local draft status type is left in packages/ui.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { STATUS_REGISTRY } from "./status.gen";
import type { RegistryCode } from "./status";

const here = dirname(fileURLToPath(import.meta.url));
const CODES = [
  "overdue",
  "due_7",
  "due_30",
  "later",
  "done",
  "postponed",
  "extended",
] as const satisfies readonly RegistryCode<"filing_deadline">[];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

describe("F-07-T25 tier-4 status rows", () => {
  it("carries every filing_deadline code, derived", () => {
    const object = STATUS_REGISTRY.filing_deadline;
    expect(Object.keys(object).sort()).toEqual([...CODES].sort());
    for (const code of CODES) expect(object[code].derived, code).toBe(true);
    expect(object.postponed.label).toBe("Postponed → {date}");
    expect(object.overdue.label).toBe("Past due");
  });

  it("keeps the session and K-1 package words", () => {
    expect(STATUS_REGISTRY.workbench_session.awaiting_answer.label).toBe("Needs your answer");
    expect(STATUS_REGISTRY.k1_package.draft.label).toBe("Draft K-1 · pre-release");
  });

  it("leaves no kit-local draft status type in packages/ui", () => {
    expect(existsSync(join(here, "tier4", "draft-status.ts"))).toBe(false);
    for (const path of files(here)) {
      if (!/\.(ts|tsx)$/.test(path) || path.endsWith(".test.ts")) continue;
      expect(readFileSync(path, "utf8"), path).not.toMatch(/DraftStatus\b/);
    }
  });
});
