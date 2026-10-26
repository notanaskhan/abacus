// POR-04 Request sheet (R-01-T05): one scenario per artboard, a–g (docs/screens/POR-04.md), each
// a data condition on `GET /v1/portal/request-items/{id}` over the POR-03 binder behind it. e and
// f are the sheet's question and decision slots, fixture only: their data is the artboard's
// `ARTBOARD` entry (C-01 and T-06 / T-09 wire them to their own routes). Clocks: E0, except c
// (9:12 AM, the email) and e (1:10 PM) and f (before 5:00 PM CT).

import type { PortalRequestOut } from "@abacus/api-client";
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { portalHandlers } from "../handlers/portal";
import { portalDocumentsHandlers } from "../handlers/portal-documents";
import { DEMO_INSTANT } from "../seed/clock";
import {
  type DecisionSlot,
  FELD,
  FELD_2024,
  FELD_2025,
  FELD_FILES,
  FELD_ROWS_A,
  FELD_ROWS_C2,
  FELD_ROWS_G,
  type QuestionSlot,
  RETURNED_NOTE,
  RIDGELINE_DECISION,
  SHEET_UPLOAD_PERCENT,
  SOUND_ELECTRIC_QUESTION,
  THREADS,
  feldBinder,
  sheet1095c,
} from "../seed/portal-documents";
import { EMAIL_CLOCK } from "./POR-03";

/** Mon Sep 14, 2026, 1:10 PM CT: Ben Ashby answers Raj Malhotra's question (POR-04 e). */
export const QUESTION_CLOCK = "2026-09-14T13:10:00-05:00";
/** Mon Sep 14, 2026, 4:12 PM CT: before Ridgeline's 5:00 PM CT answer-by (POR-04 f). */
export const DECISION_CLOCK = "2026-09-14T16:12:00-05:00";

export interface Por04Artboard {
  requestId: string;
  /** "This doesn't apply to me…" pressed (b). */
  ignoreOpen?: boolean;
  /** A portal upload in flight, held for review (g). */
  uploadPercent?: number;
  /** The file in flight (g): Claire's 2025 1095-C, 412 KB. */
  uploading?: { name: string; sizeBytes: number; percent: number };
  question?: QuestionSlot;
  decision?: DecisionSlot;
}

const sheetAt = (
  state: string,
  persona: string,
  sheet: PortalRequestOut | null,
  rows = FELD_ROWS_A,
  clock = DEMO_INSTANT,
): Scenario => ({
  state,
  persona,
  clock,
  handlers: {
    ...portalHandlers({ clock }),
    ...portalDocumentsHandlers({
      clock,
      binders: [FELD_2025, FELD_2024],
      binder: feldBinder(rows),
      requests: sheet === null ? [] : [sheet],
      threads: THREADS,
    }),
  },
});

/** c, the seeded day: the copy Claire emailed at 9:12 AM, filed by the firm (no Withdraw). */
export const SHEET_EMAILED = sheet1095c({
  client_status: "done",
  files: [FELD_FILES.emailed1095c],
  allowed_actions: ["comment"],
});
/** c, the portal-upload variant (alternate path): Withdraw on Claire's own unaccepted file. */
export const SHEET_UPLOADED = sheet1095c({
  client_status: "done",
  files: [FELD_FILES.uploaded1095c],
  allowed_actions: ["withdraw", "comment"],
});
const SHEET_RETURNED = sheet1095c({
  client_status: "returned",
  files: [FELD_FILES.returned1095c],
  returned: RETURNED_NOTE,
  allowed_actions: ["upload", "comment"],
});

const BUILD = {
  a: () => sheetAt("a", "claire-feld", sheet1095c()),
  b: () => sheetAt("b", "claire-feld", sheet1095c()),
  c: () => sheetAt("c", "claire-feld", SHEET_EMAILED, FELD_ROWS_C2, EMAIL_CLOCK),
  d: () => sheetAt("d", "claire-feld", SHEET_RETURNED, FELD_ROWS_G),
  e: () => sheetAt("e", "ben-ashby", null, FELD_ROWS_A, QUESTION_CLOCK),
  f: () => sheetAt("f", "owen-calder", null, FELD_ROWS_A, DECISION_CLOCK),
  g: () => sheetAt("g", "claire-feld", sheet1095c({ uploading_count: 1 })),
} as const;

export type Por04State = keyof typeof BUILD;

export const scenarios = defineScenarios({
  a: BUILD.a(),
  b: BUILD.b(),
  c: BUILD.c(),
  d: BUILD.d(),
  e: BUILD.e(),
  f: BUILD.f(),
  g: BUILD.g(),
});

/** A scenario with handlers of its own: the writes it answers (an upload, a comment) change only
 * its own rows (tests that write start from the artboard each time). */
export function freshScenario(state: Por04State): Scenario {
  return BUILD[state]();
}

export const ARTBOARD: Readonly<Record<Por04State, Por04Artboard>> = {
  a: { requestId: FELD.form1095c },
  b: { requestId: FELD.form1095c, ignoreOpen: true },
  c: { requestId: FELD.form1095c },
  d: { requestId: FELD.form1095c },
  e: { requestId: "question", question: SOUND_ELECTRIC_QUESTION },
  f: { requestId: "decision", decision: RIDGELINE_DECISION },
  g: {
    requestId: FELD.form1095c,
    uploadPercent: SHEET_UPLOAD_PERCENT,
    uploading: {
      name: FELD_FILES.uploaded1095c.name,
      sizeBytes: FELD_FILES.uploaded1095c.size_bytes ?? 0,
      percent: SHEET_UPLOAD_PERCENT,
    },
  },
};
