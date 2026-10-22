import { describe, expect, it } from "vitest";
import {
  DASH,
  accountMask,
  amount,
  bytes,
  cellRef,
  count,
  date,
  dateTime,
  einMask,
  isoDate,
  longDate,
  monthYear,
  parseDecimal,
  pct,
  period,
  progress,
  prose,
  ratio,
  relative,
  since,
  ssnMask,
  time,
  viaAgent,
  sameDay,
  weekdayDate,
  zoneName,
} from "./format";

// Unit tests for format.ts's own rules (F-05-T10). The independent golden suite is F-05-T11.
const NOW = new Date("2026-09-14T09:24:00-05:00"); // Monday, 9:24 AM in Chicago
const CHI = { now: NOW, tz: "America/Chicago" };

describe("parseDecimal", () => {
  it("is exact past 15 digits", () => {
    expect(parseDecimal("123456789012345.678")).toEqual({ units: 123456789012345678n, scale: 3 });
  });
  it("reads signs, bare fractions, exponents, numbers and bigints", () => {
    expect(parseDecimal("+1.50")).toEqual({ units: 150n, scale: 2 });
    expect(parseDecimal("-.5")).toEqual({ units: -5n, scale: 1 });
    expect(parseDecimal("1e3")).toEqual({ units: 1000n, scale: 0 });
    expect(parseDecimal("12.5e-1")).toEqual({ units: 125n, scale: 2 });
    expect(parseDecimal(0.1)).toEqual({ units: 1n, scale: 1 });
    expect(parseDecimal(1e-7)).toEqual({ units: 1n, scale: 7 });
    expect(parseDecimal(12n)).toEqual({ units: 12n, scale: 0 });
  });
  it("refuses anything that is not a decimal", () => {
    for (const bad of ["", "abc", "1,234.00", "1.2.3", ".", "-", "1e999999", NaN, Infinity]) {
      expect(() => parseDecimal(bad)).toThrow(RangeError);
    }
  });
});

describe("amount", () => {
  it("holds the golden examples", () => {
    expect(amount("-0.004").text).toBe("—");
    expect(amount("0.005").text).toBe("$0.01");
    expect(amount("-1234567.885").text).toBe("($1,234,567.89)");
  });
  it("rounds half away from zero", () => {
    expect(amount("-2.5", "whole").text).toBe("(3)");
    expect(amount("2.5", "whole").text).toBe("3");
    expect(amount("0.5", "whole").text).toBe("1");
    expect(amount("-0.5", "whole").text).toBe("(1)");
    expect(amount("1.004", "cents").text).toBe("1.00");
    expect(amount("1.005", "cents").text).toBe("1.01");
    expect(amount("-1.005", "cents").text).toBe("(1.01)");
    expect(amount("2.675", "money").text).toBe("$2.68"); // a float gives 2.67
  });
  it("never goes through a float", () => {
    expect(amount("123456789012345.675").text).toBe("$123,456,789,012,345.68");
    expect(amount("9007199254740993.01").text).toBe("$9,007,199,254,740,993.01");
    expect(amount("-99999999999999999.995", "money").text).toBe("($100,000,000,000,000,000.00)");
  });
  it("styles: money, cents, whole", () => {
    expect(amount("1462726.47").text).toBe("$1,462,726.47");
    expect(amount("1462726.47", "cents").text).toBe("1,462,726.47");
    expect(amount("1379849", "whole").text).toBe("1,379,849");
    expect(amount("1250.1", "money").text).toBe("$1,250.10");
    expect(amount("1250", "cents").text).toBe("1,250.00");
    expect(amount(1379849.4, "whole").text).toBe("1,379,849");
    expect(amount(1500000n, "whole").text).toBe("1,500,000");
  });
  it("puts negatives in parentheses and never uses a minus sign", () => {
    expect(amount("-6821", "whole")).toEqual({ text: "(6,821)", tone: "neg" });
    expect(amount("-6821", "money")).toEqual({ text: "($6,821.00)", tone: "neg" });
    expect(amount("-0.99", "money").text).toBe("($0.99)");
  });
  it("tones: pos, neg, zero, blank", () => {
    expect(amount("5").tone).toBe("pos");
    expect(amount("-5").tone).toBe("neg");
    expect(amount("0.00").tone).toBe("zero");
    expect(amount("-0.004").tone).toBe("zero"); // zero after rounding is not negative
    expect(amount("0.4", "whole").tone).toBe("zero");
    expect(amount(null)).toEqual({ text: DASH, tone: "blank" });
    expect(amount(undefined).tone).toBe("blank");
    expect(amount("  ").tone).toBe("blank");
  });
  it("prints zero as an em dash unless asked", () => {
    expect(amount("0", "money").text).toBe("—");
    expect(amount("0", "money", { zero: "explicit" }).text).toBe("$0.00");
    expect(amount("0", "cents", { zero: "explicit" }).text).toBe("0.00");
    expect(amount("-0.004", "whole", { zero: "explicit" })).toEqual({ text: "0", tone: "zero" });
  });
  it("throws on a malformed value rather than printing it", () => {
    expect(() => amount("12,000.00")).toThrow(RangeError);
  });
});

