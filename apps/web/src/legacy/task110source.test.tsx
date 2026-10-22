// TASK-110: citations open the source at the cited cell, highlighted.
import { describe, expect, it } from "vitest";
import { parseCell } from "./EvidencePreview";

describe("parseCell", () => {
  it("reads A1-style references, with a sheet or absolute marks", () => {
    expect(parseCell("C9")).toEqual({ col: 2, row: 9 });
    expect(parseCell("Sheet1!$AB$12")).toEqual({ col: 27, row: 12 });
    expect(parseCell("a1")).toEqual({ col: 0, row: 1 });
  });

  it("refuses what isn't a cell", () => {
    expect(parseCell("page 2")).toBeNull();
    expect(parseCell("")).toBeNull();
  });
});
