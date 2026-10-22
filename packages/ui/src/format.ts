// The only formatter (docs/plan/04-frontend-architecture.md section 3.7; SPEC-048; F-05-T10).
// Number, money, date, time and mask formatting for the whole app. ESLint refuses `toFixed`,
// `toLocale*` and `Intl` everywhere else (packages/ui/eslint-design-rules.js).
//
// Money and decimals arrive as exact decimal strings (ADR-050). They are parsed into a scaled
// bigint and rounded with bigint arithmetic; no value passes through `Number()` or `parseFloat`.
// Dates are read in the firm's time zone (default America/Chicago), never the device's.

/** What a caller may hand to a number formatter. Null, undefined and "" render as a blank. */
export type Decimal = string | number | bigint | null | undefined;

/** What a caller may hand to a date formatter: an ISO string, epoch milliseconds or a Date. A
 * bare `YYYY-MM-DD` is a calendar date: it is never shifted by a time zone. */
export type Instant = string | number | Date | null | undefined;

/** `pos`, `neg` and `zero` are the colour cases for tables; `blank` is no value at all. */
export type AmountTone = "pos" | "neg" | "zero" | "blank";

/** `whole`: statements (1,379,849). `money`: workpaper, ledger and TB cells ($1,462,726.47).
 * `cents`: the same two decimals with no symbol, for columns whose header names the unit. */
export type AmountStyle = "whole" | "money" | "cents";

export interface AmountOptions {
  /** `dash` (default): zero is an em dash. `explicit`: zero prints as 0, 0.00 or $0.00. */
  zero?: "dash" | "explicit";
}

export interface FormattedAmount {
  text: string;
  tone: AmountTone;
}

export const DASH = "—";
/** The separator in meta lines: "Raised by Hannah Leclerc · Aug 7". */
export const SEP = " · ";
/** The firm time zone until a firm sets its own. */
export const DEFAULT_TZ = "America/Chicago";

// --- Exact decimals -----------------------------------------------------------------------

/** value = units / 10^scale */
interface Scaled {
  units: bigint;
  scale: number;
}

