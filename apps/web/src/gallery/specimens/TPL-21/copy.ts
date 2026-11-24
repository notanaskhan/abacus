// TPL-21's words, verbatim from the handoff (screens/TPL-21 spec.md).
export const C = {
  record: "FY2026 Financial Statement Audit",
  client: "Granite Peak Outdoor Supply, Inc.",
  tabs: "Engagement",
  tabWords: [
    "Overview",
    "Dashboard",
    "Board",
    "Work items 1",
    "Team 4",
    "Letter & terms",
    "Budget",
    "Activity",
  ],
  programs: "Programs",
  allPrograms: "All programs",
  planning: "PLANNING",
  execution: "EXECUTION",
  allowedTip:
    "Allowed by your AI policy for FS audits. A move can start a run; it never signs off.",
  runTip: "Procedure session · BH-FS-430 · Cole Hart via Agent · started 10:05 AM",
  dropped: "BH-FS-430 moved to In progress · run started · logged in Activity",
  guard: "Moving to Complete needs a reviewer sign-off.",
  openSignOff: "Open sign-off…",
  dock: "Agent dock",
  dockLine: "Unrecorded liabilities tester · started by Cole Hart via board move · 10:05 AM",
  openSession: "Open procedure session ›",
  overlays: "Overlay states · specimen, not seed",
  binderFooter: (b: { preparer: number; reviewer: number; total: number }) =>
    `Preparer ${String(b.preparer)} of ${String(b.total)} · Reviewer ${String(b.reviewer)} of ${String(b.total)}`,
};
