// F-06-T02 (SPEC-400 AC-34): the E0 tax-season specimen seed foots. Every sum is done here, in
// BigInt over the seed's decimal strings, never in a kit. Figures from F-06.md §5.3 and the
// screen contracts' Figures sections (docs/screens/TPL-01, TPL-06, TPL-10, TPL-16, TPL-19).

import { describe, expect, it } from "vitest";
import {
  BRIDGE,
  CAPITAL_ROWS,
  CAPITAL_TOTAL,
  DEPRECIATION,
  E6,
  ENVELOPES,
  EXTENDED_TOTAL,
  FELD_OPEN_REQUESTS,
  feldCounts,
  OPEN_STATUSES,
  OPEN_TOTAL,
  RETURNS_BY_OFFICE,
  RETURNS_TOTAL,
  STATE_SHARES,
  STATUS_COUNTS,
  TALLY_DRAFTED,
  TALLY_FIXED,
  TAX_RETURNS,
  TIE_OUT,
  TRANSFER,
} from "../tax";

const b = (s: string): bigint => BigInt(s);
const sum = (xs: readonly string[]): bigint => xs.reduce((a, x) => a + b(x), 0n);

describe("TPL-01 practice board", () => {
  it("AC-34: 224 TY2025 returns, 79 open and 145 done", () => {
    expect(TAX_RETURNS).toHaveLength(RETURNS_TOTAL);
    const open = TAX_RETURNS.filter((r) => OPEN_STATUSES.includes(r.status));
    expect(open).toHaveLength(OPEN_TOTAL);
    expect(TAX_RETURNS.length - open.length).toBe(145);
  });

  it("AC-34: the open tiles foot 8 + 9 + 17 + 15 + 11 + 7 + 10 + 2 = 79", () => {
    for (const status of Object.keys(STATUS_COUNTS) as (keyof typeof STATUS_COUNTS)[]) {
      expect(
        TAX_RETURNS.filter((r) => r.status === status),
        status,
      ).toHaveLength(STATUS_COUNTS[status]);
    }
    const tiles = [8, 9, 17, 15, 11, 7, 10, 2];
    expect(tiles.reduce((a, n) => a + n, 0)).toBe(79);
    expect(79 + 145).toBe(224);
    expect(STATUS_COUNTS.filed + STATUS_COUNTS.accepted).toBe(145);
  });

  it("AC-34: 161 returns are extended", () => {
    expect(TAX_RETURNS.filter((r) => r.extended)).toHaveLength(EXTENDED_TOTAL);
  });

  it("AC-34: offices read Chicago 98 · Denver 64 · New York 62 (§9.1)", () => {
    for (const [office, n] of Object.entries(RETURNS_BY_OFFICE)) {
      expect(
        TAX_RETURNS.filter((r) => r.office === office),
        office,
      ).toHaveLength(n);
    }
  });

  it("AC-34: Awaiting signature is exactly the ten returns behind E1–E10", () => {
    const awaiting = TAX_RETURNS.filter((r) => r.status === "awaiting_signature");
    expect(awaiting.map((r) => r.envelope).sort()).toEqual(ENVELOPES.map((e) => e.key).sort());
    for (const e of ENVELOPES) {
      expect(awaiting.find((r) => r.envelope === e.key)?.client).toBe(e.client);
    }
  });

  it("AC-34: labels and ids are unique", () => {
    expect(new Set(TAX_RETURNS.map((r) => r.label)).size).toBe(RETURNS_TOTAL);
    expect(new Set(TAX_RETURNS.map((r) => r.id)).size).toBe(RETURNS_TOTAL);
  });
});

describe("TPL-16 envelope E6", () => {
  it("AC-34: 61,200 − 58,904 = 2,296 and the NY refund is 410", () => {
    expect(b(E6.partI.withheld) - b(E6.partI.totalTax)).toBe(b(E6.partI.refund));
    expect(E6.partI.refund).toBe("2296");
    expect(E6.nyRefund).toBe("410");
  });

  it("AC-34: TINs are masked strings only, and the record has six items", () => {
    expect(JSON.stringify(E6)).not.toMatch(/\b\d{3}-?\d{2}-?\d{4}\b/);
    expect(E6.evidence).toHaveLength(6);
  });
});

