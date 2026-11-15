// A-08-T05 (SPEC-657 AC-0.4, AC-0.5): the typed fixtures foot. 236 unique JE hits, 14 = 8 + 6
// lines, Lakeshore revenue 4,174,000 (expenses 4,014,000), POR-17 a's invoices 412,600, coverage
// 897,950 / 5,860,000 = 15.3%. Whole cents as BigInt: no floating point.
import { describe, expect, it } from "vitest";
import {
  GRANITE_PEAK_COVERAGE,
  GRANITE_PEAK_CRITERIA,
  GRANITE_PEAK_LINES,
  GRANITE_PEAK_TALLIES,
  GRANITE_PEAK_UNIQUE_FLAGGED,
  LAKESHORE_LINES,
  POR17_SUMMIT_TRAIL,
} from "../seed/fieldwork";

const cents = (s: string): bigint => {
  const [whole = "0", frac = ""] = s.replace("-", "").split(".");
  const v = BigInt(whole) * 100n + BigInt((frac + "00").slice(0, 2));
  return s.startsWith("-") ? -v : v;
};
const sum = (xs: string[]): bigint => xs.reduce((a, x) => a + cents(x), 0n);

describe("A-08 typed fixtures", () => {
  it("JE criteria hit 142 · 38 · 61 · 17 · 9 for 236 unique", () => {
    expect(GRANITE_PEAK_CRITERIA.map((c) => c.hit_count)).toEqual([142, 38, 61, 17, 9]);
    expect(GRANITE_PEAK_UNIQUE_FLAGGED).toBe(236);
  });

  it("Granite Peak analytics: 14 = 8 + 6, 6 explained + 2 unexplained", () => {
    expect(GRANITE_PEAK_LINES).toHaveLength(14);
    const over = GRANITE_PEAK_LINES.filter((l) => l.over);
    expect(over).toHaveLength(8);
    expect(GRANITE_PEAK_LINES.length - over.length).toBe(6);
    expect(over.filter((l) => l.status === "unexplained")).toHaveLength(2);
    expect(GRANITE_PEAK_TALLIES).toMatchObject({
      lines: 14,
      over_threshold: 8,
      explained: 6,
      unexplained: 2,
    });
    for (const l of GRANITE_PEAK_LINES) expect(cents(l.cy) - cents(l.py)).toBe(cents(l.change));
  });

  it("Lakeshore revenue foots 4,174,000 and expenses 4,014,000; only Grants is over", () => {
    const revenue = LAKESHORE_LINES.filter((l) => l.group_key === "revenue").map((l) => l.cy);
    const expenses = LAKESHORE_LINES.filter((l) => l.group_key === "expenses").map((l) => l.cy);
    expect(sum(revenue)).toBe(cents("4174000"));
    expect(sum(expenses)).toBe(cents("4014000"));
    expect(LAKESHORE_LINES.filter((l) => l.over).map((l) => l.caption)).toEqual(["Grants"]);
  });

  it("POR-17 a's invoices foot to the balance and the page carries one confirmation", () => {
    const request = POR17_SUMMIT_TRAIL.request;
    if (request === null || request === undefined) throw new Error("no request");
    expect(sum(request.invoices.map((i) => i.amount))).toBe(
      cents(request.balance_per_client ?? "0"),
    );
    expect(Object.keys(POR17_SUMMIT_TRAIL).sort()).toEqual([
      "answered_on",
      "receipt",
      "request",
      "state",
    ]);
  });

  it("coverage is 897,950 of 5,860,000 = 15.3%", () => {
    const sent = cents(GRANITE_PEAK_COVERAGE.sent_total);
    const total = cents(GRANITE_PEAK_COVERAGE.population_total);
    expect(sent).toBe(cents("897950"));
    expect((sent * 1000n + total / 2n) / total).toBe(153n);
    expect(GRANITE_PEAK_COVERAGE.sent_pct).toBe("15.3");
  });
});
