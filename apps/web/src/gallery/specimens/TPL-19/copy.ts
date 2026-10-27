// TPL-19 portal mobile specimen copy (F-06-T01): verbatim from the handoff
// (screens/TPL-19, spec.md). Frames 3, 4 and 8 and the permission-off variant are deferred
// (DEC-97 → R-03) and render only the placeholder label. White-labelled (DEC-01).

export const COPY = {
  greeting: (first: string): string => `Good morning, ${first}`,
  returnCard: "2025 Tax Return",
  reviewing: "We're reviewing your return",
  stillNeeded: (n: number, due: string): string =>
    `${n} documents still needed · extended due date ${due}`,
  uploadTodo: (n: number): string => `Upload ${n} documents`,
  messageTodo: (from: string): string => `1 new message from ${from}`,
  teamCard: (firm: string): string => `Your ${firm} team`,
  binder: "2025 Binder",
  toDo: (n: number): string => `${n} to do`,
  dropZone: "Tap to upload or take a photo",
  dropZoneNote: "Photos of multi-page documents are combined into one PDF",
  upload: "Upload…",
  ignore: "Ignore",
  receivedRow: (received: number, provided: number, firm: string): string =>
    `${received} received · ${provided} provided by ${firm}`,
  takePhoto: "Take a photo",
  chooseFile: "Choose a file",
  retakePage: (n: number): string => `Retake page ${n}`,
  addPage: "Add a page",
  addToRequest: "Add to request",
  somethingElse: "Something else",
  uploadConfirm: "Upload",
  uploaded: (day: string): string => `✓ You uploaded ${day}`,
  matched: "Matched to this request",
  more: ["Questions", "Deliverables", "People & access", "Security", "Sign out"],
  envelopeTitle: "Form 8879 · TY2025",
  stepChips: "Verify ✓ · Review ✓ · Sign · Done",
  adoptAndSign: "Adopt signature & sign…",
  deferred: "Deferred (DEC-97)",
  alternateCaption: "Alternate: client uploads by camera instead of email (not the seeded demo day)",
  tabs: ["Home", "Documents", "Sign", "Messages", "More"],
} as const;