const DECIMAL = /^([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/;
const MAX_EXPONENT = 1000;

function pow10(n: number): bigint {
  return 10n ** BigInt(n);
}

function badDecimal(v: unknown): never {
  throw new RangeError(`Not a decimal number: ${JSON.stringify(v)}`);
}

function parseString(raw: string): Scaled {
  const m = DECIMAL.exec(raw.trim());
  const [, sign = "", whole = "", fraction = "", exponent = "0"] = m ?? [];
  if (m === null || (whole === "" && fraction === "")) return badDecimal(raw);
  const exp = Number.parseInt(exponent, 10);
  if (Math.abs(exp) > MAX_EXPONENT) return badDecimal(raw);
  let units = BigInt(`${whole}${fraction}` || "0");
  let scale = fraction.length - exp;
  if (scale < 0) {
    units *= pow10(-scale);
    scale = 0;
  }
  return { units: sign === "-" ? -units : units, scale };
}

/** Parse exactly. Throws RangeError on anything that is not a decimal number (a wrong number
 * must fail loudly, not print). Numbers go through their shortest round-trip text, never
 * arithmetic. */
export function parseDecimal(v: string | number | bigint): Scaled {
  if (typeof v === "bigint") return { units: v, scale: 0 };
  if (typeof v === "number") {
    if (!Number.isFinite(v)) return badDecimal(v);
    return parseString(String(v));
  }
  return parseString(v);
}

function isBlank(v: Decimal): v is null | undefined | "" {
  return v === null || v === undefined || (typeof v === "string" && v.trim() === "");
}

/** Round to `places` decimals, half away from zero (-2.5 becomes -3): returns units at that
 * scale. */
function roundTo(s: Scaled, places: number): bigint {
  if (s.scale <= places) return s.units * pow10(places - s.scale);
  const divisor = pow10(s.scale - places);
  const abs = s.units < 0n ? -s.units : s.units;
  let quotient = abs / divisor;
  if ((abs % divisor) * 2n >= divisor) quotient += 1n;
  return s.units < 0n ? -quotient : quotient;
}

function group(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** The magnitude of rounded units, grouped, with `places` decimals. */
function digitsOf(units: bigint, places: number): string {
  const abs = (units < 0n ? -units : units).toString().padStart(places + 1, "0");
  const whole = group(abs.slice(0, abs.length - places));
  return places === 0 ? whole : `${whole}.${abs.slice(abs.length - places)}`;
}

const PLACES: Record<AmountStyle, number> = { whole: 0, money: 2, cents: 2 };

/** An amount for a table cell: `{ text, tone }`. Negatives in parentheses, zero (after
 * rounding) as an em dash, halves rounded away from zero. Tables take their colour from the
 * tone; screens never choose a colour for a number. */
export function amount(
  v: Decimal,
  style: AmountStyle = "money",
  options: AmountOptions = {},
): FormattedAmount {
  if (isBlank(v)) return { text: DASH, tone: "blank" };
  const places = PLACES[style];
  const units = roundTo(parseDecimal(v), places);
  const symbol = style === "money" ? "$" : "";
  if (units === 0n) {
    return {
      text: options.zero === "explicit" ? `${symbol}${digitsOf(0n, places)}` : DASH,
      tone: "zero",
    };
  }
  const text = `${symbol}${digitsOf(units, places)}`;
  return units < 0n ? { text: `(${text})`, tone: "neg" } : { text, tone: "pos" };
}

/** An amount inside a sentence: a minus sign for a negative, and zero is written out
 * ("$0.00"). Tables use `amount`. */
export function prose(v: Decimal, style: AmountStyle = "money"): string {
  if (isBlank(v)) return DASH;
  const places = PLACES[style];
  const units = roundTo(parseDecimal(v), places);
  const text = `${style === "money" ? "$" : ""}${digitsOf(units, places)}`;
  return units < 0n ? `-${text}` : text;
}

/** A whole number with thousands separators, for counts ("1,204 ledger lines"). Zero is "0". */
export function count(v: Decimal): string {
  if (isBlank(v)) return DASH;
  const units = roundTo(parseDecimal(v), 0);
  return `${units < 0n ? "-" : ""}${digitsOf(units, 0)}`;
}

/** A shifted copy: value * 10^by. */
function shift(s: Scaled, by: number): Scaled {
  return { units: s.units, scale: s.scale - by };
}

export interface PctOptions {
  /** `auto` (default): up to one decimal, a trailing ".0" dropped (6%, 2.5%). A number fixes
   * the decimals. */
  decimals?: "auto" | number;
  /** `parens` (default, as in tables) or `minus` for running text. */
  negative?: "parens" | "minus";
}

/** A ratio (0.06) as a percent ("6%"). The ratio is a decimal string like any other value. */
export function pct(ratio: Decimal, options: PctOptions = {}): string {
  if (isBlank(ratio)) return DASH;
  const { decimals = "auto", negative = "parens" } = options;
  const percent = shift(parseDecimal(ratio), 2);
  const places = decimals === "auto" ? 1 : decimals;
  const units = roundTo(percent, places);
  let body = digitsOf(units, places);
  if (decimals === "auto") body = body.replace(/\.0$/, "");
  const text = `${body}%`;
  if (units >= 0n) return text;
  return negative === "minus" ? `-${text}` : `(${text})`;
}

/** A plain decimal with fixed places and no symbol, for scores and ratios ("0.85"). */
export function ratio(v: Decimal, places = 2): string {
  if (isBlank(v)) return DASH;
  const units = roundTo(parseDecimal(v), places);
  return `${units < 0n ? "-" : ""}${digitsOf(units, places)}`;
}

function nonNegativeInt(n: number, what: string): number {
  if (!Number.isSafeInteger(n) || n < 0) {
    throw new RangeError(`${what} must be a non-negative integer: ${String(n)}`);
  }
  return n;
}

/** Done over total: "17% (4 / 24)". The percent is rounded half up; no total reads 0%. */
export function progress(done: number, total: number): string {
  const d = nonNegativeInt(done, "done");
  const t = nonNegativeInt(total, "total");
  const percent = t === 0 ? 0n : (BigInt(d) * 200n + BigInt(t)) / (BigInt(t) * 2n);
  return `${percent.toString()}% (${String(d)} / ${String(t)})`;
}

const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

/** A file size, 1024-based: "512 B", "1.5 MB". One decimal from KB up, a trailing ".0" kept
 * off ("2 MB"). */
export function bytes(n: number | bigint): string {
  const total = typeof n === "bigint" ? n : BigInt(nonNegativeInt(n, "bytes"));
  if (total < 0n) throw new RangeError("bytes must not be negative");
  let unit = 0;
  while (unit < BYTE_UNITS.length - 1 && total >= 1024n ** BigInt(unit + 1)) unit += 1;
  if (unit === 0) return `${total.toString()} B`;
  const divisor = 1024n ** BigInt(unit);
  const tenths = (total * 20n + divisor) / (divisor * 2n); // round half up, exactly
  return `${digitsOf(tenths, 1).replace(/\.0$/, "")} ${BYTE_UNITS[unit] ?? "B"}`;
}

// --- Masks (ADR-031: only the last four ever reach the client) ------------------------------

function last4Of(value: string, what: string): string {
  if (!/^\d{4}$/.test(value)) {
    throw new RangeError(`${what} takes the last four digits only`);
  }
  return value;
}

/** "Operating Checking (Front Range Bank) ••4410". Takes the last four digits only. */
export function accountMask(name: string, institution: string | null, last4: string): string {
  const tail = last4Of(last4, "accountMask");
  return `${name}${institution === null || institution === "" ? "" : ` (${institution})`} ••${tail}`;
}

/** "•••-••-4417". Takes the last four digits only. */
export function ssnMask(last4: string): string {
  return `•••-••-${last4Of(last4, "ssnMask")}`;
}

/** "••-•••4417". Takes the last four digits only. */
export function einMask(last4: string): string {
  return `••-•••${last4Of(last4, "einMask")}`;
}

/** A workpaper cell reference: "03 Liabilities!C29". */
export function cellRef(sheet: string, cell: string): string {
  return `${sheet}!${cell}`;
}

/** An actor with the agent's part named: "Hannah Leclerc via Agent" (INV-5). */
export function viaAgent(person: string): string {
  return `${person.trim()} via Agent`;
}

// --- Dates and times, in the firm's zone ---------------------------------------------------

export interface ZoneOptions {
  /** An IANA zone; the firm's, default America/Chicago. */
  tz?: string;
}

export interface NowOptions extends ZoneOptions {
  /** Business time now, from `useNow()`. */
  now: Date | number;
}

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const MONTHS_LONG = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

interface Civil {
  y: number;
  m: number;
  d: number;
  /** Absent for a calendar date. */
  time?: { h: number; min: number; sec: number };
}

const partFormats = new Map<string, Intl.DateTimeFormat>();
const zoneFormats = new Map<string, Intl.DateTimeFormat>();

function partFormat(tz: string): Intl.DateTimeFormat {
  let f = partFormats.get(tz);
  if (f === undefined) {
    f = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      hourCycle: "h23",
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
    });
    partFormats.set(tz, f);
  }
  return f;
}

function zoneFormat(tz: string): Intl.DateTimeFormat {
  let f = zoneFormats.get(tz);
  if (f === undefined) {
    f = new Intl.DateTimeFormat("en-US", { timeZone: tz, timeZoneName: "shortGeneric" });
    zoneFormats.set(tz, f);
  }
  return f;
}

function civilAt(ms: number, tz: string): Civil {
  const out: Record<string, number> = {};
  for (const p of partFormat(tz).formatToParts(ms)) {
    if (p.type !== "literal") out[p.type] = Number(p.value);
  }
  return {
    y: out["year"] ?? 0,
    m: out["month"] ?? 1,
    d: out["day"] ?? 1,
    time: { h: out["hour"] ?? 0, min: out["minute"] ?? 0, sec: out["second"] ?? 0 },
  };
}

const CALENDAR_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

function msOf(v: Date | number | string): number {
  const ms = v instanceof Date ? v.getTime() : typeof v === "number" ? v : Date.parse(v);
  if (!Number.isFinite(ms)) throw new RangeError(`Not a date: ${JSON.stringify(v)}`);
  return ms;
}

function civilOf(v: Date | number | string, tz: string): Civil {
  if (typeof v === "string") {
    const m = CALENDAR_DATE.exec(v);
    if (m !== null) return { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) };
  }
  return civilAt(msOf(v), tz);
}

