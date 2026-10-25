// SHL-20 by code (P-06-T22; DEC-351, DV-2): the card's words from the C5 aggregate. Nothing here
// reads model text: the check answers are worded from the counts and the request's period, a flag
// reason is the flag's verified citation (rendered through AgentText by the host), and there is
// never a confidence to show.

import type { ScreeningCardOut, ScreeningCheckOut } from "@abacus/api-client";
import { type ScreeningCheckVerdict, date, time } from "@abacus/ui";
import { SCREENING_COPY } from "./copy";

/** "Jun 1 – Sep 18, 2026", or "Apr 15, 2025 – Jan 15, 2026" across years; null without both ends. */
export function periodText(start: string | null, end: string | null): string | null {
  if (start === null || end === null) return null;
  const sameYear = start.slice(0, 4) === end.slice(0, 4);
  // A calendar date is read as written; `now` only decides whether the start repeats the year.
  const now = new Date(`${(sameYear ? start : end).slice(0, 4)}-07-01T12:00:00Z`);
  const from = date(start, { now, withYear: !sameYear });
  return `${from} – ${date(end, { now, withYear: true })}`;
}

/** "Sep 26, 10:12 AM": when the batch was screened. */
export function screenedAt(at: string | null, tz: string, now: Date): string | null {
  if (at === null) return null;
  return `${date(at, { now, tz })}, ${time(at, { tz })}`;
}

/** "Screened by Accrued Agent · screener@v3 · 2 s · instructions inside files are never followed" */
export function provenanceLine(card: ScreeningCardOut): string {
  const ms = card.provenance.duration_ms;
  const seconds = ms === null ? null : Math.max(1, Math.round(ms / 1000));
  return SCREENING_COPY.provenance(card.provenance.prompt_ref, seconds);
}

/** The files a rerun is screening: those not yet answering (c: "Screening 2 new files…"). */
export function newFiles(card: ScreeningCardOut): number {
  return Math.max(1, card.files_total - card.files_answering);
}

/** A check's answer, worded by code. */
export function checkAnswer(check: ScreeningCheckOut, card: ScreeningCardOut): string {
  const period = periodText(card.period_start, card.period_end);
  const flagged = card.file_flags.length;
  if (check.verdict === "not_run") return SCREENING_COPY.answers.notRun;
  if (check.key === "right_document") {
    return check.verdict === "flag"
      ? SCREENING_COPY.answers.documentFlag(card.files_answering, card.files_total)
      : SCREENING_COPY.answers.documentPass(card.files_total);
  }
  const range = period ?? "the expected period";
  if (check.verdict === "flag") {
    const wrongYear = card.file_flags.filter((f) => f.reason_code === "wrong_year").length;
    return SCREENING_COPY.answers.periodFlag(Math.max(1, wrongYear), range);
  }
  return flagged > 0
    ? SCREENING_COPY.answers.periodPassOthers(range)
    : SCREENING_COPY.answers.periodPass(range);
}

export function checkVerdict(check: ScreeningCheckOut): ScreeningCheckVerdict {
  return check.verdict;
}

/** The row chip: "Screening · 2 flagged" or "Screening · passed". */
export function chipText(card: Pick<ScreeningCardOut, "verdict" | "file_flags">): string {
  if (card.verdict === "flagged") return SCREENING_COPY.chip.flagged(card.file_flags.length);
  if (card.verdict === "passed") return SCREENING_COPY.chip.passed;
  return SCREENING_COPY.chip.notScreened;
}

/** "SURL" from "Support for 40 subsequent disbursements (SURL)"; the title when it has none. */
export function shortName(title: string): string {
  return /\(([^()]+)\)\s*$/.exec(title)?.[1] ?? title;
}
