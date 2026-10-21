// F-05-T11 (SPEC-048 B1, ADR-078): the independent golden suite for format.ts.
//
// Written from the specification, never from the implementation. Every expected value comes from
//   "04 §3.7"   docs/plan/04-frontend-architecture.md section 3.7 (data formatting)
//   "F-05 B1"   docs/plan/epics/F-05.md section 3.B, story B1
//   "handoff 05" _foundations/design_handoff_foundations/specs/05-data-formatting.md
//   "DECISIONS" packages/ui/src/tokens/DECISIONS.md (the plan wins over the handoff's reference code)
// and each row names its rule in `cite`. Where a row is not in the sources word for word, the cite
// says "inferred" and names the rule it follows from.
//
// Clock: now = 2026-09-14T09:24:00-05:00, firm zone America/Chicago, passed to every formatter that
// takes {now, tz}; the useFormat() cases pin it through ClockProvider.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ClockProvider, useFormat } from "./clock";
import {
  accountMask,
  amount,
  cellRef,
  date,
  dateTime,
  einMask,
  pct,
  progress,
  relative,
  SEP,
  ssnMask,
  time,
  viaAgent,
  type AmountOptions,
  type AmountStyle,
  type Decimal,
  type Instant,
} from "./format";

const NOW = new Date("2026-09-14T09:24:00-05:00");
const CT = "America/Chicago";
const DASH = "—";

// --- Money --------------------------------------------------------------------------------

interface MoneyCase {
  id: string;
  cite: string;
  v: Decimal;
  style: AmountStyle;
  options?: AmountOptions;
  text: string;
  tone: "pos" | "neg" | "zero" | "blank";
}

