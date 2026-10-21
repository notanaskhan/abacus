import { describe, expect, it } from "vitest";
import { progress } from "../format";
import {
  RING_CIRCUMFERENCE,
  barView,
  isLongPillLabel,
  kpiDelta,
  percentOf,
  practiceOpen,
  ringView,
  sparkPoints,
  stepViews,
} from "./progress-model";

// The C-19 helpers, from the bundle's IMPLEMENTATION step 1.

describe("percentOf", () => {
  it("rounds half up to a whole percent and agrees with format.progress()", () => {
    expect(percentOf(4, 24)).toBe(17);
    expect(percentOf(1, 8)).toBe(13);
    expect(percentOf(0, 5)).toBe(0);
    expect(percentOf(3, 0)).toBe(0);
    for (const [d, t] of [
      [4, 24],
      [13, 20],
      [9, 13],
      [1, 3],
      [2, 3],
      [312, 312],
    ] as const) {
      expect(progress(d, t)).toBe(`${String(percentOf(d, t))}% (${String(d)} / ${String(t)})`);
    }
  });
  it("shows 17% (4 / 24)", () => {
    expect(progress(4, 24)).toBe("17% (4 / 24)");
  });
});

describe("barView", () => {
  it("labels n of N with the default and the noun", () => {
    expect(barView(9, 13).left).toBe("9 of 13 complete");
    expect(barView(7, 18, { noun: "files uploaded" }).left).toBe("7 of 18 files uploaded");
    expect(barView(9, 13).width).toBe("69%");
  });
  it("is indeterminate with no total: no valuenow, busy, a default label", () => {
    const v = barView(0, null);
    expect(v.indeterminate).toBe(true);
    expect(v.width).toBeNull();
    expect(v.left).toBe("Counting files…");
    expect(v.aria["aria-valuenow"]).toBeUndefined();
    expect(v.aria["aria-busy"]).toBe(true);
    expect(barView(0, null, { left: "Counting files in the binder…" }).left).toBe(
      "Counting files in the binder…",
    );
  });
  it("clamps the fill but keeps the real numbers in the label", () => {
    expect(barView(20, 18).width).toBe("100%");
    expect(barView(20, 18).left).toBe("20 of 18 complete");
  });
  it("groups thousands", () => {
    expect(barView(1204, 3000).left).toBe("1,204 of 3,000 complete");
  });
});

describe("ringView", () => {
  it("runs the offset from the circumference to 0 and finishes at 1", () => {
    expect(ringView(0).offset).toBeCloseTo(RING_CIRCUMFERENCE);
    expect(ringView(0.5).offset).toBeCloseTo(RING_CIRCUMFERENCE / 2);
    expect(ringView(1).offset).toBeCloseTo(0);
    expect(ringView(1).done).toBe(true);
    expect(ringView(0.99).done).toBe(false);
    expect(ringView(0.45).valueNow).toBe(45);
  });
  it("hides the arc at 0, where a round cap leaves a dot", () => {
    expect(ringView(0).arc).toBe(false);
    expect(ringView(0.01).arc).toBe(true);
  });
});

describe("stepViews", () => {
  const steps = [
    { name: "Read the general ledger", done: 312, total: 312 },
    { name: "Match bank transactions", done: 10, total: 312 },
    { name: "Draft reconciling entries", done: 0, total: 18 },
    { name: "Wait for the reviewer", done: 0, total: 0 },
  ];
  it("puts only the first unfinished step in progress", () => {
    expect(stepViews(steps).map((s) => s.state)).toEqual([
      "done",
      "progress",
      "pending",
      "pending",
    ]);
  });
  it("writes the counter with grouping and a whole percent, or a dash", () => {
    expect(stepViews(steps).map((s) => s.counter)).toEqual([
      "312 of 312 · 100%",
      "10 of 312 · 3%",
      "0 of 18 · 0%",
      "—",
    ]);
  });
});

describe("kpiDelta", () => {
  it("draws the arrow by direction and the judgement by good or bad", () => {
    expect(kpiDelta("good")).toEqual({ arrow: "up", judgement: "good" });
    expect(kpiDelta("good-down")).toEqual({ arrow: "down", judgement: "good" });
    expect(kpiDelta("bad")).toEqual({ arrow: "up", judgement: "bad" });
    expect(kpiDelta("bad-down")).toEqual({ arrow: "down", judgement: "bad" });
    expect(kpiDelta("flat")).toEqual({ arrow: null, judgement: "flat" });
  });
});

describe("sparkPoints", () => {
  it("spans x 2 to 74 and y 21 (min) to 3 (max)", () => {
    expect(sparkPoints([0, 10])).toBe("2.0,21.0 74.0,3.0");
    const pts = sparkPoints([4, 6, 5, 9, 8, 12, 14]).split(" ");
    expect(pts).toHaveLength(7);
    expect(pts[0]).toBe("2.0,21.0");
    expect(pts[6]).toBe("74.0,3.0");
  });
  it("draws nothing for fewer than two readings", () => {
    expect(sparkPoints([])).toBe("");
    expect(sparkPoints([3])).toBe("");
  });
});

describe("pill size and the practice strip", () => {
  it("drops to 10.5px above 14 characters", () => {
    expect(isLongPillLabel("Awaiting signat")).toBe(true); // 15
    expect(isLongPillLabel("Filed · Accepte")).toBe(true); // 15
    expect(isLongPillLabel("Filed · Accept")).toBe(false); // 14
    expect(isLongPillLabel("Prepared")).toBe(false);
  });
  it("adds up: the two Not started returns count in the 79 and have no tile", () => {
    expect(practiceOpen([17, 15, 11, 7, 8, 9, 10], 2)).toBe(79);
    expect(practiceOpen([17, 15, 11, 7, 8, 9, 10], 2) + 145).toBe(224);
  });
});
