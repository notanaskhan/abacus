// R-02-T08 / R-02-T06 (TASK-6115): the portal's figures book, read by the screens' fixtures. The
// book is transcribed from R-02 §3 (never the code) and the backend's C10/C18 suites read the same
// file; here the arithmetic the artboards draw, and the to-do words POR-02 shows for R-02's kinds.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { COPY as HOME } from "../../screens/POR-02/copy";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const BOOK = JSON.parse(
  readFileSync(
    join(
      process.cwd(),
      "..",
      "..",
      "backend",
      "tests",
      "golden",
      "scenario",
      "brightwater_hale",
      "portal_figures.json",
    ),
    "utf8",
  ),
) as {
  uncorrected_misstatements: {
    would_increase: string;
    would_decrease: string;
    net_effect: string;
  };
  attest_entries: Record<string, { total: string; lines: string[] } | string[]>;
  fs_draft: {
    pages: number;
    page_2: Record<string, { parts: string[]; total: string } | string>;
  };
};

const cents = (v: string): number => Math.round(Number(v) * 100);
const sum = (values: string[]): number => values.reduce((total, v) => total + cents(v), 0);

describe("the portal figures book", () => {
  it("POR-08 e2: the uncorrected net effect is 35,300.00 − 13,050.00", () => {
    const um = BOOK.uncorrected_misstatements;
    expect(cents(um.would_increase) - cents(um.would_decrease)).toBe(cents(um.net_effect));
    expect(um.net_effect).toBe("22250.00");
  });

  it("POR-08 e: each entry's sub-lines foot to its amount", () => {
    for (const key of ["receivable", "accrued"]) {
      const entry = BOOK.attest_entries[key] as { total: string; lines: string[] };
      expect(sum(entry.lines)).toBe(cents(entry.total));
    }
  });

  it("POR-09 a: page 2 foots and the draft is 14 pages", () => {
    const page = BOOK.fs_draft.page_2;
    for (const key of ["investments", "receivables", "prior_year"]) {
      const block = page[key] as { parts: string[]; total: string };
      expect(sum(block.parts)).toBe(cents(block.total));
    }
    const investments = page.investments as { total: string };
    const receivables = page.receivables as { total: string };
    expect(cents(investments.total) + cents(receivables.total)).toBe(
      cents(page.net_assets as string),
    );
    expect(BOOK.fs_draft.pages).toBe(14);
  });

  it("POR-02: R-02's to-dos (approvals waiting, deliverables ready) open Approvals and Deliverables", () => {
    expect(HOME.todo.go.approve).toBe("Go to Approvals →");
    expect(HOME.todo.go.deliverables).toBe("Go to Deliverables →");
  });
});
