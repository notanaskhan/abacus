// A-06-T32 (TASK-6006; DEC-2606; ADR-078): the completion golden figures against the screens'
// fixtures. The figure book is backend/tests/golden/scenario/brightwater_hale/completion_figures
// .json, transcribed from the epic; backend/tests/golden/scenario/test_a06t32_completion_figures.py
// checks the Brightwater Hale scenario against the same book, so a figure that drifts on either
// side fails. AUD-15's tab badge (3) is the list's `awaiting_decision` count (DEC-2612); the
// 26-row sign-off matrix isn't drawn (13 named rows, DEC-2391), so its check is expected to fail.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { bandOf } from "../../screens/AUD-15";
import { aud15List } from "../seed/aud15";
import { aud16Sum } from "../seed/aud16";
import { aud17Matrix, aud17Notes } from "../seed/aud17";
import { checklistView, statementsView } from "../seed/aud20";

interface Book {
  findings: { bands: number[]; total: number; badge: number };
  sum: { rollover: string; iron_curtain: string; pm: string; pct_of_pm: string };
  tie_out: { total: number };
  checklist: { total: number; yes: number; na: number; no: number };
  review_notes: { open: number; responded: number; cleared: number; total: number };
  matrix: { total: number };
  matrix_footer: Record<string, number>;
}

const here = dirname(fileURLToPath(import.meta.url));
const BOOK = JSON.parse(
  readFileSync(
    join(here, "..", "..", "..", "..", "..", "backend", "tests", "golden", "scenario",
      "brightwater_hale", "completion_figures.json"),
    "utf8",
  ),
) as Book; // prettier-ignore

const usd = (s: string): number => Math.round(Number(s));

describe("A-06-T32: the completion figures drawn by the screens' fixtures", () => {
  it("AUD-15 a: 9 findings in bands 1 + 2 + 1 + 5", () => {
    const rows = aud15List("a").items;
    const bands = ["significant_deficiency", "deficiency", "exception", "misstatements"].map(
      (band) => rows.filter((f) => bandOf(f) === band).length,
    );
    expect(bands).toEqual(BOOK.findings.bands);
    expect(rows.length).toBe(BOOK.findings.total);
  });

  it("AUD-15 a: the Findings tab badge reads 3 (F-01, F-03, F-04 awaiting a decision)", () => {
    expect(aud15List("a").counts?.awaiting_decision).toBe(BOOK.findings.badge);
  });

  it("AUD-16 a: rollover 34,150, iron curtain 22,250, 18.1% of PM", () => {
    const sum = aud16Sum("a");
    expect(usd(sum.rollover)).toBe(usd(BOOK.sum.rollover));
    expect(usd(sum.iron_curtain)).toBe(usd(BOOK.sum.iron_curtain));
    expect(usd(sum.thresholds?.pm ?? "0")).toBe(usd(BOOK.sum.pm));
    expect(sum.pct_of_pm).toBe(BOOK.sum.pct_of_pm);
  });

  it("AUD-20 a: 63 of 63 tie; checklist 97 + 45 + 0 = 142", () => {
    const tie = statementsView("a").current?.tie_out;
    expect(tie?.total).toBe(BOOK.tie_out.total);
    expect(tie?.tied).toBe(BOOK.tie_out.total);
    const items = checklistView().items;
    expect(items.length).toBe(BOOK.checklist.total);
    expect(items.filter((i) => i.answer === "yes").length).toBe(BOOK.checklist.yes);
    expect(items.filter((i) => i.answer === "na").length).toBe(BOOK.checklist.na);
    expect(items.filter((i) => i.answer === "no").length).toBe(BOOK.checklist.no);
  });

  it("AUD-17 a: notes 2 + 1 + 11 = 14 and the matrix footer", () => {
    const notes = aud17Notes("a");
    const count = (status: string): number =>
      notes.items.filter((n) => n.status === status).length;
    expect(count("open")).toBe(BOOK.review_notes.open);
    expect(count("responded")).toBe(BOOK.review_notes.responded);
    expect(count("cleared")).toBe(BOOK.review_notes.cleared);
    expect(notes.total).toBe(BOOK.review_notes.total);
    expect(aud17Matrix().footer).toEqual(BOOK.matrix_footer);
  });

  it.fails("AUD-17 a: the matrix draws 26 papers (DEC-2391: 13 named so far)", () => {
    expect(aud17Matrix().rows.length).toBe(BOOK.matrix.total);
  });
});
