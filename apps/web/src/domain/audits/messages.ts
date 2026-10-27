// The audit cockpit L3's words (A-01-T06), verbatim from the AUD-02 and AUD-03 handoff (spec.md
// and revision.md; docs/screens/AUD-02.md Copy). Screens add their own copy in copy.ts; these are
// the strings the shared cockpit parts draw.

export const AUDIT_MESSAGES = {
  back: "All Audits",
  railTitle: "Overview",
  bands: {
    overview: "Overview",
    planning: "Planning",
    group: "Group",
    fieldwork: "Fieldwork",
    completion: "Completion",
    reporting: "Reporting",
  },
  started: (time: string) => `Started ${time}`,
  layout: "Layout",
  dock: { agent: "Agent", viewer: "Viewer" },
  aiUnavailable: "AI isn't available for real client data yet",
  /** The Viewer tab (SHL-08 in the dock). Not drawn in any artboard (DEC-341). */
  viewer: {
    none: "Select a document to view it here",
    unavailable: "This document can't be shown here",
    /** The E5 kit's revealed-value note ("Revealed by Samuel Ito · 9:31 AM · logged to the audit
     * trail", F-05-T47). */
    revealed: (person: string, at: string) =>
      `Revealed by ${person} · ${at} · logged to the audit trail`,
    /** Not drawn (DEC-421): the toast rules' wording for a refused reveal. */
    revealFailed: "Couldn’t reveal the value",
    /** The shell's step-up words (shell/mfa.tsx `ConfirmItsYou`). */
    stepUp: {
      title: "Confirm it's you",
      body: "This action needs a recent sign-in. Sign in again, then try once more. If it still isn't allowed, your role doesn't permit it.",
      cancel: "Cancel",
      signIn: "Sign in again",
    },
  },
  /** The v1 Agent tab (DV-2; SPEC-027 words). */
  agent: {
    pause: "Pause agent",
    paused: (person: string) => `Paused by ${person}`,
    menu: "Agent actions",
    empty: "Nothing yet",
    emptyBody:
      "When the engagement agent screens, retrieves or suggests something, it shows here.",
  },
  /** The O3 export sheet (A-01-T24). No artboard exists (DV-9): composed from kits, its words
   * from A-01 §3.6 and the C2 `engagement_export` status words (DEC-541). */
  export: {
    entry: "Export binder…",
    title: "Export binder",
    description:
      "A ZIP of this audit's PBC binder in an open format: the files, an index, their provenance and the audit trail.",
    options: "Include",
    includeUnaccepted: "Include files awaiting review",
    includeTrail: "Include the audit trail",
    footer: "Needs a recent sign-in · Undo for 10 seconds",
    cancel: "Cancel",
    export: "Export",
    requested: "Export requested",
    building: "Packaging the binder. You can close this sheet; it keeps going.",
    download: (files: number, size: string, expires: string) =>
      `Download · ${String(files)} files · ${size} · expires ${expires}`,
    failure: {
      integrity_mismatch: "A file no longer matches its fingerprint, so nothing was packaged.",
      export_section_missing: "A section of the package could not be written.",
      build_error: "The package could not be built.",
    },
    voided: {
      expired: "Downloads are kept for 7 days.",
      withdrawn_content: "A file in it was withdrawn by the client, so the package was removed.",
    },
    problem: (code: string | null) =>
      code === "export_expired"
        ? "This export has expired."
        : code === "undo_window_closed" || code === "effect_started"
          ? "The export had already started."
          : code === "export_not_ready"
            ? "This export isn't ready yet."
            : "Couldn’t export the binder",
  },
  /** Record mode (A-01-T24; DV-4): a person records what happened in the firm's own tool. */
  record: {
    menu: "Record…",
    phase: {
      entry: "Record phase…",
      title: "Record the audit's phase",
      to: "Phase",
      reason: "Reason (optional)",
      confirm: "Record phase",
    },
    release: {
      entry: "Record release…",
      title: "Record the report's release",
      on: "Released on",
      datePlaceholder: "YYYY-MM-DD",
      dateInvalid: "Enter the date as YYYY-MM-DD",
      kind: "Report",
      opinion: "Opinion issued",
      noReport: "No report",
      confirm: "Record release",
    },
    archive: {
      entry: "Record archive…",
      title: "Record the archive in the firm's tool",
      exportLabel: "Final binder export",
      none: "No ready final-binder export",
      reference: "Firm tool reference",
      confirm: "Record archive",
    },
    cancel: "Cancel",
    recorded: "Recorded",
    /** The contract's refusals in words (audits-cockpit §6); anything else reads generically. */
    refusals: {
      phase_backward: "A phase can't be recorded backwards.",
      phase_skip: "Phases are recorded one step at a time.",
      phase_follows_gate: "This phase follows its gate and can't be recorded by hand.",
      release_date_future: "The release date can't be in the future.",
      release_mode_in_app: "Releases are recorded in Accrued for this firm.",
      final_export_required: "Export a final binder first, then record the archive.",
      export_stale: "Evidence changed after that export. Export the final binder again.",
      archived_write: "This audit is archived.",
      record_out_of_phase: "The audit isn’t at the phase this record needs.",
    } as Readonly<Record<string, string>>,
    problem: "Couldn’t record it",
  },
  blocked: {
    title: (person: string) => `Waiting on ${person}`,
    action: "Open decision",
    /** Announced while the decision card (SHL-11, P-04) is a planned link. */
    unavailable: "Not built yet",
  },
} as const;

export type BandKey = keyof typeof AUDIT_MESSAGES.bands;