const MONEY: MoneyCase[] = [
  // Workpaper cells: $ and two decimals.
  {
    id: "M01",
    cite: "handoff 05 §In a workpaper (FIN Bond Index)",
    v: "1462726.47",
    style: "money",
    text: "$1,462,726.47",
    tone: "pos",
  },
  {
    id: "M02",
    cite: "handoff 05 §In a workpaper (Beginning of Year)",
    v: "1342718.20",
    style: "money",
    text: "$1,342,718.20",
    tone: "pos",
  },
  {
    id: "M03",
    cite: "handoff 05 §In a workpaper (Rounding variance)",
    v: "0.06",
    style: "money",
    text: "$0.06",
    tone: "pos",
  },
  {
    id: "M04",
    cite: "handoff 05 §In a workpaper (Total investments)",
    v: "14397480.00",
    style: "money",
    text: "$14,397,480.00",
    tone: "pos",
  },
  {
    id: "M05",
    cite: "04 §3.7 rule 1: $ and 2 decimals on every workpaper cell (integer input gains cents)",
    v: "16861000",
    style: "money",
    text: "$16,861,000.00",
    tone: "pos",
  },
  {
    id: "M06",
    cite: "04 §3.7 rule 1 (one decimal in, two out)",
    v: "1234.5",
    style: "money",
    text: "$1,234.50",
    tone: "pos",
  },
  {
    id: "M07",
    cite: "04 §3.7 rule 1 (thousands separator on the smallest 4-digit value)",
    v: "1000",
    style: "money",
    text: "$1,000.00",
    tone: "pos",
  },
  {
    id: "M08",
    cite: "04 §3.7 rule 1 (no separator below 1,000)",
    v: "999.99",
    style: "money",
    text: "$999.99",
    tone: "pos",
  },
  // Statement tables: whole dollars, no symbol.
  {
    id: "M09",
    cite: "handoff 05 §In a statement (Employer contributions receivable)",
    v: "1379849",
    style: "whole",
    text: "1,379,849",
    tone: "pos",
  },
  {
    id: "M10",
    cite: "handoff 05 §In a statement (Net assets available)",
    v: "18446508",
    style: "whole",
    text: "18,446,508",
    tone: "pos",
  },
  {
    id: "M11",
    cite: "04 §3.7 rule 2: statements are whole dollars, no $ (cents are rounded, not cut)",
    v: "1379849.60",
    style: "whole",
    text: "1,379,850",
    tone: "pos",
  },
  {
    id: "M12",
    cite: "04 §3.7 'Never truncate a number' (carry into a new digit)",
    v: "999999999.999",
    style: "whole",
    text: "1,000,000,000",
    tone: "pos",
  },
  {
    id: "M13",
    cite: "handoff 05 §Formats Statement tables (no symbol, no cents) with 'cents' style (symbol-free two decimals), inferred from AmountStyle in 04 §3.7 API",
    v: "1234.5",
    style: "cents",
    text: "1,234.50",
    tone: "pos",
  },
  // Negatives in parentheses, never a minus sign.
  {
    id: "M14",
    cite: "handoff 05 §In a statement (Excess contributions payable)",
    v: "-6821",
    style: "whole",
    text: "(6,821)",
    tone: "neg",
  },
  {
    id: "M15",
    cite: "handoff 05 §Notes: workpaper negatives follow the same parentheses rule",
    v: "-6821",
    style: "money",
    text: "($6,821.00)",
    tone: "neg",
  },
  {
    id: "M16",
    cite: "04 §3.7 rule 3: negatives in parentheses in every table (cents style)",
    v: "-1234.567",
    style: "cents",
    text: "(1,234.57)",
    tone: "neg",
  },
  {
    id: "M17",
    cite: "handoff 05 §Formats Negative: parentheses, never a minus sign (smallest negative)",
    v: "-0.01",
    style: "money",
    text: "($0.01)",
    tone: "neg",
  },
  // Rounding: half away from zero at cents, exact via bigint.
  {
    id: "M18",
    cite: "F-05 B1 / 04 §3.7: '0.005' -> '$0.01'",
    v: "0.005",
    style: "money",
    text: "$0.01",
    tone: "pos",
  },
  {
    id: "M19",
    cite: "F-05 B1 / 04 §3.7: '-1234567.885' -> '($1,234,567.89)'",
    v: "-1234567.885",
    style: "money",
    text: "($1,234,567.89)",
    tone: "neg",
  },
  {
    id: "M20",
    cite: "04 §3.7 rule 5 half away from zero (mirror of M19)",
    v: "1234567.885",
    style: "money",
    text: "$1,234,567.89",
    tone: "pos",
  },
  {
    id: "M21",
    cite: "04 §3.7 rule 5 half away from zero: '-2.5' -> '(3)'",
    v: "-2.5",
    style: "whole",
    text: "(3)",
    tone: "neg",
  },
  {
    id: "M22",
    cite: "04 §3.7 rule 5 half away from zero (positive mirror of '-2.5')",
    v: "2.5",
    style: "whole",
    text: "3",
    tone: "pos",
  },
  {
    id: "M23",
    cite: "04 §3.7 rule 5 (a half just above zero rounds out to 1)",
    v: "0.5",
    style: "whole",
    text: "1",
    tone: "pos",
  },
  {
    id: "M24",
    cite: "04 §3.7 rule 5 (a negative half rounds out to (1))",
    v: "-0.5",
    style: "whole",
    text: "(1)",
    tone: "neg",
  },
  {
    id: "M25",
    cite: "04 §3.7 rule 5 (1.5 -> 2; an even-biased banker's rounding would also give 2)",
    v: "1.5",
    style: "whole",
    text: "2",
    tone: "pos",
  },
  {
    id: "M26",
    cite: "04 §3.7 rule 5 (3.5 -> 4)",
    v: "3.5",
    style: "whole",
    text: "4",
    tone: "pos",
  },
  {
    id: "M27",
    cite: "04 §3.7 rule 5, banker's-rounding trap (0.125 half cent -> $0.13, not $0.12)",
    v: "0.125",
    style: "money",
    text: "$0.13",
    tone: "pos",
  },
  {
    id: "M28",
    cite: "04 §3.7 rule 5, banker's-rounding trap (0.135 -> $0.14)",
    v: "0.135",
    style: "money",
    text: "$0.14",
    tone: "pos",
  },
  {
    id: "M29",
    cite: "04 §3.7 rule 5, binary-float trap (1.005 is 1.00499.. as a double; exact parse -> $1.01)",
    v: "1.005",
    style: "money",
    text: "$1.01",
    tone: "pos",
  },
  {
    id: "M30",
    cite: "04 §3.7 rule 5 (just under a half rounds down)",
    v: "0.994",
    style: "money",
    text: "$0.99",
    tone: "pos",
  },
  {
    id: "M31",
    cite: "04 §3.7 rule 5 (0.995 rounds up and carries into the dollars)",
    v: "0.995",
    style: "money",
    text: "$1.00",
    tone: "pos",
  },
  {
    id: "M32",
    cite: "04 §3.7 rule 5 (a long tail past the half still rounds up: 0.0050000001)",
    v: "0.0050000001",
    style: "money",
    text: "$0.01",
    tone: "pos",
  },
  {
    id: "M33",
    cite: "04 §3.7 rule 5 (a long tail below the half rounds down to zero: 0.0049999999)",
    v: "0.0049999999",
    style: "money",
    text: DASH,
    tone: "zero",
  },
  {
    id: "M34",
    cite: "04 §3.7 rule 5 (cents style, negative half away from zero)",
    v: "-0.005",
    style: "cents",
    text: "(0.01)",
    tone: "neg",
  },
  {
    id: "M35",
    cite: "04 §3.7 rule 5 (negative half cent, money style)",
    v: "-0.005",
    style: "money",
    text: "($0.01)",
    tone: "neg",
  },
  // Zero and round-to-zero.
  {
    id: "M36",
    cite: "04 §3.7 rule 4: zero renders an em dash (money)",
    v: "0",
    style: "money",
    text: DASH,
    tone: "zero",
  },
  {
    id: "M37",
    cite: "04 §3.7 rule 4: zero renders an em dash (whole)",
    v: "0",
    style: "whole",
    text: DASH,
    tone: "zero",
  },
  {
    id: "M38",
    cite: "handoff 05 §Formats Zero: em dash, never 0.00 (written 0.00)",
    v: "0.00",
    style: "money",
    text: DASH,
    tone: "zero",
  },
  {
    id: "M39",
    cite: "F-05 B1 / 04 §3.7: '-0.004' -> an em dash (rounds to zero)",
    v: "-0.004",
    style: "money",
    text: DASH,
    tone: "zero",
  },
  {
    id: "M40",
    cite: "04 §3.7 rule 4 (positive 0.004 rounds to zero, mirror of M39)",
    v: "0.004",
    style: "money",
    text: DASH,
    tone: "zero",
  },
  {
    id: "M41",
    cite: "04 §3.7 rule 4 (negative zero is zero: no parentheses)",
    v: "-0",
    style: "money",
    text: DASH,
    tone: "zero",
  },
  {
    id: "M42",
    cite: "04 §3.7 rules 4+5 (whole style: 0.49 rounds to zero)",
    v: "0.49",
    style: "whole",
    text: DASH,
    tone: "zero",
  },
  {
    id: "M43",
    cite: "04 §3.7 rules 4+5 (whole style: -0.49 rounds to zero, no parentheses)",
    v: "-0.49",
    style: "whole",
    text: DASH,
    tone: "zero",
  },
  {
    id: "M44",
    cite: "04 §3.7 rule 4: the 'explicit' option prints $0.00 (money)",
    v: "0",
    style: "money",
    options: { zero: "explicit" },
    text: "$0.00",
    tone: "zero",
  },
  {
    id: "M45",
    cite: "04 §3.7 rule 4 explicit, whole style prints 0 (inferred: explicit zero in the style's own shape)",
    v: "0",
    style: "whole",
    options: { zero: "explicit" },
    text: "0",
    tone: "zero",
  },
  {
    id: "M46",
    cite: "04 §3.7 rule 4 explicit, cents style prints 0.00 (inferred as M45)",
    v: "0",
    style: "cents",
    options: { zero: "explicit" },
    text: "0.00",
    tone: "zero",
  },
  {
    id: "M47",
    cite: "04 §3.7 rules 4+5 explicit: a value that rounds to zero is $0.00 with the zero tone, not '($0.00)'",
    v: "-0.004",
    style: "money",
    options: { zero: "explicit" },
    text: "$0.00",
    tone: "zero",
  },
  {
    id: "M48",
    cite: "04 §3.7 rule 4: a non-zero amount is unaffected by the explicit option",
    v: "12.30",
    style: "money",
    options: { zero: "explicit" },
    text: "$12.30",
    tone: "pos",
  },
  // Large values: exact through scaled bigint.
  {
    id: "M49",
    cite: "04 §3.7 test list: 15-digit values (15 integer digits)",
    v: "123456789012345.67",
    style: "money",
    text: "$123,456,789,012,345.67",
    tone: "pos",
  },
  {
    id: "M50",
    cite: "04 §3.7 Input: never through Number() (17 digits is past 2^53)",
    v: "12345678901234567.89",
    style: "money",
    text: "$12,345,678,901,234,567.89",
    tone: "pos",
  },
  {
    id: "M51",
    cite: "04 §3.7 Input + F-05 B1 (negative 15-digit value)",
    v: "-999999999999999.99",
    style: "money",
    text: "($999,999,999,999,999.99)",
    tone: "neg",
  },
  {
    id: "M52",
    cite: "04 §3.7 rule 5 on a large value (carry through every digit)",
    v: "99999999999999999.995",
    style: "money",
    text: "$100,000,000,000,000,000.00",
    tone: "pos",
  },
  {
    id: "M53",
    cite: "04 §3.7 Input: bigint accepted (whole dollars, 19 digits)",
    v: 9007199254740993n,
    style: "whole",
    text: "9,007,199,254,740,993",
    tone: "pos",
  },
  // Other accepted inputs.
  {
    id: "M54",
    cite: "04 §3.7 Input: number accepted",
    v: 1234.5,
    style: "money",
    text: "$1,234.50",
    tone: "pos",
  },
  {
    id: "M55",
    cite: "04 §3.7 Input: number 0.1+0.2 (0.30000000000000004) is read as the cent amount",
    v: 0.1 + 0.2,
    style: "money",
    text: "$0.30",
    tone: "pos",
  },
  {
    id: "M56",
    cite: "04 §3.7 rule 5 with a number input, '-2.5' -> '(3)'",
    v: -2.5,
    style: "whole",
    text: "(3)",
    tone: "neg",
  },
  {
    id: "M57",
    cite: "04 §3.7 Input: bigint zero is zero",
    v: 0n,
    style: "money",
    text: DASH,
    tone: "zero",
  },
  {
    id: "M58",
    cite: "04 §3.7 Input: null -> tone 'blank'",
    v: null,
    style: "money",
    text: DASH,
    tone: "blank",
  },
  {
    id: "M59",
    cite: "04 §3.7 Input: undefined -> tone 'blank'",
    v: undefined,
    style: "whole",
    text: DASH,
    tone: "blank",
  },
  {
    id: "M60",
    cite: "04 §3.7 Input: decimal string with an explicit plus and padded zeros reads exactly",
    v: "+0012.340",
    style: "money",
    text: "$12.34",
    tone: "pos",
  },
];

