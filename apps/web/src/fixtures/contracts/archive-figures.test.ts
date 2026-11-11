// A-07-T43 (TASK-6736; ADR-078, author notanaskhan): the issuance-to-archive golden figures against
// the screens' fixtures. The figure book is backend/tests/golden/scenario/brightwater_hale/
// archive_figures.json, transcribed from A-07 §1, F2, F3, F6 and F7; the backend's
// test_a07t43_archive_figures.py and test_a07t43_archive_golden.py hold the content, the clocks
// and the loaded scenario to the same book, so a figure that drifts on either side fails.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { aud18, aud19, aud24, aud25 } from "../seed/audit-completion";

interface Book {
  release: { at: string; by: string; documentation_completion_date: string };
  assembling: { days_left: number };
  lock: { at: string; by: string; days_left: number };
  retention: { retention_until: string };
  eqr_checklist: { done_at_1105: number; total: number };
  completion_checklist: {
    done: number;
    not_applicable: number;
    open: number;
    summary_total: number;
  };
  archive_checklist: { done_on_oct_22: number; total: number };
}

const here = dirname(fileURLToPath(import.meta.url));
const BOOK = JSON.parse(
  readFileSync(
    join(here, "..", "..", "..", "..", "..", "backend", "tests", "golden", "scenario",
      "brightwater_hale", "archive_figures.json"),
    "utf8",
  ),
) as Book; // prettier-ignore

describe("A-07-T43: the archive figures drawn by the screens' fixtures", () => {
  it("AUD-18 a: 6 of 10 on the EQR checklist", () => {
    const eqr = aud18("a");
    expect(eqr.checklist_done).toBe(BOOK.eqr_checklist.done_at_1105);
    expect(eqr.checklist_total).toBe(BOOK.eqr_checklist.total);
  });

  it("AUD-19 a: 12 of 17, one not applicable, five open", () => {
    const view = aud19("a");
    expect(view.complete).toBe(BOOK.completion_checklist.done);
    expect(view.not_applicable).toBe(BOOK.completion_checklist.not_applicable);
    expect(view.open).toBe(BOOK.completion_checklist.open);
    expect(view.total).toBe(BOOK.completion_checklist.summary_total);
  });

  it("AUD-24 d: released Oct 9 at 10:07 AM by Margaret Okonkwo; Dec 8 is 60 days on", () => {
    const done = aud24("d");
    expect(done.released_at).toBe(BOOK.release.at);
    expect(done.released_by_name).toBe(BOOK.release.by);
    expect(done.documentation_completion_date).toBe(BOOK.release.documentation_completion_date);
  });

  it("AUD-25 a: Archive in 47 days on Oct 22, 8 of 9, retention to Oct 9, 2033", () => {
    const a = aud25("a");
    expect(a.days_left).toBe(BOOK.assembling.days_left);
    expect(a.checklist_done).toBe(BOOK.archive_checklist.done_on_oct_22);
    expect(a.checklist_total).toBe(BOOK.archive_checklist.total);
    expect(a.retention_until).toBe(BOOK.retention.retention_until);
    expect(a.documentation_completion_date).toBe(BOOK.release.documentation_completion_date);
  });

  it("AUD-25 c: locked Dec 3 at 4:18 PM CST by Hannah Leclerc, five days before the deadline", () => {
    const c = aud25("c");
    expect(c.locked_at).toBe(BOOK.lock.at);
    expect(c.locked_by_name).toBe(BOOK.lock.by);
    expect(c.days_left).toBe(BOOK.lock.days_left);
    expect(c.checklist_done).toBe(BOOK.archive_checklist.total);
  });
});
