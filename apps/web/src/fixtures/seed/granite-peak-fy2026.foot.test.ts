// F-08-T02 (DEC-5617): the TPL-20 and TPL-21 footings as tests (F-08 G1).
import { describe, expect, it } from "vitest";
import type { BoardDraft } from "../contracts/board";
import { AUDIT_PROGRAM_BOARD, afterBhFs430Move } from "./granite-peak-fy2026-board";
import { SURL_SHEET } from "./granite-peak-fy2026-surl-sheet";
import { slugOf } from "./people";

const columns = (b: BoardDraft): number[] =>
  (["not_started", "in_progress", "in_review", "complete"] as const).map(
    (col) => b.cards.filter((c) => c.column === col).length,
  );

describe("Granite Peak FY2026 wave-5 slices", () => {
  it("TPL-20: stratum 1 foots 3,286,400 = 1,942,600 (SURL-01–14) + 1,343,800 (SURL-15–24)", () => {
    const named = SURL_SHEET.rows.reduce((n, r) => n + r.amount, 0);
    expect(named).toBe(1942600);
    const derived = SURL_SHEET.derived[0];
    expect(derived?.total).toBe(1343800);
    expect(named + (derived?.total ?? 0)).toBe(SURL_SHEET.sections[0]?.total);
    expect(SURL_SHEET.sections.reduce((n, s) => n + s.count, 0)).toBe(SURL_SHEET.status.rows);
  });

  it("TPL-20: exactly one exception, SURL-05 Front Range Freight Co. 68,400", () => {
    const ex = SURL_SHEET.rows.filter((r) => r.conclusion.value === "improperly_excluded");
    expect(ex.map((r) => [r.key, r.vendor, r.amount])).toEqual([
      ["SURL-05", "Front Range Freight Co.", 68400],
    ]);
    expect(SURL_SHEET.status.exceptions).toBe(ex.length);
  });

  it("TPL-21: columns 4 · 5 · 2 · 2, then 3 · 6 · 2 · 2 after BH-FS-430 moves", () => {
    expect(AUDIT_PROGRAM_BOARD.cards.length).toBe(13);
    expect(columns(AUDIT_PROGRAM_BOARD)).toEqual([4, 5, 2, 2]);
    const moved = afterBhFs430Move(AUDIT_PROGRAM_BOARD);
    expect(columns(moved)).toEqual([3, 6, 2, 2]);
    // The move signs nothing off.
    expect(moved.cards.map((c) => c.signoffs)).toEqual(
      AUDIT_PROGRAM_BOARD.cards.map((c) => c.signoffs),
    );
  });

  it("TPL-21 (F-08-T23): every execution area's program count is its cards; 8 + 13 = 21", () => {
    const areas = AUDIT_PROGRAM_BOARD.areas;
    for (const a of areas.filter((x) => x.phase === "execution")) {
      expect(AUDIT_PROGRAM_BOARD.cards.filter((c) => c.area === a.key).length).toBe(a.programs);
    }
    const total = areas.reduce((n, a) => n + a.programs, 0);
    expect(total).toBe(AUDIT_PROGRAM_BOARD.binder.total);
  });

  it("TPL-21e: binder Preparer 12 of 21 · Reviewer 10 of 21", () => {
    expect(AUDIT_PROGRAM_BOARD.binder).toEqual({ preparer: 12, reviewer: 10, total: 21 });
  });

  it("?as=cole-hart and ?as=simone-baptiste name seated people", () => {
    expect(slugOf("Cole Hart")).toBe("cole-hart");
    expect(slugOf("Simone Baptiste")).toBe("simone-baptiste");
  });
});