describe("amount() golden cases (04 §3.7 money rules)", () => {
  for (const c of MONEY) {
    it(`${c.id} ${String(c.v)} ${c.style}${c.options ? " explicit" : ""} -> ${c.text} [${c.cite}]`, () => {
      const got = amount(c.v, c.style, c.options);
      // A blank value has no number to show; its contract is the tone (04 §3.7 API).
      if (c.tone !== "blank") expect(got.text).toBe(c.text);
      expect(got.tone).toBe(c.tone);
    });
  }

  it("M61 invalid input never renders as a number [04 §3.7 Input: parsed exactly, never through Number()]", () => {
    for (const bad of ["abc", "12abc", "1,234.50", "$5", "1.2.3", "NaN", "Infinity"]) {
      let out: string | undefined;
      try {
        out = amount(bad).text;
      } catch {
        out = undefined; // refusing is allowed
      }
      if (out !== undefined) expect(out).not.toMatch(/\d/);
    }
    for (const bad of [Number.NaN, Number.POSITIVE_INFINITY]) {
      let out: string | undefined;
      try {
        out = amount(bad).text;
      } catch {
        out = undefined;
      }
      if (out !== undefined) expect(out).not.toMatch(/\d/);
    }
  });
});

// --- Percent and progress ----------------------------------------------------------------

