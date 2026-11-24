// TAX-10 (T-08-T22; TASK-8936; DEC-5938): the Feld two-year comparison a–e and x1, exported from
// the Python slice (`two_year_slice.tax10_rows`, `scenario.tax10.json`). Every figure, Δ, Δ% and
// flag is the code's there; this file only applies the person's writes the handlers record.
import type { TaxPracticeTwoYearLineOut, TaxPracticeTwoYearOut } from "@abacus/api-client";
import exported from "./scenario.tax10.json";

export type Tax10State = "a" | "b" | "c" | "d" | "e" | "x1";
const DATA = exported as unknown as Record<Tax10State, TaxPracticeTwoYearOut>;

export function twoYear(state: Tax10State): TaxPracticeTwoYearOut {
  return DATA[state];
}

/** A person's acceptance (the reviewer's initials) or edit (a new human version, proposed). */
export function applyWrite(
  base: TaxPracticeTwoYearOut,
  lineKey: string,
  write: { accept: true } | { text: string },
): TaxPracticeTwoYearOut {
  const lines = base.lines.map((l): TaxPracticeTwoYearLineOut => {
    if (l.line_key !== lineKey) return l;
    return "accept" in write
      ? {
          ...l,
          state: "accepted",
          accepted_by_initials: "SI",
          accepted_at: "2026-09-14T10:07:00-05:00",
          allowed_actions: ["two_year.edit"],
        }
      : {
          ...l,
          state: "proposed",
          explanation: write.text,
          author_kind: "human",
          explanation_version_id:
            l.explanation_version_id ?? "00000000-0000-4000-8000-00000000a010",
          allowed_actions: ["two_year.edit", "two_year.accept"],
        };
  });
  return { ...base, lines, accepted: lines.filter((l) => l.state === "accepted").length };
}
