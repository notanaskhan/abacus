// F-07-T19 (TASK-7949; handoff TPL-17 a–f): "All six artboards render, the K-1 list ties to
// 1,231,600 / 18,400 / 6,200 / 600,000, diagnostics read 1 error and 2 warnings, and every K-1
// shows Draft K-1 - pre-release."
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TPL17_BOARDS, Tpl17Specimen } from "./tpl17";
import { TPL17_DIAGNOSTICS, TPL17_K1S, TPL17_TOTAL, tpl17File } from "./tpl17-data";

afterEach(cleanup);

describe("TPL-17 Form renderer specimen", () => {
  it("all six artboards render", () => {
    render(<Tpl17Specimen />);
    for (const b of TPL17_BOARDS) {
      expect(document.querySelector(`[data-tpl17='${b.id}']`)).toBeTruthy();
    }
    expect(TPL17_BOARDS.map((b) => b.id)).toEqual(["a", "b", "c", "d", "e", "f"]);
  });

  it("the K-1 boxes foot to the Schedule K total, as written (the specimen never sums at render)", () => {
    for (let box = 0; box < 4; box += 1) {
      const footed = TPL17_K1S.reduce((n, k) => n + Number(k.boxes[box]), 0);
      expect(String(footed)).toBe(TPL17_TOTAL.boxes[box]);
    }
    expect(TPL17_TOTAL.boxes).toEqual(["1231600", "18400", "6200", "600000"]);
  });

  it("diagnostics read 1 error and 2 warnings", () => {
    expect(TPL17_DIAGNOSTICS.filter((d) => d.severity === "error").length).toBe(1);
    expect(TPL17_DIAGNOSTICS.filter((d) => d.severity === "warning").length).toBe(2);
  });

  it("every K-1 shows Draft K-1 · pre-release", () => {
    expect(new Set(TPL17_K1S.map((k) => k.status))).toEqual(new Set(["Draft K-1 · pre-release"]));
    render(<Tpl17Specimen />);
    expect(screen.getAllByText("Draft K-1 · pre-release").length).toBeGreaterThanOrEqual(5);
  });

  it("the traced Schedule K fields are regions on the rendered pages (FormRenderer parity)", () => {
    const file = tpl17File();
    expect(file.pages.length).toBe(6);
    const matches = new Set(file.regions.map((r) => r.match));
    for (const m of ["sch-k-2", "sch-k-5", "sch-k-18a", "sch-k-19a", "sch-k-20a"]) {
      expect(matches.has(m as never)).toBe(true);
    }
  });
});
