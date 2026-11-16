import { date } from "@abacus/ui";
// CLS-03's words (C-01-T35), verbatim from the handoff (CLS-03 A–F, R2 G–H). Request titles,
// file names and figures come from the read model, never from here.
import type { RequestNodeOut } from "@abacus/api-client";

export const COPY = {
  intake: "Intake",
  viewer: "Viewer",
  requested: "Requested Documents",
  questionnaire: "Questionnaire",
  questionnaireTitle: "August close questions",
  documentRequest: "Document Request",
  uploadedDocument: "Uploaded Document",
  fields: { request: "Request", visible: "Visible to client", due: "Due", status: "Status" },
  pendingIncorporation: "Pending incorporation",
  incorporated: "Incorporated",
  summary: "Summary",
  totalsFromFile: "Totals from the file",
  screening: "Screening…",
  incorporate: "Incorporate",
  returnToClient: "Return to client…",
  rerunAffected: "Re-run affected tasks",
  undoIncorporation: "Undo incorporation",
  nothingUploaded: "Nothing uploaded yet",
  sendReminder: "Send reminder",
  sendReminderEllipsis: "Send reminder…",
  uploadOnBehalf: "Upload on behalf",
  uploadOnBehalfEllipsis: "Upload on behalf…",
  awaitingAnswer: "Awaiting answer",
  linked: "Linked",
  notPublished: (on: string | null, version: number | null): string => {
    const when =
      on === null ? "on the first business day" : date(on, { now: Date.parse(`${on}T12:00:00Z`) });
    return `Requests publish ${when} (BD1) from close plan v${String(version ?? 1)}.`;
  },
} as const;

/** The return reasons (a3), posted to POR-04. */
export const RETURN_REASONS = ["Wrong period", "Unreadable", "Incomplete"] as const;

/** A request row's sub-line from its status word (the dates ride on the request's history). */
export function subLineOf(node: RequestNodeOut): string {
  switch (node.status) {
    case "pending_incorporation":
    case "matched":
      return "Matched to uploaded document";
    case "incorporated":
      return "Incorporated";
    case "received":
      return "Received";
    default:
      return node.due_on ? `Requested · due ${node.due_on}` : "Requested";
  }
}