interface PctCase {
  id: string;
  cite: string;
  run: () => string;
  want: string;
}

const PCT: PctCase[] = [
  {
    id: "P01",
    cite: "04 §3.7 rule 'Percent drops a trailing .0': 0.06 -> 6%",
    run: () => pct("0.06"),
    want: "6%",
  },
  { id: "P02", cite: "04 §3.7 percent example 2.5%", run: () => pct("0.025"), want: "2.5%" },
  { id: "P03", cite: "04 §3.7 percent: 50% not 50.0%", run: () => pct("0.5"), want: "50%" },
  { id: "P04", cite: "04 §3.7 percent: 100% not 100.0%", run: () => pct("1"), want: "100%" },
  {
    id: "P05",
    cite: "04 §3.7 percent: one decimal kept when non-zero (17.5%)",
    run: () => pct("0.175"),
    want: "17.5%",
  },
  { id: "P06", cite: "04 §3.7 percent: 0.1 -> 10%", run: () => pct("0.1"), want: "10%" },
  {
    id: "P07",
    cite: "F-05 B1: percent drops a trailing .0 after rounding (0.0601 -> 6%, not 6.0%)",
    run: () => pct("0.0601"),
    want: "6%",
  },
  {
    id: "P08",
    cite: "04 §3.7 rule 3: negatives in parentheses in every table (percent)",
    run: () => pct("-0.025"),
    want: "(2.5%)",
  },
  { id: "P09", cite: "04 §3.7 percent with a number input", run: () => pct(0.06), want: "6%" },
  {
    id: "P10",
    cite: "handoff 05 §Formats Ratio: 17% (4 / 24), whole percent, spaced slash",
    run: () => progress(4, 24),
    want: "17% (4 / 24)",
  },
  {
    id: "P11",
    cite: "handoff 05 §Formats Ratio (done over total, 2/3 rounds to 67%)",
    run: () => progress(2, 3),
    want: "67% (2 / 3)",
  },
  {
    id: "P12",
    cite: "handoff 05 §Formats Ratio (all done)",
    run: () => progress(24, 24),
    want: "100% (24 / 24)",
  },
  {
    id: "P13",
    cite: "handoff 05 §Formats Ratio (none done)",
    run: () => progress(0, 24),
    want: "0% (0 / 24)",
  },
  {
    id: "P14",
    cite: "04 §3.7 rule 5 half away from zero on the ratio (1/8 = 12.5% -> 13%)",
    run: () => progress(1, 8),
    want: "13% (1 / 8)",
  },
];

describe("pct() and progress() golden cases", () => {
  for (const c of PCT)
    it(`${c.id} -> ${c.want} [${c.cite}]`, () => {
      expect(c.run()).toBe(c.want);
    });
});

// --- Masks, references, separators --------------------------------------------------------

const TEXT: PctCase[] = [
  {
    id: "X01",
    cite: "handoff 05 §Formats Account mask",
    run: () => accountMask("Operating Checking", "Front Range Bank", "4410"),
    want: "Operating Checking (Front Range Bank) ••4410",
  },
  {
    id: "X02",
    cite: "handoff 05 §Formats Tax ID mask: •••-••-4417",
    run: () => ssnMask("4417"),
    want: "•••-••-4417",
  },
  {
    id: "X03",
    cite: "handoff 05 §Formats Cell reference: sheet, bang, cell",
    run: () => cellRef("03 Liabilities", "C29"),
    want: "03 Liabilities!C29",
  },
  {
    id: "X04",
    cite: "AGENTS.md non-negotiable 18: attributed '<person> via Agent'",
    run: () => viaAgent("Hannah Leclerc"),
    want: "Hannah Leclerc via Agent",
  },
  {
    id: "X05",
    cite: "04 §3.7 API SEP (meta line 'Raised by Hannah Leclerc · Aug 7')",
    run: () => `Raised by Hannah Leclerc${SEP}Aug 7`,
    want: "Raised by Hannah Leclerc · Aug 7",
  },
];

describe("masks, cellRef, viaAgent, SEP", () => {
  for (const c of TEXT)
    it(`${c.id} [${c.cite}]`, () => {
      expect(c.run()).toBe(c.want);
    });

  it("X06 ssnMask refuses more than the last four [F-05 B1 / 04 §3.7: accept last-4 only]", () => {
    expect(() => ssnMask("900-45-4417")).toThrow();
    expect(() => ssnMask("900454417")).toThrow();
  });
  it("X07 einMask refuses more than the last four [F-05 B1 / ADR-031]", () => {
    expect(() => einMask("12-3454417")).toThrow();
    expect(() => einMask("900454417")).toThrow();
  });
  it("X08 accountMask refuses a full account number [F-05 B1 / ADR-031]", () => {
    expect(() => accountMask("Operating Checking", "Front Range Bank", "000123454410")).toThrow();
  });
  it("X09 a mask never echoes the digits it was not given [F-05 B1 / ADR-031]", () => {
    expect(ssnMask("4417")).not.toMatch(/\d{5}/);
    expect(einMask("4417").replace(/\D/g, "")).toBe("4417");
  });
});

// --- Dates, times, date-times, relative ---------------------------------------------------

interface DateCase {
  id: string;
  cite: string;
  run: () => string;
  want: string;
}

const d = (v: Instant, o: { withYear?: boolean; tz?: string; now?: Date | number } = {}): string =>
  date(v, {
    now: o.now ?? NOW,
    tz: o.tz ?? CT,
    ...(o.withYear === undefined ? {} : { withYear: o.withYear }),
  });
