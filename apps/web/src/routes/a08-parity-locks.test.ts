// A-08-T37 (TASK-8756; A-08 §5.4): the parity report lists A-08's 29 artboards at Tier C with 13
// locked (AUD-12 a, c, e · AUD-13 a, e · AUD-14 a, e · AUD-26 a, d · POR-17 a, b, c, f), read from
// the screen contracts' Parity tables the report itself reads.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { contractRows } from "../../e2e/parity/screen-rows";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const SCREENS = ["AUD-12", "AUD-13", "AUD-14", "AUD-26", "POR-17"] as const;

function rows() {
  return SCREENS.flatMap((id) =>
    contractRows(id, readFileSync(`${process.cwd()}/../../docs/screens/${id}.md`, "utf8")),
  ).filter((r) => r.state !== "host");
}

describe("A-08 parity locks", () => {
  it("test_ac1_29_artboards_reported_at_tier_c", () => {
    const all = rows();
    expect(all).toHaveLength(29);
    expect(all.every((r) => r.tier === "C")).toBe(true);
  });

  it("test_ac2_13_locked_as_a08_lists_them", () => {
    expect(
      rows()
        .filter((r) => r.locked)
        .map((r) => r.artboard)
        .sort(),
    ).toEqual(
      [
        "AUD-12a",
        "AUD-12c",
        "AUD-12e",
        "AUD-13a",
        "AUD-13e",
        "AUD-14a",
        "AUD-14e",
        "AUD-26a",
        "AUD-26d",
        "POR-17a",
        "POR-17b",
        "POR-17c",
        "POR-17f",
      ].sort(),
    );
  });

  it("test_ac3_host_frames_are_tier_d", () => {
    for (const id of SCREENS) {
      const host = contractRows(
        id,
        readFileSync(`${process.cwd()}/../../docs/screens/${id}.md`, "utf8"),
      ).find((r) => r.state === "host");
      expect(host?.tier).toBe("D");
    }
  });

  // G-04-T21 and C-01-T50's locks, read the same way (their tables first wrote "locked in …",
  // which the parser reads as scheduled, not locked).
  it.each([
    ["PLT-01", ["a", "b", "c", "d", "f", "g"]],
    ["ADM-14", ["a", "b", "c", "d", "e", "f"]],
    ["SHL-05", ["a", "b", "c", "d", "e", "f", "d2"]],
    ["CLS-01", ["a", "b", "c", "e"]],
    ["CLS-09", ["a", "e", "f"]],
    ["CLS-10", ["a", "d"]],
  ] as const)("%s locks its Tier C artboards", (id, locked) => {
    const found = contractRows(
      id,
      readFileSync(`${process.cwd()}/../../docs/screens/${id}.md`, "utf8"),
    ).filter((r) => r.locked && r.tier === "C");
    expect(found.map((r) => r.state).sort()).toEqual([...locked].sort());
  });
});
