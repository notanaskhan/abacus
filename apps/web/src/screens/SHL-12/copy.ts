// SHL-12 · Sign-off modal copy (P-04-T48): verbatim from the handoff (screens/SHL-12, spec.md) and
// the P-04 epic's SHL-12 row. Names, counts, dates and the statement are server data; these are
// the sentences around them.

import type { SignOffLevel } from "../../domain/review";

export const COPY = {
  title: "Sign off",
  loading: "Loading the sign-off…",
  missing: "This sign-off can't be loaded.",
  version: (n: number): string => `Version ${String(n)}`,
  hash: (hash: string): string => `Content hash ${hash}`,
  cells: (n: number): string => `${String(n)} cells`,
  citations: (n: number): string => `${String(n)} citations`,
  levelPicker: "Sign-off level",
  eqrHelper: "As EQR you can't sign L1–L4 on this engagement",
  ladder: "Sign-offs",
  checks: "Before you sign",
  statement: "Statement",
  cancel: "Cancel",
  roles: {
    L1_preparer: "Preparer",
    L2_reviewer: "Reviewer",
    L3_manager: "Manager",
    L4_partner: "Partner",
    L5_eqr: "EQR",
  } satisfies Record<SignOffLevel, string>,
  short: {
    L1_preparer: "L1",
    L2_reviewer: "L2",
    L3_manager: "L3",
    L4_partner: "L4",
    L5_eqr: "L5",
  } satisfies Record<SignOffLevel, string>,
  finalApproval: "final approval",
  finalLevel: (rule: string | null): string =>
    rule === null ? "Partner · final approval" : `Partner · final approval (${rule})`,
  you: "You · now",
  optional: "Optional for this workpaper",
  required: (name: string): string => `Required · ${name}`,
  atCompletion: (name: string): string => `${name} · at completion`,
  performed: (run: number, person: string, initials: string): string =>
    `Performed by Agent run #${String(run)} under the direction of ${person} · adopted by ${initials}`,
  changedAfter: "Changed after sign-off",
  viewChanges: "View changes",
  viewChangesHint: "Opens AUD-17 · review notes and sign-off matrix",
  checksCopy: {
    notesPass: (n: number): string => `Open review notes: ${String(n)}`,
    notesFail: (n: number): string =>
      n === 1 ? "1 open review note" : `${String(n)} open review notes`,
    openNotes: "Open review notes",
    openNotesHint: "Opens AUD-17 · review notes and sign-off matrix",
    noteOpen: "Open",
    independencePass: (client: string, person: string, on: string): string =>
      `Independence confirmed for ${client} · ${person} · ${on}`,
    independenceFail: (client: string): string =>
      `Your independence confirmation for ${client} is not on file (Gate G2)`,
    confirmIndependence: "Confirm independence…",
    confirmIndependenceHint: "Opens ENG-05 · team roles (later)",
    segregationPass: (preparer: string): string =>
      `You did not prepare this workpaper (preparer: ${preparer})`,
    segregationPassReturn: (preparer: string, reviewer: string): string =>
      `You did not prepare or review this return (preparer: ${preparer} · reviewer: ${reviewer})`,
    segregationFail: (short: string): string =>
      `You prepared this workpaper. A different reviewer must sign ${short}.`,
    citedPass: (cited: number, cells: number): string =>
      `Every value cited · ${String(cited)} of ${String(cells)} cells`,
    citedFail: (cited: number, cells: number): string =>
      `${String(cited)} of ${String(cells)} cells cited`,
    g4: (awaiting: string): string =>
      `Planning not approved (Gate G4): materiality is awaiting ${awaiting}. Planning workpapers can be signed; fieldwork sign-offs will show a banner.`,
    issues: (n: number, waiting: number | null, points: number | null): string =>
      waiting === null || points === null
        ? `${String(n)} issues open`
        : `${String(n)} issues open (${String(waiting)} waiting on the client · ${String(points)} review points)`,
    topPoint: "Top review point",
    openIssues: "Open issues",
    openIssuesHint: "Opens TAX-06 · return issues",
    eqrLimits: "As EQR you can sign only EQR (L5) on this engagement",
  },
  cta: {
    signOff: (role: string, short: string): string => `Sign off as ${role} (${short})`,
    reSign: (role: string, short: string): string => `Re-sign as ${role} (${short})`,
    approve: "Approve",
    clearNotes: (n: number): string =>
      n === 1 ? "Clear 1 open note to sign off" : `Clear ${String(n)} open notes to sign off`,
    resolveIssues: (n: number): string => `Resolve ${String(n)} issues to approve`,
  },
  toasts: {
    signed: (label: string, short: string, at: string): string =>
      `Signed off ${label} (${short}) · ${at}`,
    approved: (label: string, at: string): string => `Approved ${label} · ${at}`,
    failed: "The sign-off wasn't recorded. Try again.",
  },
  // SHL-12 f (P-04-T49): the bulk sheet, verbatim from the handoff's frame 6.
  bulk: {
    title: (n: number): string => `Sign off ${String(n)} workpapers`,
    workpapers: "Workpapers",
    excludedNote: "Ineligible workpapers are excluded automatically.",
    cta: (n: number, role: string, short: string): string =>
      `Sign off ${String(n)} as ${role} (${short})`,
    waiting: "Waiting on inputs",
    openNotes: (n: number): string => (n === 1 ? "1 open note" : `${String(n)} open notes`),
    youPrepared: "You prepared this",
    notAllowed: "Your role can't sign this level",
    independence: "Independence not on file",
    signed: "Signed",
    done: "Done",
    toast: (n: number, short: string): string =>
      n === 1
        ? `Signed off 1 workpaper (${short})`
        : `Signed off ${String(n)} workpapers (${short})`,
    excluded: {
      content_changed: "Changed since you opened it",
      segregation: "You prepared this",
      open_review_notes: "Open review notes",
      independence_pending: "Independence not on file",
      incomplete: "Waiting on inputs",
      uncited_change: "Uncited change",
      level_not_permitted: "Your role can't sign this level",
      not_prepared: "Waiting on inputs",
      already_signed: "Already signed",
      sign_off_invalid: "Not signed",
    } as Record<string, string>,
  },
  blocked: {
    content_changed:
      "The workpaper changed after you opened it. Review the changes, then sign again.",
    open_review_notes: "Open review notes block this level.",
    segregation: "You prepared this workpaper. A different reviewer must sign this level.",
    independence_pending: "Your independence confirmation is not on file.",
    level_not_permitted: "Your role can't sign this level.",
    fallback: "This sign-off is blocked.",
  } as Record<string, string>,
} as const;