describe("prose, count, ratio, pct", () => {
  it("writes money in a sentence with a minus sign and a written-out zero", () => {
    expect(prose("-1234.5")).toBe("-$1,234.50");
    expect(prose("0")).toBe("$0.00");
    expect(prose("-0.004")).toBe("$0.00");
    expect(prose("1234.5", "cents")).toBe("1,234.50");
    expect(prose(null)).toBe("—");
  });
  it("counts with separators", () => {
    expect(count(1204)).toBe("1,204");
    expect(count("0")).toBe("0");
    expect(count("1234567")).toBe("1,234,567");
    expect(count(undefined)).toBe("—");
  });
  it("ratio is a fixed-decimal score", () => {
    expect(ratio(0.855)).toBe("0.86");
    expect(ratio("0.5")).toBe("0.50");
    expect(ratio("3", 0)).toBe("3");
    expect(ratio("-0.125", 2)).toBe("-0.13");
  });
  it("percent drops a trailing .0", () => {
    expect(pct("0.06")).toBe("6%");
    expect(pct("0.025")).toBe("2.5%");
    expect(pct("0.0251")).toBe("2.5%");
    expect(pct("0.5")).toBe("50%");
    expect(pct("1")).toBe("100%");
    expect(pct("0.0004")).toBe("0%");
    expect(pct("0.0005")).toBe("0.1%");
    expect(pct("-0.0004")).toBe("0%");
    expect(pct("0.123456", { decimals: 2 })).toBe("12.35%");
    expect(pct("0.5", { decimals: 1 })).toBe("50.0%");
    expect(pct(null)).toBe("—");
  });
  it("percent negatives follow the table rule, or a minus in running text", () => {
    expect(pct("-0.025")).toBe("(2.5%)");
    expect(pct("-0.025", { negative: "minus" })).toBe("-2.5%");
  });
  it("progress reads done over total", () => {
    expect(progress(4, 24)).toBe("17% (4 / 24)");
    expect(progress(0, 0)).toBe("0% (0 / 0)");
    expect(progress(1, 8)).toBe("13% (1 / 8)"); // 12.5 rounds up
    expect(progress(24, 24)).toBe("100% (24 / 24)");
    expect(() => progress(-1, 3)).toThrow(RangeError);
    expect(() => progress(1.5, 3)).toThrow(RangeError);
  });
});

describe("bytes", () => {
  it("scales by 1024 with one decimal and no trailing .0", () => {
    expect(bytes(0)).toBe("0 B");
    expect(bytes(1023)).toBe("1023 B");
    expect(bytes(1024)).toBe("1 KB");
    expect(bytes(1536)).toBe("1.5 KB");
    expect(bytes(1024 * 1024)).toBe("1 MB");
    expect(bytes(2.5 * 1024 * 1024)).toBe("2.5 MB");
    expect(bytes(5n * 1024n ** 3n)).toBe("5 GB");
    expect(() => bytes(-1)).toThrow(RangeError);
  });
});

