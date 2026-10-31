// KNW-02 copy (K-01-T07; handoff KNW-02 spec and K-01 §3.3). Strings the handoff has none for
// (the workbook viewer's empty state, the upload sheet and the checklist's server codes) are
// written here and recorded in DEC-957.

export const COPY = {
  back: "Knowledge",
  tab: "Import review",
  // K-01-T19: KNW-02 c, d and the Activity tab.
  tabs: {
    review: "Import review",
    diff: (label: string): string => `Diff vs ${label}`,
    standards: "Standards mapping",
    activity: "Activity",
  },
  compare: (label: string): string => `Compare with ${label}`,
  diff: {
    title: (label: string): string => `Diff vs ${label}`,
    added: "Added",
    changed: "Changed",
    removed: "Removed",
    unchanged: "Unchanged",
    totals: (v: string, n: number, w: string, m: number): string =>
      `${v} = ${String(n)} steps · ${w} = ${String(m)} steps`,
    kind: { added: "New", changed: "Changed", removed: "Removed" } as Readonly<
      Record<string, string>
    >,
    where: (code: string, n: number): string => `${code} · step ${String(n)}`,
    none: "No differences.", // (undesigned)
    failed: "The diff couldn't load.", // (undesigned)
  },
  standards: {
    title: "Standards mapping",
    set: "Standards set",
    quality: "Quality management",
    types: "Engagement types",
    default: (family: string): string => `Default for new ${family} audits`,
    defaultOn: (family: string, label: string): string =>
      `Yes · new ${family} audits start on ${label}`,
    defaultOff: "No", // (undesigned)
    change: "Change",
    none: "—",
    note: (family: string, prior: string): string =>
      `New ${family} audits accepted on or after the effective date use this version and standards set. Engagements already in progress keep ${prior}.`,
    typeWords: {
      ebp_dc_limited_scope: "EBP DC §103(a)(3)(C)",
      ebp_dc_full_scope: "EBP DC full scope",
      ebp_db: "EBP DB",
      ebp_audit: "EBP audit",
      fs_audit: "FS audit",
      review: "Review",
      compilation: "Compilation",
      preparation: "Preparation",
    } as Readonly<Record<string, string>>,
    failed: "The mapping wasn't saved. Try again.", // (undesigned)
  },
  activity: {
    title: "Activity",
    empty: "No activity yet.", // (undesigned)
    kinds: {
      imported: "imported this version",
      import_started: "started the import",
      submitted: "submitted it for approval",
      approved: "approved it",
      superseded: "superseded it",
      published: "published it",
      discarded: "discarded it",
      draft_created: "created the draft",
      standards_mapped: "mapped the standards",
      exported: "exported the programs",
      step_added: "added a step",
      step_edited: "edited a step",
      step_removed: "removed a step",
      mandatory_changed: "changed a mandatory lock",
      flag_resolved: "resolved a flag",
      legacy_backfilled: "carried it over",
    } as Readonly<Record<string, string>>,
    system: "Accrued", // (undesigned) the system's own events
  },
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
    // K-01 AC6.3: a draft edited in the program editor.
    draft: "This version was edited in the program editor. There is no source document.",
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