function blankDate(v: Instant): v is null | undefined | "" {
  return v === null || v === undefined || v === "";
}

/** Whole calendar days since 1970-01-01, so a difference of two is DST-proof. */
function dayNumber(c: Civil): number {
  return Math.floor(Date.UTC(c.y, c.m - 1, c.d) / 86_400_000);
}

function clockText(t: { h: number; min: number; sec: number }, seconds = false): string {
  const sec = seconds ? `:${String(t.sec).padStart(2, "0")}` : "";
  return `${String(t.h % 12 === 0 ? 12 : t.h % 12)}:${String(t.min).padStart(2, "0")}${sec} ${t.h < 12 ? "AM" : "PM"}`;
}

function monthDay(c: Civil): string {
  return `${MONTHS[c.m - 1] ?? ""} ${String(c.d)}`;
}

export interface DateOptions extends NowOptions {
  /** Always print the year. Due dates always do. Otherwise the year is printed only when it is
   * not the current one. */
  withYear?: boolean;
}

/** "Aug 7", or "Jul 5, 2026" outside the current year and on due dates. */
export function date(v: Instant, options: DateOptions): string {
  if (blankDate(v)) return DASH;
  const tz = options.tz ?? DEFAULT_TZ;
  const c = civilOf(v, tz);
  const thisYear = civilAt(msOf(options.now), tz).y;
  return options.withYear === true || c.y !== thisYear
    ? `${monthDay(c)}, ${String(c.y)}`
    : monthDay(c);
}

