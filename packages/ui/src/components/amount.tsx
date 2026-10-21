import type { HTMLAttributes, JSX } from "react";
import { cn } from "../cn";
import { useFormat } from "../clock";
import {
  type AmountOptions,
  type AmountStyle,
  type AmountTone,
  type Decimal,
  type Instant,
  amount,
} from "../format";

const TONE_CLASS: Record<AmountTone, string> = {
  pos: "",
  neg: "text-negative",
  zero: "text-ink-4",
  blank: "text-ink-4",
};

export interface AmountProps
  extends AmountOptions, Omit<HTMLAttributes<HTMLSpanElement>, "children" | "style"> {
  /** An exact decimal string from the API (ADR-050), or a number or bigint. */
  value: Decimal;
  /** The number format (plan section 3.7), not CSS: inline styles are not accepted.
   * `money` ($1,462,726.47, default), `cents` (no symbol) or `whole` (statements). */
  style?: AmountStyle;
}

/** A number in a table: tabular figures, negatives in parentheses in the negative colour, zero
 * as an em dash in ink-4. Screens never choose a colour for a number (plan section 3.7). */
export function Amount({
  value,
  style = "money",
  zero,
  className,
  ...props
}: AmountProps): JSX.Element {
  const { text, tone } = amount(value, style, zero === undefined ? {} : { zero });
  return (
    <span className={cn("tabular-nums", TONE_CLASS[tone], className)} {...props}>
      {text}
    </span>
  );
}

export type DateKind = "date" | "dateTime" | "time" | "relative" | "since";

export interface DateTextProps extends Omit<HTMLAttributes<HTMLTimeElement>, "children"> {
  value: Instant;
  /** `date` (default): "Aug 7". `dateTime`: "May 11, 2026 11:03 AM". `time`. `relative`: list
   * words ("Yesterday"). `since`: elapsed ("5 Min Ago"). */
  kind?: DateKind;
  /** Print the year even in the current one (due dates). Only for `date`. */
  withYear?: boolean;
  /** Append the zone label ("9:00 AM CT"). Only for `time` and `dateTime`. */
  zone?: boolean;
  /** Print seconds, for the audit trail. Only for `time` and `dateTime`. */
  seconds?: boolean;
}

function attributeOf(value: Instant): string | undefined {
  if (value === null || value === undefined || value === "") return undefined;
  if (typeof value === "string") return value;
  return new Date(value).toISOString();
}

/** A date or time in the firm's zone, as a `<time>` element, read against the business clock. */
export function DateText({
  value,
  kind = "date",
  withYear = false,
  zone = false,
  seconds = false,
  className,
  ...props
}: DateTextProps): JSX.Element {
  const f = useFormat();
  let text: string;
  switch (kind) {
    case "dateTime":
      text = f.dateTime(value, { zone, seconds });
      break;
    case "time":
      text = f.time(value, { zone, seconds });
      break;
    case "relative":
      text = f.relative(value);
      break;
    case "since":
      text = f.since(value);
      break;
    case "date":
      text = f.date(value, { withYear });
      break;
  }
  return (
    <time dateTime={attributeOf(value)} className={cn("tabular-nums", className)} {...props}>
      {text}
    </time>
  );
}