describe("masks", () => {
  it("accepts the last four digits only", () => {
    expect(accountMask("Operating Checking", "Front Range Bank", "4410")).toBe(
      "Operating Checking (Front Range Bank) ••4410",
    );
    expect(accountMask("Payroll", null, "0007")).toBe("Payroll ••0007");
    expect(ssnMask("4417")).toBe("•••-••-4417");
    expect(einMask("4417")).toBe("••-•••4417");
  });
  it("refuses a full identifier (ADR-031)", () => {
    expect(() => ssnMask("900-45-4417")).toThrow(RangeError);
    expect(() => ssnMask("900454417")).toThrow(RangeError);
    expect(() => einMask("12-3454417")).toThrow(RangeError);
    expect(() => accountMask("Operating", null, "00004410")).toThrow(RangeError);
    expect(() => accountMask("Operating", null, "44")).toThrow(RangeError);
  });
  it("cell references and attribution", () => {
    expect(cellRef("03 Liabilities", "C29")).toBe("03 Liabilities!C29");
    expect(viaAgent("Hannah Leclerc")).toBe("Hannah Leclerc via Agent");
  });
});

describe("dates", () => {
  it("omits the year in the current year and prints it otherwise", () => {
    expect(date("2026-08-07T15:00:00Z", CHI)).toBe("Aug 7");
    expect(date("2026-07-05", CHI)).toBe("Jul 5");
    expect(date("2025-07-05", CHI)).toBe("Jul 5, 2025");
    expect(date("2027-01-02T12:00:00Z", CHI)).toBe("Jan 2, 2027");
  });
  it("always prints the year on a due date", () => {
    expect(date("2026-10-15", { ...CHI, withYear: true })).toBe("Oct 15, 2026");
  });
  it("reads a calendar date as written, in any zone", () => {
    expect(date("2026-08-07", { now: NOW, tz: "Pacific/Auckland" })).toBe("Aug 7");
    expect(date("2026-08-07", { now: NOW, tz: "Pacific/Honolulu" })).toBe("Aug 7");
  });
  it("reads a timestamp in the firm's zone, not the device's", () => {
    // 2026-08-08 03:30 UTC is 10:30 PM on Aug 7 in Chicago.
    expect(date("2026-08-08T03:30:00Z", CHI)).toBe("Aug 7");
    expect(date("2026-08-08T03:30:00Z", { now: NOW, tz: "Asia/Kolkata" })).toBe("Aug 8");
    expect(time("2026-08-08T03:30:00Z", { tz: "America/Chicago" })).toBe("10:30 PM");
  });
  it("defaults to America/Chicago", () => {
    expect(time("2026-09-14T14:24:00Z")).toBe("9:24 AM");
    expect(date("2026-08-08T03:30:00Z", { now: NOW })).toBe("Aug 7");
  });
  it("formats the time without a leading zero, with noon and midnight right", () => {
    expect(time("2026-09-14T14:24:00Z")).toBe("9:24 AM");
    expect(time("2026-09-14T17:00:00Z")).toBe("12:00 PM");
    expect(time("2026-09-14T05:05:00Z")).toBe("12:05 AM");
    expect(time("2026-09-14T23:59:00Z")).toBe("6:59 PM");
    expect(time("2026-09-14")).toBe("—"); // a calendar date has no time
  });
  it("labels the zone from Intl", () => {
    expect(time("2026-09-14T14:00:00Z", { zone: true })).toBe("9:00 AM CT");
    expect(time("2026-09-14T14:00:00Z", { tz: "America/New_York", zone: true })).toBe(
      "10:00 AM ET",
    );
    expect(dateTime("2026-05-11T16:03:00Z", { zone: true })).toBe("May 11, 2026 11:03 AM CT");
  });
  it("seconds are there for the audit trail", () => {
    expect(time("2026-09-14T14:24:07Z", { seconds: true })).toBe("9:24:07 AM");
    expect(dateTime("2026-09-14T14:24:07Z", { seconds: true, zone: true })).toBe(
      "Sep 14, 2026 9:24:07 AM CT",
    );
  });
  it("timestamps carry the year", () => {
    expect(dateTime("2026-05-11T16:03:00Z")).toBe("May 11, 2026 11:03 AM");
    expect(dateTime("2026-05-11")).toBe("May 11, 2026");
  });
  it("blank dates are an em dash", () => {
    expect(date(null, CHI)).toBe("—");
    expect(dateTime(undefined)).toBe("—");
    expect(time("")).toBe("—");
    expect(relative(null, CHI)).toBe("—");
  });
  it("refuses a value that is not a date", () => {
    expect(() => date("not a date", CHI)).toThrow(RangeError);
  });
  it("takes a Date or epoch milliseconds", () => {
    expect(time(new Date("2026-09-14T14:24:00Z"))).toBe("9:24 AM");
    expect(time(Date.parse("2026-09-14T14:24:00Z"))).toBe("9:24 AM");
  });
  it("periods", () => {
    expect(period("2025-01-01", "2025-12-31")).toBe("Jan 1 – Dec 31, 2025");
    expect(period("2025-07-01", "2026-06-30")).toBe("Jul 1, 2025 – Jun 30, 2026");
    expect(period(null, "2025-12-31")).toBe("—");
  });
  it("writes dates out in full for sentences", () => {
    expect(longDate("2026-10-01")).toBe("October 1, 2026");
    expect(longDate("2026-12-31T05:00:00Z")).toBe("December 30, 2026"); // 11 PM in Chicago
    expect(longDate(null)).toBe("—");
    expect(monthYear("2026-03")).toBe("March 2026");
    expect(monthYear("2026-03-15")).toBe("March 2026");
    expect(monthYear("")).toBe("—");
  });
  it("heads a day with its weekday (SHL-04 day groups)", () => {
    const now = "2026-09-14T09:41:00-05:00";
    expect(weekdayDate("2026-09-11T14:05:00-05:00", { now })).toBe("Friday, September 11");
    expect(weekdayDate("2026-09-28T11:46:00-05:00", { now })).toBe("Monday, September 28");
    expect(weekdayDate("2025-12-31T12:00:00-06:00", { now })).toBe("Wednesday, December 31, 2025");
    // 11 PM in Chicago is still Friday there.
    expect(weekdayDate("2026-09-12T04:00:00Z", { now })).toBe("Friday, September 11");
    expect(weekdayDate(null, { now })).toBe("—");
    expect(sameDay("2026-09-14T00:30:00-05:00", now)).toBe(true);
    expect(sameDay("2026-09-14T04:30:00Z", now)).toBe(false); // 11:30 PM on the 13th in Chicago
  });
  it("names a firm's time zone in full (SHL-03a)", () => {
    expect(zoneName("America/Chicago")).toBe("Central Time");
    expect(zoneName("America/New_York")).toBe("Eastern Time");
    expect(zoneName("Not/AZone")).toBe("Not/AZone");
  });
  it("isoDate is the business date in the zone", () => {
    expect(isoDate(NOW)).toBe("2026-09-14");
    expect(isoDate(new Date("2026-09-15T03:00:00Z"))).toBe("2026-09-14"); // 10 PM in Chicago
    expect(isoDate(new Date("2026-09-15T05:00:00Z"))).toBe("2026-09-15");
  });
});