export interface TimeOptions extends ZoneOptions {
  /** Append the zone label from Intl: "9:00 AM CT". */
  zone?: boolean;
  /** Print seconds ("9:24:07 AM"), for the audit trail. */
  seconds?: boolean;
}

function zoneLabel(ms: number, tz: string): string {
  return (
    zoneFormat(tz)
      .formatToParts(ms)
      .find((p) => p.type === "timeZoneName")?.value ?? ""
  );
}

/** "9:21 AM". A calendar date has no time and gives an em dash. */
export function time(v: Instant, options: TimeOptions = {}): string {
  if (blankDate(v)) return DASH;
  const tz = options.tz ?? DEFAULT_TZ;
  const c = civilOf(v, tz);
  if (c.time === undefined) return DASH;
  const text = clockText(c.time, options.seconds);
  return options.zone === true ? `${text} ${zoneLabel(msOf(v), tz)}` : text;
}

/** "May 11, 2026 11:03 AM": a timestamp always carries its year. */
export function dateTime(v: Instant, options: TimeOptions = {}): string {
  if (blankDate(v)) return DASH;
  const tz = options.tz ?? DEFAULT_TZ;
  const c = civilOf(v, tz);
  const day = `${monthDay(c)}, ${String(c.y)}`;
  if (c.time === undefined) return day;
  const text = `${day} ${clockText(c.time, options.seconds)}`;
  return options.zone === true ? `${text} ${zoneLabel(msOf(v), tz)}` : text;
}

/** A date written out in full, for sentences: "October 1, 2026". A calendar date is read as
 * written. */
export function longDate(v: Instant, options: ZoneOptions = {}): string {
  if (blankDate(v)) return DASH;
  const c = civilOf(v, options.tz ?? DEFAULT_TZ);
  return `${MONTHS_LONG[c.m - 1] ?? ""} ${String(c.d)}, ${String(c.y)}`;
}

