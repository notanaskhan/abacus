// The Feld 2025 binder as TPL-19 shows it at 390 (F-06-T02; docs/screens/TPL-19.md): the two open
// requests (Form 1095-C, estimated payments), 4 received and 1 provided by the firm, all derived
// from the BND-02 binder rows (fixtures/seed/binder-detail.ts), never restated. After frame f's
// upload the 1095-C is matched and the binder reads "1 to do" (Feld Intake 2 → 1).

import { FELD_REQUEST_FACTS } from "../binder-detail";

export const FELD = "Jonah & Claire Feld";

export function feldCounts(uploaded: readonly string[] = []): {
  toDo: number;
  received: number;
  provided: number;
} {
  const open = FELD_REQUEST_FACTS.filter((r) => r.state === "to_do" && !uploaded.includes(r.key));
  return {
    toDo: open.length,
    received: FELD_REQUEST_FACTS.filter((r) => r.state === "received").length,
    provided: FELD_REQUEST_FACTS.filter((r) => r.state === "provided").length,
  };
}

/** The open requests in binder order (frame b's request cards). */
export const FELD_OPEN_REQUESTS = FELD_REQUEST_FACTS.filter((r) => r.state === "to_do");

/** Frame e: the stitched upload (R-03 stitches server side; the kit takes these as props). */
export const FELD_CAPTURE = {
  request: "aca",
  fileName: "Claire_Feld_2025_1095-C_MercerHill.pdf",
  pages: 2,
  size: "3.1 MB",
  sources: ["Claire_Feld_1095C_Camera_P1.jpg", "Claire_Feld_1095C_Camera_P2.jpg"],
  uploadedDay: "Sep 14",
} as const;

/** Frame a: the return card and the team (TPL-19 frame 1). */
export const FELD_HOME = {
  dueDate: "Oct 15, 2026",
  messageFrom: "Kevin Osei",
  messagePreview: "Could you send the 1095-C when you have a moment?",
  team: [
    { name: "Daniel Reyes", role: "Partner" },
    { name: "Samuel Ito", role: "Manager" },
    { name: "Kevin Osei", role: "Preparer" },
  ],
} as const;