describe("TPL-06 Ridgeline capital", () => {
  const cols = [
    "beginning",
    "contributions",
    "income",
    "taxExempt",
    "transfers",
    "distributions",
    "endingDrafted",
    "endingFixed",
  ] as const;

  it("AC-34: every row crossfoots, as drafted and fixed", () => {
    for (const r of CAPITAL_ROWS) {
      const drafted = sum([r.beginning, r.contributions, r.income, r.transfers, r.distributions]);
      expect(drafted, r.partner).toBe(b(r.endingDrafted));
      expect(drafted + b(r.taxExempt), r.partner).toBe(b(r.endingFixed));
    }
  });

  it("AC-34: every column foots to the Total row", () => {
    for (const c of cols) expect(sum(CAPITAL_ROWS.map((r) => r[c])), c).toBe(b(CAPITAL_TOTAL[c]));
  });

  it("AC-34: 5,960,000 + 250,000 + 1,250,000 − 600,000 = 6,860,000 → 6,866,200", () => {
    expect(5_960_000n + 250_000n + 1_250_000n - 600_000n).toBe(b(CAPITAL_TOTAL.endingDrafted));
    expect(b(CAPITAL_TOTAL.endingDrafted) + b(CAPITAL_TOTAL.taxExempt)).toBe(
      b(CAPITAL_TOTAL.endingFixed),
    );
    expect(sum(["124", "2356", "2015", "155", "1550"])).toBe(6_200n);
  });

  it("AC-34: transfers net to 0 and 331,405 = 2,319,835 × 5/35", () => {
    expect(sum(CAPITAL_ROWS.map((r) => r.transfers))).toBe(0n);
    expect(sum(TRANSFER.pieces)).toBe(b(TRANSFER.pellStreetJune30));
    const exact = b(TRANSFER.pellStreetJune30) * BigInt(TRANSFER.points);
    expect(exact / BigInt(TRANSFER.of)).toBe(b(TRANSFER.capital));
    expect(b(TRANSFER.price) - b(TRANSFER.capital)).toBe(b(TRANSFER.excess));
  });

  it("AC-34: the tie-out explains the M-2 difference, and only M-2 is off", () => {
    expect(b(TIE_OUT.m2Drafted) - b(TIE_OUT.scheduleL)).toBe(b(TIE_OUT.differenceDrafted));
    expect(TALLY_DRAFTED.filter((t) => t.result === "off").map((t) => t.key)).toEqual(["m2Ties"]);
    expect(TALLY_FIXED.some((t) => t.result === "off")).toBe(false);
  });
});

describe("TPL-10 Ridgeline memo", () => {
  it("AC-34: 3,776,500 + 96,400 − 2,641,300 = 1,231,600 → 1,256,200", () => {
    expect(sum([BRIDGE.rents, BRIDGE.parking, BRIDGE.rentalExpenses])).toBe(b(BRIDGE.netRental));
    expect(sum([BRIDGE.netRental, BRIDGE.interest, BRIDGE.taxExempt])).toBe(
      b(BRIDGE.bookNetIncome),
    );
  });

  it("AC-34: depreciation 480,000 + 9,500 + 180,000 + 64,000 = 733,500", () => {
    expect(sum(DEPRECIATION.parts)).toBe(b(DEPRECIATION.total));
  });

  it("AC-34: state shares sum to 1,231,600", () => {
    expect(sum(STATE_SHARES.parts.map((p) => p.amount))).toBe(b(STATE_SHARES.total));
  });
});

describe("TPL-19 Feld binder", () => {
  it("AC-34: 2 to do → 1 to do after the 1095-C upload; 4 received, 1 provided", () => {
    expect(feldCounts()).toEqual({ toDo: 2, received: 4, provided: 1 });
    expect(feldCounts(["aca"]).toDo).toBe(1);
    expect(FELD_OPEN_REQUESTS.map((r) => r.title)[0]).toBe("Form 1095-C From Mercer Hill Health");
  });
});