const zoneNames = new Map<string, string>();

/** A time zone's generic long name, for a firm's facts: "Central Time" for America/Chicago
 * (SHL-03a "US · Central Time · 46 seats"). Unknown zones read as their IANA id. */
export function zoneName(tz: string): string {
  let name = zoneNames.get(tz);
  if (name === undefined) {
    try {
      name =
        new Intl.DateTimeFormat("en-US", { timeZone: tz, timeZoneName: "longGeneric" })
          .formatToParts(0)
          .find((p) => p.type === "timeZoneName")?.value ?? tz;
    } catch {
      name = tz;
    }
    zoneNames.set(tz, name);
  }
  return name;
}

/** A month: "March 2026", from "2026-03" or any date in it. */
export function monthYear(v: string | null | undefined, options: ZoneOptions = {}): string {
  if (v === null || v === undefined || v === "") return DASH;
  const m = /^(\d{4})-(\d{2})$/.exec(v);
  const c =
    m === null ? civilOf(v, options.tz ?? DEFAULT_TZ) : { y: Number(m[1]), m: Number(m[2]), d: 1 };
  return `${MONTHS_LONG[c.m - 1] ?? ""} ${String(c.y)}`;
}

/** For lists: today shows the time ("9:21 AM"), then "Yesterday", "2 Days Ago" to "6 Days
 * Ago", then the date. A calendar date from today reads "Today". Days are counted on the
 * firm's calendar, so "Yesterday" turns over at its midnight and across a DST change. */
export function relative(v: Instant, options: NowOptions): string {
  if (blankDate(v)) return DASH;
  const tz = options.tz ?? DEFAULT_TZ;
  const c = civilOf(v, tz);
  const days = dayNumber(civilAt(msOf(options.now), tz)) - dayNumber(c);
  if (days === 0) return c.time === undefined ? "Today" : clockText(c.time);
  if (days === 1) return "Yesterday";
  if (days > 1 && days < 7) return `${String(days)} Days Ago`;
  return date(v, options);
}

/** Elapsed time for a recent event: "Just Now", "5 Min Ago", "3 Hr Ago" (same day), else the
 * list-relative form. */
export function since(v: Instant, options: NowOptions): string {
  if (blankDate(v)) return DASH;
  if (typeof v === "string" && CALENDAR_DATE.test(v)) return relative(v, options);
  const elapsed = msOf(options.now) - msOf(v);
  if (elapsed >= 0 && elapsed < 60_000) return "Just Now";
  if (elapsed >= 0 && elapsed < 3_600_000)
    return `${String(Math.floor(elapsed / 60_000))} Min Ago`;
  const tz = options.tz ?? DEFAULT_TZ;
  const sameDay = dayNumber(civilAt(msOf(options.now), tz)) === dayNumber(civilAt(msOf(v), tz));
  if (elapsed >= 0 && sameDay) return `${String(Math.floor(elapsed / 3_600_000))} Hr Ago`;
  return relative(v, options);
}

/** A period: "Jan 1 – Dec 31, 2025", or with both years when they differ. */
export function period(start: Instant, end: Instant, options: ZoneOptions = {}): string {
  if (blankDate(start) || blankDate(end)) return DASH;
  const tz = options.tz ?? DEFAULT_TZ;
  const a = civilOf(start, tz);
  const b = civilOf(end, tz);
  return a.y === b.y
    ? `${monthDay(a)} – ${monthDay(b)}, ${String(b.y)}`
    : `${monthDay(a)}, ${String(a.y)} – ${monthDay(b)}, ${String(b.y)}`;
}

/** The calendar date at an instant in the firm's zone, as YYYY-MM-DD (the business "today"). */
export function isoDate(at: Date | number, tz: string = DEFAULT_TZ): string {
  const c = civilAt(msOf(at), tz);
  return `${String(c.y).padStart(4, "0")}-${String(c.m).padStart(2, "0")}-${String(c.d).padStart(2, "0")}`;
}
