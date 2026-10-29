// "+ Upload methodology…" (K-01-T07; K-01 §3.2 AC2.1): a v2 workbook is the raw request body of
// `POST /v1/methodology/templates/{name}/versions` (SPEC-008 D3). A refusal is a 422 in the
// validation shape whose `loc` names the sheet, row and column and whose `msg` is a fixed code:
// a row problem reads "Steps · row 14 · Level", never the cell's value (ADR-052).

import { importTemplate } from "@abacus/api-client";

export const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export interface WorkbookProblem {
  where: string;
  message: string;
}

const MESSAGES: Readonly<Record<string, string>> = {
  not_a_workbook: "This isn't an Excel workbook (.xlsx).",
  too_large: "The file is larger than the limit.",
  missing_sheet: "A required sheet is missing.",
  missing_header: "The header row doesn't match the template.",
  empty_value: "This cell is empty.",
  too_long: "This value is too long.",
  duplicate_area: "This area code is used twice.",
  unknown_area: "No area has this code.",
  no_areas: "The Areas sheet has no rows.",
  invalid_tier: "The tier must be A, B, C, D or E.",
  invalid_range: "'From' is after 'to'.",
  overlapping_range: "This account range overlaps another.",
  too_many_rows: "This sheet has more rows than allowed.",
  duplicate_program: "This program code is used twice.",
  unknown_program: "No program has this code.",
  duplicate_number: "This step number is used twice in the program.",
  numbering_gap: "The step numbers skip a number.",
  duplicate_step_id: "This step ID is used twice.",
  invalid_step_id: "This step ID isn't valid.",
  invalid_code: "This code isn't valid.",
  invalid_level: "The level must be foundation, planning, testing or completion.",
  invalid_list: "This list isn't valid.",
  invalid_number: "This must be a whole number.",
  invalid_effort: "This effort isn't valid.",
  invalid_yes_no: "This must be Yes or No.",
  lock_note_without_mandatory: "A lock note needs the step to be mandatory.",
  unknown_request: "No request has this number.",
  unsafe_text: "This cell holds text that can't be imported.",
};

/** A 422 body as readable problems (sheet · row · column and a fixed message); else null. */
export function workbookProblems(error: unknown): WorkbookProblem[] | null {
  if (typeof error !== "object" || error === null || !("detail" in error)) return null;
  const detail = error.detail;
  if (!Array.isArray(detail)) return null;
  return detail.map((item: unknown) => {
    const entry = typeof item === "object" && item !== null ? item : {};
    const loc = "loc" in entry && Array.isArray(entry.loc) ? entry.loc.slice(1) : [];
    const code = "msg" in entry && typeof entry.msg === "string" ? entry.msg : "";
    const [sheet, row, column] = loc.map(String);
    const where =
      sheet === undefined
        ? "Workbook"
        : [sheet, row === undefined ? null : `row ${row}`, column ?? null]
            .filter((part): part is string => part !== null)
            .join(" · ");
    return { where, message: MESSAGES[code] ?? "This part of the workbook isn't valid." };
  });
}

/** Upload a workbook as a new version of the template `name` (which keeps its own engagement
 * types); the new version's id. */
export async function uploadMethodology(name: string, file: File): Promise<string> {
  const created = await importTemplate({
    path: { name },
    body: file as never,
    bodySerializer: null,
    headers: { "Content-Type": XLSX },
    throwOnError: true,
  });
  return created.data.version_id;
}
