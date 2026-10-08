import { importTemplate } from "@abacus/api-client";

export const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

/** A workbook problem as the API reports it (SPEC-008 AC-2): where, and a fixed code. */
export interface Problem {
  where: string;
  message: string;
}

const MESSAGES: Record<string, string> = {
  not_a_workbook: "This isn't an Excel workbook (.xlsx).",
  too_large: "The file is larger than 5 MB.",
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
};

/** Turns a 422 body into readable problems; anything else becomes null. */
export function workbookProblems(error: unknown): Problem[] | null {
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
        : [sheet, row !== undefined ? `row ${row}` : null, column ?? null]
            .filter(Boolean)
            .join(" · ");
    return { where, message: MESSAGES[code] ?? "This part of the workbook isn't valid." };
  });
}

/** The workbook is the raw request body (SPEC-008 D3); the generated client sends it as is. */
export async function uploadWorkbook(name: string, file: File): Promise<void> {
  await importTemplate({
    path: { name },
    body: file as never,
    bodySerializer: null,
    headers: { "Content-Type": XLSX },
    throwOnError: true,
  });
}