const t = (v: Instant, o: { zone?: boolean; seconds?: boolean; tz?: string } = {}): string =>
  time(v, {
    tz: o.tz ?? CT,
    ...(o.zone === undefined ? {} : { zone: o.zone }),
    ...(o.seconds === undefined ? {} : { seconds: o.seconds }),
  });
const dt = (v: Instant, o: { zone?: boolean; tz?: string } = {}): string =>
  dateTime(v, { tz: o.tz ?? CT, ...(o.zone === undefined ? {} : { zone: o.zone }) });
const rel = (v: Instant, now: Date | number = NOW, tz: string = CT): string =>
  relative(v, { now, tz });

const DATES: DateCase[] = [
  // Date: "Aug 7", year only outside the current year or on due dates.
  {
    id: "D01",
    cite: "04 §3.7 Dates 'Aug 7'; handoff 05 §Formats Dates",
    run: () => d("2026-08-07"),
    want: "Aug 7",
  },
  {
    id: "D02",
    cite: "04 §3.7 'Jul 5, 2026': due dates always carry the year",
    run: () => d("2026-07-05", { withYear: true }),
    want: "Jul 5, 2026",
  },
  {
    id: "D03",
    cite: "handoff 05 §Formats Dates: year outside the current year (previous year)",
    run: () => d("2025-12-31"),
    want: "Dec 31, 2025",
  },
  {
    id: "D04",
    cite: "handoff 05 §Formats Dates: year outside the current year (next year)",
    run: () => d("2027-01-01"),
    want: "Jan 1, 2027",
  },
  {
    id: "D05",
    cite: "handoff 05 §Formats Dates: no leading zero",
    run: () => d("2026-03-05"),
    want: "Mar 5",
  },
  {
    id: "D06",
    cite: "handoff 05 §Formats Dates: short month (September is 'Sep')",
    run: () => d("2026-09-05"),
    want: "Sep 5",
  },
  {
    id: "D07",
    cite: "handoff 05 §Formats Dates: short month (June is 'Jun')",
    run: () => d("2026-06-01"),
    want: "Jun 1",
  },
  {
    id: "D08",
    cite: "handoff 05 §Formats Dates: short month (the four-letter trap, July)",
    run: () => d("2026-07-04"),
    want: "Jul 4",
  },
  {
    id: "D09",
    cite: "handoff 05 §Formats Dates: December, two-digit day",
    run: () => d("2026-12-25"),
    want: "Dec 25",
  },
  {
    id: "D10",
    cite: "04 §3.7 due dates always carry the year, even in the current year",
    run: () => d("2026-09-15", { withYear: true }),
    want: "Sep 15, 2026",
  },
  { id: "D11", cite: "04 §3.7 Input: null -> an em dash", run: () => d(null), want: DASH },
  {
    id: "D12",
    cite: "04 §3.7 Input: undefined -> an em dash",
    run: () => d(undefined),
    want: DASH,
  },
  // Firm zone, not the device or UTC zone.
  {
    id: "D13",
    cite: "DECISIONS 2026-10-21 firm-zone dates: 03:00Z on Aug 7 is Aug 6 in Chicago",
    run: () => d("2026-08-07T03:00:00Z"),
    want: "Aug 6",
  },
  {
    id: "D14",
    cite: "DECISIONS firm-zone dates: 05:00Z is local midnight CDT, so Aug 7",
    run: () => d("2026-08-07T05:00:00Z"),
    want: "Aug 7",
  },
  {
    id: "D15",
    cite: "DECISIONS firm-zone dates: 04:59Z is 23:59 CDT the day before",
    run: () => d("2026-08-07T04:59:00Z"),
    want: "Aug 6",
  },
  {
    id: "D16",
    cite: "DECISIONS firm-zone dates + year rule: New Year in UTC is still last year in Chicago",
    run: () => d("2026-01-01T03:00:00Z"),
    want: "Dec 31, 2025",
  },
  {
    id: "D17",
    cite: "DECISIONS firm-zone dates: 06:00Z on Jan 1 is local midnight CST, current year, no year printed",
    run: () => d("2026-01-01T06:00:00Z"),
    want: "Jan 1",
  },
  {
    id: "D18",
    cite: "04 §3.7 {now, tz}: the 'current year' is the firm-zone year of now (Dec 31 21:00 CST is still 2026)",
    run: () => d("2026-12-31", { now: new Date("2027-01-01T03:00:00Z") }),
    want: "Dec 31",
  },
  {
    id: "D19",
    cite: "04 §3.7 {now, tz}: the year is outside 'now' once the firm zone crosses New Year",
    run: () => d("2026-12-31", { now: new Date("2027-01-01T06:00:00Z") }),
    want: "Dec 31, 2026",
  },
  {
    id: "D20",
    cite: "04 §3.7 {now, tz}: tz option, New York is ahead of Chicago (04:30Z -> 00:30 EDT)",
    run: () => d("2026-09-14T04:30:00Z", { tz: "America/New_York" }),
    want: "Sep 14",
  },
  {
    id: "D21",
    cite: "04 §3.7 {now, tz}: same instant in Chicago is the previous evening",
    run: () => d("2026-09-14T04:30:00Z"),
    want: "Sep 13",
  },
  {
    id: "D22",
    cite: "04 §3.7 {now, tz}: tz option, Tokyo",
    run: () => d("2026-08-07T15:30:00Z", { tz: "Asia/Tokyo" }),
    want: "Aug 8",
  },
  {
    id: "D23",
    cite: "04 §3.7 Input: an offset timestamp is read at its own instant (-05:00 midnight is 05:00Z)",
    run: () => d("2026-08-07T00:00:00-05:00"),
    want: "Aug 7",
  },
  {
    id: "D24",
    cite: "04 §3.7 Input: a number is epoch milliseconds (2026-09-14T14:24Z)",
    run: () => d(Date.UTC(2026, 8, 14, 14, 24)),
    want: "Sep 14",
  },
  {
    id: "D25",
    cite: "04 §3.7 Input: a Date object",
    run: () => d(new Date("2026-02-28T20:00:00Z")),
    want: "Feb 28",
  },
  // Time: "9:21 AM", 12-hour clock in the firm zone.
  {
    id: "T01",
    cite: "handoff 05 §Formats List-relative: 9:21 AM",
    run: () => t("2026-09-14T14:21:00Z"),
    want: "9:21 AM",
  },
  {
    id: "T02",
    cite: "handoff 05 §Formats: 12-hour clock, no leading zero (1:05 PM)",
    run: () => t("2026-09-14T18:05:00Z"),
    want: "1:05 PM",
  },
  {
    id: "T03",
    cite: "handoff 05 §Formats: noon is 12:00 PM",
    run: () => t("2026-09-14T17:00:00Z"),
    want: "12:00 PM",
  },
  {
    id: "T04",
    cite: "handoff 05 §Formats: midnight is 12:00 AM",
    run: () => t("2026-09-14T05:00:00Z"),
    want: "12:00 AM",
  },
  {
    id: "T05",
    cite: "handoff 05 §Formats: 11:59 PM",
    run: () => t("2026-09-15T04:59:00Z"),
    want: "11:59 PM",
  },
  {
    id: "T06",
    cite: "04 §3.7 time-zone labels from Intl shortGeneric: Chicago is CT",
    run: () => t("2026-09-14T14:00:00Z", { zone: true }),
    want: "9:00 AM CT",
  },
  {
    id: "T07",
    cite: "04 §3.7 shortGeneric does not switch to CST in winter",
    run: () => t("2026-12-01T15:00:00Z", { zone: true }),
    want: "9:00 AM CT",
  },
  {
    id: "T08",
    cite: "04 §3.7 '9:00 AM ET': New York is ET",
    run: () => t("2026-09-14T13:00:00Z", { zone: true, tz: "America/New_York" }),
    want: "9:00 AM ET",
  },
  {
    id: "T09",
    cite: "04 §3.7 shortGeneric: Denver is MT",
    run: () => t("2026-09-14T15:00:00Z", { zone: true, tz: "America/Denver" }),
    want: "9:00 AM MT",
  },
  {
    id: "T10",
    cite: "TimeOptions.seconds (audit trail): 9:24:07 AM",
    run: () => t("2026-09-14T14:24:07Z", { seconds: true }),
    want: "9:24:07 AM",
  },
  {
    id: "T11",
    cite: "inferred from 04 §3.7 date/time inputs: a calendar date has no time, so an em dash",
    run: () => t("2026-09-14"),
    want: DASH,
  },
  { id: "T12", cite: "04 §3.7 Input: null time -> an em dash", run: () => t(null), want: DASH },
  // Date-time: "May 11, 2026 11:03 AM".
  {
    id: "DT01",
    cite: "handoff 05 §Formats Dates: May 11, 2026 11:03 AM",
    run: () => dt("2026-05-11T16:03:00Z"),
    want: "May 11, 2026 11:03 AM",
  },
  {
    id: "DT02",
    cite: "handoff 05 §Formats: a timestamp carries its year even in the current year",
    run: () => dt("2026-09-14T14:24:00Z"),
    want: "Sep 14, 2026 9:24 AM",
  },
  {
    id: "DT03",
    cite: "handoff 05 §Formats + DECISIONS firm zone: a UTC evening is the firm's afternoon of that day, year intact",
    run: () => dt("2025-12-31T23:30:00Z"),
    want: "Dec 31, 2025 5:30 PM",
  },
  {
    id: "DT04",
    cite: "DECISIONS firm zone: 03:00Z January 1 is still last year in Chicago",
    run: () => dt("2026-01-01T03:00:00Z"),
    want: "Dec 31, 2025 9:00 PM",
  },
  {
    id: "DT05",
    cite: "04 §3.7 shortGeneric label on a date-time",
    run: () => dt("2026-05-11T16:03:00Z", { zone: true }),
    want: "May 11, 2026 11:03 AM CT",
  },
  {
    id: "DT06",
    cite: "04 §3.7 Input: null date-time -> an em dash",
    run: () => dt(null),
    want: DASH,
  },
  // Relative dates at now = 2026-09-14T09:24:00-05:00, Chicago.
  {
    id: "R01",
    cite: "handoff 05 §Formats List-relative: today shows the time (9:21 AM)",
    run: () => rel("2026-09-14T14:21:00Z"),
    want: "9:21 AM",
  },
  {
    id: "R02",
    cite: "handoff 05 §Formats: today shows the time, even at local midnight (12:00 AM)",
    run: () => rel("2026-09-14T05:00:00Z"),
    want: "12:00 AM",
  },
  {
    id: "R03",
    cite: "04 §3.7 'Yesterday' across midnight: 23:59 CDT the day before, 9h25m ago",
    run: () => rel("2026-09-14T04:59:00Z"),
    want: "Yesterday",
  },
  {
    id: "R04",
    cite: "04 §3.7 'Yesterday' across midnight: 22:00 CDT Sep 13 is already Sep 14 in UTC",
    run: () => rel("2026-09-14T03:00:00Z"),
    want: "Yesterday",
  },
  {
    id: "R05",
    cite: "04 §3.7 'Yesterday': the first minute of the day before",
    run: () => rel("2026-09-13T05:00:00Z"),
    want: "Yesterday",
  },
  {
    id: "R06",
    cite: "04 §3.7 'Yesterday' across midnight: 33h ago is '2 Days Ago' because Sep 12 is two calendar days back",
    run: () => rel("2026-09-13T04:59:00Z"),
    want: "2 Days Ago",
  },
  {
    id: "R07",
    cite: "handoff 05 §Formats / 04 §3.7 Title Case: 2 Days Ago",
    run: () => rel("2026-09-12T17:00:00Z"),
    want: "2 Days Ago",
  },
  {
    id: "R08",
    cite: "04 §3.7 Title Case: 3 Days Ago",
    run: () => rel("2026-09-11T17:00:00Z"),
    want: "3 Days Ago",
  },
  {
    id: "R09",
    cite: "handoff 05 §Notes: older than the relative window falls back to a short date",
    run: () => rel("2026-08-07T17:00:00Z"),
    want: "Aug 7",
  },
  {
    id: "R10",
    cite: "handoff 05 §Formats Dates + R09: a date in a previous year carries the year",
    run: () => rel("2025-12-31T18:00:00Z"),
    want: "Dec 31, 2025",
  },
  { id: "R11", cite: "04 §3.7 Input: null -> an em dash", run: () => rel(null), want: DASH },
  {
    id: "R12",
    cite: "inferred from 04 §3.7 date inputs: a calendar date of today reads 'Today'",
    run: () => rel("2026-09-14"),
    want: "Today",
  },
  {
    id: "R13",
    cite: "inferred: a calendar date is read as written; the day before is 'Yesterday'",
    run: () => rel("2026-09-13"),
    want: "Yesterday",
  },
  {
    id: "R14",
    cite: "inferred: a calendar date two days back is '2 Days Ago'",
    run: () => rel("2026-09-12"),
    want: "2 Days Ago",
  },
  {
    id: "R15",
    cite: "04 §3.7 'Yesterday' across midnight: 10 minutes ago is Yesterday when now is 00:05",
    run: () => rel("2026-09-14T23:50:00-05:00", new Date("2026-09-15T00:05:00-05:00")),
    want: "Yesterday",
  },
  {
    id: "R16",
    cite: "04 §3.7 today shows the time: 00:01 when now is 23:59 the same day",
    run: () => rel("2026-09-14T00:01:00-05:00", new Date("2026-09-14T23:59:00-05:00")),
    want: "12:01 AM",
  },
  {
    id: "R17",
    cite: "04 §3.7 {now, tz}: now as epoch milliseconds",
    run: () => rel("2026-09-13T20:00:00-05:00", NOW.getTime()),
    want: "Yesterday",
  },
  {
    id: "R18",
    cite: "04 §3.7 {now, tz}: Tokyo's calendar says today (Sep 14 00:30 JST)",
    run: () => rel("2026-09-13T15:30:00Z", NOW, "Asia/Tokyo"),
    want: "12:30 AM",
  },
  {
    id: "R19",
    cite: "04 §3.7 {now, tz}: the same instant on Chicago's calendar is Yesterday",
    run: () => rel("2026-09-13T15:30:00Z"),
    want: "Yesterday",
  },
  {
    id: "R20",
    cite: "04 §3.7 {now, tz}: the cut-over year is the firm-zone year of now (Dec 31 2026 vs Jan 1 2027)",
    run: () => rel("2026-06-01T17:00:00Z", new Date("2027-01-02T18:00:00Z")),
    want: "Jun 1, 2026",
  },
  // The Nov 1 2026 DST change: America/Chicago falls back 02:00 CDT -> 01:00 CST at 07:00Z.
  {
    id: "S01",
    cite: "DST Nov 1 2026: 06:30Z is 1:30 AM CDT (first pass)",
    run: () => t("2026-11-01T06:30:00Z"),
    want: "1:30 AM",
  },
  {
    id: "S02",
    cite: "DST Nov 1 2026: 07:30Z is 1:30 AM CST (repeated hour)",
    run: () => t("2026-11-01T07:30:00Z"),
    want: "1:30 AM",
  },
  {
    id: "S03",
    cite: "DST Nov 1 2026: the label is shortGeneric CT in both passes of 1:30 (first)",
    run: () => t("2026-11-01T06:30:00Z", { zone: true }),
    want: "1:30 AM CT",
  },
  {
    id: "S04",
    cite: "DST Nov 1 2026: the label is shortGeneric CT in both passes of 1:30 (second)",
    run: () => t("2026-11-01T07:30:00Z", { zone: true }),
    want: "1:30 AM CT",
  },
  {
    id: "S05",
    cite: "DST Nov 1 2026: 08:00Z is 2:00 AM CST",
    run: () => t("2026-11-01T08:00:00Z"),
    want: "2:00 AM",
  },
  {
    id: "S06",
    cite: "DST Nov 1 2026: 05:59Z is 12:59 AM CDT, just before the repeated hour",
    run: () => t("2026-11-01T05:59:00Z"),
    want: "12:59 AM",
  },
  {
    id: "S07",
    cite: "DST Nov 1 2026: 06:59:59Z is the last second of CDT, 1:59:59 AM",
    run: () => t("2026-11-01T06:59:59Z", { seconds: true }),
    want: "1:59:59 AM",
  },
  {
    id: "S08",
    cite: "DST Nov 1 2026: 07:00:00Z is the first second of CST, 1:00:00 AM again",
    run: () => t("2026-11-01T07:00:00Z", { seconds: true }),
    want: "1:00:00 AM",
  },
  {
    id: "S09",
    cite: "DST Nov 1 2026: local midnight CDT is Nov 1",
    run: () => d("2026-11-01T05:00:00Z"),
    want: "Nov 1",
  },
  {
    id: "S10",
    cite: "DST Nov 1 2026: 23:59 CDT Oct 31 is Oct 31",
    run: () => d("2026-11-01T04:59:00Z"),
    want: "Oct 31",
  },
  {
    id: "S11",
    cite: "DST Nov 1 2026: Nov 1 lasts 25 hours; 23:59 CST is still Nov 1",
    run: () => d("2026-11-02T05:59:00Z"),
    want: "Nov 1",
  },
  {
    id: "S12",
    cite: "DST Nov 1 2026: 06:00Z Nov 2 is local midnight CST, Nov 2",
    run: () => d("2026-11-02T06:00:00Z"),
    want: "Nov 2",
  },
  {
    id: "S13",
    cite: "DST Nov 1 2026: date-time in the repeated hour, first pass",
    run: () => dt("2026-11-01T06:30:00Z"),
    want: "Nov 1, 2026 1:30 AM",
  },
  {
    id: "S14",
    cite: "DST Nov 1 2026: date-time in the repeated hour, second pass",
    run: () => dt("2026-11-01T07:30:00Z"),
    want: "Nov 1, 2026 1:30 AM",
  },
  {
    id: "S15",
    cite: "DST Nov 1 2026 + 'Yesterday': now 00:30 CST Nov 2, event 23:30 CDT Oct 31 is 26h ago but two calendar days back",
    run: () => rel("2026-11-01T04:30:00Z", new Date("2026-11-02T06:30:00Z")),
    want: "2 Days Ago",
  },
  {
    id: "S16",
    cite: "DST Nov 1 2026 + 'Yesterday': now 23:30 CST Nov 1, event 00:00 CDT Nov 1 is 24.5h ago but the same calendar day",
    run: () => rel("2026-11-01T05:00:00Z", new Date("2026-11-02T05:30:00Z")),
    want: "12:00 AM",
  },
  {
    id: "S17",
    cite: "DST Nov 1 2026 + 'Yesterday': Nov 1 noon seen from Nov 2 10:00 CST",
    run: () => rel("2026-11-01T18:00:00Z", new Date("2026-11-02T16:00:00Z")),
    want: "Yesterday",
  },
  {
    id: "S18",
    cite: "DST Nov 1 2026: on the day itself, 1:30 AM CDT is a time (now is noon CST)",
    run: () => rel("2026-11-01T06:30:00Z", new Date("2026-11-01T18:00:00Z")),
    want: "1:30 AM",
  },
  {
    id: "S19",
    cite: "DST Nov 1 2026: on the day itself, noon the day before is Yesterday",
    run: () => rel("2026-10-31T17:00:00Z", new Date("2026-11-01T18:00:00Z")),
    want: "Yesterday",
  },
  {
    id: "S20",
    cite: "DST Nov 1 2026: a calendar date across the change (Nov 2 seen from Nov 3)",
    run: () => rel("2026-11-02", new Date("2026-11-03T16:00:00Z")),
    want: "Yesterday",
  },
  // Spring forward Mar 14 2027: 02:00 CST -> 03:00 CDT at 08:00Z (the other DST edge).
  {
    id: "S21",
    cite: "DST Mar 14 2027: 07:59Z is 1:59 AM CST",
    run: () => t("2027-03-14T07:59:00Z"),
    want: "1:59 AM",
  },
  {
    id: "S22",
    cite: "DST Mar 14 2027: 08:00Z is 3:00 AM CDT (2:xx never occurs)",
    run: () => t("2027-03-14T08:00:00Z"),
    want: "3:00 AM",
  },
];