describe("relative", () => {
  it("shows the time today, then the day words", () => {
    expect(relative("2026-09-14T14:21:00Z", CHI)).toBe("9:21 AM");
    expect(relative("2026-09-13T20:00:00Z", CHI)).toBe("Yesterday");
    expect(relative("2026-09-12T20:00:00Z", CHI)).toBe("2 Days Ago");
    expect(relative("2026-09-08T20:00:00Z", CHI)).toBe("6 Days Ago");
    expect(relative("2026-09-07T20:00:00Z", CHI)).toBe("Sep 7");
    expect(relative("2025-12-30T20:00:00Z", CHI)).toBe("Dec 30, 2025");
  });
  it("turns Yesterday over at the firm's midnight", () => {
    const justAfter = { now: new Date("2026-09-14T00:05:00-05:00"), tz: "America/Chicago" };
    expect(relative("2026-09-13T23:50:00-05:00", justAfter)).toBe("Yesterday"); // 15 minutes ago
    expect(relative("2026-09-14T00:01:00-05:00", justAfter)).toBe("12:01 AM");
    const lateEvening = { now: new Date("2026-09-14T23:55:00-05:00"), tz: "America/Chicago" };
    expect(relative("2026-09-13T00:05:00-05:00", lateEvening)).toBe("Yesterday"); // 47 hours ago
  });
  it("is a calendar-day count, so it holds across the Nov 1 2026 DST change", () => {
    // Central time falls back at 2:00 AM on Sunday Nov 1: that day has 25 hours.
    const sunday = { now: new Date("2026-11-01T23:45:00-06:00"), tz: "America/Chicago" };
    expect(relative("2026-11-01T00:30:00-05:00", sunday)).toBe("12:30 AM"); // today, 23h15 ago
    expect(relative("2026-10-31T23:30:00-05:00", sunday)).toBe("Yesterday"); // 24h15 ago
    expect(relative("2026-10-31T00:30:00-05:00", sunday)).toBe("Yesterday"); // 47h15 ago
    const monday = { now: new Date("2026-11-02T00:30:00-06:00"), tz: "America/Chicago" };
    expect(relative("2026-11-01T00:30:00-05:00", monday)).toBe("Yesterday"); // 25h ago
    expect(relative("2026-10-31T23:30:00-05:00", monday)).toBe("2 Days Ago"); // 25h ago, two days
  });
  it("keeps the wall time on either side of the repeated hour", () => {
    expect(time("2026-11-01T06:30:00Z")).toBe("1:30 AM"); // 1:30 CDT
    expect(time("2026-11-01T07:30:00Z")).toBe("1:30 AM"); // 1:30 CST, an hour later
    expect(time("2026-11-01T07:30:00Z", { zone: true })).toBe("1:30 AM CT");
    expect(dateTime("2026-11-01T08:00:00Z")).toBe("Nov 1, 2026 2:00 AM");
  });
  it("counts the spring-forward day too", () => {
    const now = { now: new Date("2026-03-09T00:30:00-05:00"), tz: "America/Chicago" };
    expect(relative("2026-03-08T01:30:00-06:00", now)).toBe("Yesterday");
  });
  it("shows a calendar date as Today, Yesterday or the date", () => {
    expect(relative("2026-09-14", CHI)).toBe("Today");
    expect(relative("2026-09-13", CHI)).toBe("Yesterday");
    expect(relative("2026-09-01", CHI)).toBe("Sep 1");
  });
  it("shows later times today and later days as dates", () => {
    expect(relative("2026-09-14T20:00:00Z", CHI)).toBe("3:00 PM");
    expect(relative("2026-09-15T20:00:00Z", CHI)).toBe("Sep 15");
  });
});

describe("since", () => {
  it("counts up from the moment, then falls back to the list words", () => {
    expect(since("2026-09-14T14:23:40Z", CHI)).toBe("Just Now");
    expect(since("2026-09-14T14:19:00Z", CHI)).toBe("5 Min Ago");
    expect(since("2026-09-14T11:00:00Z", CHI)).toBe("3 Hr Ago");
    expect(since("2026-09-13T20:00:00Z", CHI)).toBe("Yesterday");
    expect(since("2026-09-14", CHI)).toBe("Today");
  });
});
