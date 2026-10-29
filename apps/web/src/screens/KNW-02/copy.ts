// KNW-02 copy (K-01-T07; handoff KNW-02 spec and K-01 §3.3). Strings the handoff has none for
// (the workbook viewer's empty state, the upload sheet and the checklist's server codes) are
// written here and recorded in DEC-957.

export const COPY = {
  back: "Knowledge",
  tab: "Import review",
  tabsLabel: "Methodology version",
  tree: {
    title: "Programs",
    files: "Uploaded files",
    programs: (n: number): string => `Programs · ${String(n)} steps`,
    unavailable: "Programs can't be read yet.",
  },
  status: {
    needs_review: "Needs review",
    parsing: "Parsing…",
    draft: "Draft",
    superseded: "Superseded",
    discarded: "Discarded",
    approved: (at: string, by: string): string => `Approved · ${at} · ${by}`,
    published: "Approved",
  },
  viewer: {
    workbook: "This version came from a workbook. There is no source document.",
    workbookHelp: "Its programs and steps are in the sheet; each step keeps its workbook row.",
  },
  sheet: {
    tab: "Parsed steps",
    pick: "Program",
    mandatory: "Mandatory step",
    workbook: "Workbook",
    footer: (steps: number, mandatory: number, flagged: number): string =>
      `${String(steps)} steps · ${String(mandatory)} mandatory · ${String(flagged)} flagged`,
    empty: "Pick a program to see its steps.",
  },
  footer: {
    approve: "Approve version…",
    resolveFirst: (n: number): string =>
      `Resolve ${String(n)} flagged ${n === 1 ? "step" : "steps"} first`,
    openEditor: "Open program editor ›",
    upload: "+ Upload methodology…",
  },
  approve: {
    title: (name: string): string => `Approve ${name}`,
    effective: "Effective date",
    appliesTo: "Applies to",
    appliesValue: "Engagements accepted on or after the effective date",
    supersedes: "Supersedes",
    supersedesValue: (label: string, ends: string): string => `${label} (ends ${ends})`,
    checklist: "Before approving",
    checks: {
      has_programs: (n: number): string => `${String(n)} programs`,
      has_steps: (n: number): string => `${String(n)} steps`,
      every_program_has_steps: (): string => "Every program has steps",
    } as Readonly<Record<string, (n: number) => string>>,
    confirm: "Approve version",
    cancel: "Cancel",
    flagsOpen: "Flagged steps are still open.",
    checklistChanged: "The version changed while this sheet was open. Review it again.",
    unverified: "Some sources aren't verified yet.",
  },
  upload: {
    title: "Upload methodology",
    help: "A v2 workbook: Areas and Requests, with optional Programs and Steps sheets. It becomes a new version in Needs review.",
    file: "Workbook (.xlsx)",
    choose: "Choose file…",
    confirm: "Upload",
    problems: (n: number): string =>
      `${String(n)} ${n === 1 ? "problem" : "problems"} in the workbook`,
    failed: "The workbook couldn't be uploaded.",
  },
  stepUp: {
    title: "Confirm it's you",
    body: "Approving needs a recent second factor. Sign in again to continue.",
    cancel: "Cancel",
    signIn: "Sign in again",
  },
  refused: "Only the QM owner can approve a methodology version.",
  error: "This methodology version couldn't load.",
} as const;
