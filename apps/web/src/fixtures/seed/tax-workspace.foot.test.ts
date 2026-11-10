// T-04-T07: the return workspace slice foots (the screen contracts' figures).
import { describe, expect, it } from "vitest";
import { FIGURES, LINE_3B, TREATMENTS, workspace } from "./tax-workspace";

const sum = (xs: readonly string[]): number => xs.reduce((n, x) => n + Number(x), 0);

describe("T-04 return workspace slice", () => {
  it("line 8 foots 598,030 + 1,550 + 16,025 = 615,605", () => {
    expect(sum(FIGURES.line8Parts)).toBe(Number(FIGURES.line8Total));
  });

  it("Ridgeline box 2 shares foot to 307,900", () => {
    expect(sum(FIGURES.ridgelineBox2Shares)).toBe(Number(FIGURES.ridgelineBox2Total));
  });

  it("Review 37 = 41 − 4, then 36; TAX-04 approves one: 36 → 35", () => {
    expect(FIGURES.reviewDocuments - FIGURES.reviewApproved).toBe(37);
    expect(workspace("a").review_count - workspace("b").review_count).toBe(1);
  });

  it("TAX-04 c's mismatch is the transposition 14,820 vs 14,280", () => {
    expect(LINE_3B.amount).not.toBe(LINE_3B.typed);
  });

  it("TXI-02 a: seven proposed, one approved", () => {
    expect(TREATMENTS.filter((t) => t.status === "proposed")).toHaveLength(7);
    expect(TREATMENTS.filter((t) => t.status === "approved")).toHaveLength(1);
  });
});
