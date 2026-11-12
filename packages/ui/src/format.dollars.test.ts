// T-05-T37 (TASK-7627; DEC-4622): the TB grammar's dollars style (TXP-02: "$" on every cell,
// whole dollars, credits in parentheses, "—" for zero).
import { describe, expect, it } from "vitest";
import { amount, prose } from "./format";

describe("dollars", () => {
  it("prints $ on whole dollars, credits in parentheses, zero as a dash", () => {
    expect(amount("693667", "dollars")).toEqual({ text: "$693,667", tone: "pos" });
    expect(amount("-2625167", "dollars")).toEqual({ text: "($2,625,167)", tone: "neg" });
    expect(amount("0", "dollars")).toEqual({ text: "—", tone: "zero" });
    expect(amount("0", "dollars", { zero: "explicit" }).text).toBe("$0");
  });

  it("reads in prose with a minus sign", () => {
    expect(prose("-18500", "dollars")).toBe("-$18,500");
  });
});