describe("date, time, dateTime and relative golden cases (now = 2026-09-14T09:24-05:00, America/Chicago)", () => {
  for (const c of DATES)
    it(`${c.id} -> ${c.want} [${c.cite}]`, () => {
      expect(c.run()).toBe(c.want);
    });
});

// --- Bound to the clock -------------------------------------------------------------------

describe("useFormat() pins the same clock (04 §3.7: date/relative take {now, tz} from useNow())", () => {
  function Probe(): ReturnType<typeof createElement> {
    const f = useFormat();
    return createElement(
      "p",
      null,
      [
        f.relative("2026-09-14T03:00:00Z"),
        f.relative("2026-09-14T14:21:00Z"),
        f.date("2026-08-07"),
        f.date("2026-07-05", { withYear: true }),
        f.dateTime("2026-05-11T16:03:00Z"),
      ].join("|"),
    );
  }

  it("B01 the bound formatters give the golden strings at the pinned business time", () => {
    const html = renderToStaticMarkup(
      createElement(ClockProvider, { now: () => NOW, tz: CT, children: createElement(Probe) }),
    );
    expect(html).toBe("<p>Yesterday|9:21 AM|Aug 7|Jul 5, 2026|May 11, 2026 11:03 AM</p>");
  });

  it("B02 the zone comes from the provider: Tokyo's calendar turns Yesterday into a time", () => {
    const html = renderToStaticMarkup(
      createElement(ClockProvider, {
        now: () => NOW,
        tz: "Asia/Tokyo",
        children: createElement(Probe),
      }),
    );
    expect(html.startsWith("<p>12:00 PM|")).toBe(true);
  });
});
