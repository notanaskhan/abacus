// AUD-17 (A-06-T24): Northwind PY2025's review notes and sign-off matrix at Fri Oct 2, 2026, 2:10 PM,
// verbatim from the handoff. 2 + 1 + 11 = 14 notes. All names are fictional. Dev and test only.

import type {
  EpInvolvementOut,
  ReviewNoteDetailOut,
  ReviewNoteItemOut,
  SignOffMatrixCellOut,
  SignOffMatrixOut,
  SignOffMatrixRowOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const AUD17_ENGAGEMENT = stableId("engagement:northwind:py2025");
export const AUD17_WORK_ITEM = stableId("work-item:northwind:py2025:assurance");
export type Aud17Variant = "a" | "b" | "f";

interface Note {
  ref: string;
  body: string;
  status: ReviewNoteItemOut["status"];
  by: string;
  anchor: string;
}

const NOTES: readonly Note[] = [
  {
    ref: "RN-12",
    body: "Show the Dec 26 lag is not a pattern — compare all 26 biweekly remittances",
    status: "open",
    by: "MO",
    anchor: "EBP-04!F31",
  },
  {
    ref: "RN-14",
    body: "Rep letter: add the specific representation on correcting the 4 missed deferrals",
    status: "open",
    by: "HL",
    anchor: "AUD-21 §3",
  },
  {
    ref: "RN-13",
    body: "Show how the $35,300 projection was computed",
    status: "responded",
    by: "MO",
    anchor: "EBP-04!K18",
  },
];

const CLEARED_COUNT = 11;

function item(n: Note, status = n.status): ReviewNoteItemOut {
  return {
    // Margaret is the engagement partner: she clears or reopens any note (SPEC-313 AC-3).
    allowed_actions:
      status === "cleared" ? ["review_note.reopen"] : ["review_note.clear", "review_note.respond"],
    anchor: { kind: "cell", ref: n.anchor },
    assignee_user_id: stableId("user:ana-cruz"),
    engagement_id: AUD17_ENGAGEMENT,
    id: stableId(`review-note:${n.ref}`),
    raised_at: "2026-09-30T16:05:00-05:00",
    raised_by_initials: n.by,
    raised_by_user_id: stableId(`user:${n.by}`),
    status,
    target_id: stableId("workpaper:EBP-04"),
    target_type: "workpaper",
  };
}

function cleared(i: number): ReviewNoteItemOut {
  return item(
    {
      ref: `RN-${String(i + 1).padStart(2, "0")}`,
      body: "",
      status: "cleared",
      by: "HL",
      anchor: "EBP-03!C4",
    },
    "cleared",
  );
}

export function aud17Notes(variant: Aud17Variant = "a"): {
  items: ReviewNoteItemOut[];
  total: number;
} {
  if (variant === "f") return { items: [], total: 0 };
  const live = NOTES.map((n) =>
    variant === "b" && n.ref === "RN-13" ? item(n, "cleared") : item(n),
  );
  const rest = Array.from({ length: CLEARED_COUNT }, (_, i) => cleared(i));
  return { items: [...live, ...rest], total: live.length + rest.length };
}

export function aud17Detail(noteId: string, variant: Aud17Variant = "a"): ReviewNoteDetailOut {
  const found = NOTES.find((n) => stableId(`review-note:${n.ref}`) === noteId);
  if (found === undefined) {
    return { body: "Cleared note", events: [], note: cleared(0) };
  }
  const events: ReviewNoteDetailOut["events"] =
    found.ref === "RN-13"
      ? [
          {
            actor_name: "Margaret Okonkwo",
            actor_user_id: stableId("user:MO"),
            at: "2026-09-30T16:05:00-05:00",
            body: "The SUM carries $35,300 as projected. Put the projection on the workpaper: sample error, sample size, population and method.",
            event: "raised",
          },
          {
            actor_name: "Ana Cruz via Agent",
            actor_user_id: stableId("user:ana-cruz"),
            at: "2026-10-02T13:58:00-05:00",
            body: "Addressed in v3: added the projection table at EBP-04!K18:K24.",
            event: "responded",
          },
          {
            actor_name: "Ana Cruz",
            actor_user_id: stableId("user:ana-cruz"),
            at: "2026-10-02T14:04:00-05:00",
            body: "Reviewed the agent's change and adopted it as v3 (L1).",
            event: "responded",
          },
        ]
      : [
          {
            actor_name: "Margaret Okonkwo",
            actor_user_id: stableId("user:MO"),
            at: "2026-09-30T16:05:00-05:00",
            body: found.body,
            event: "raised",
          },
        ];
  return {
    body: found.body,
    events,
    note: variant === "b" && found.ref === "RN-13" ? item(found, "cleared") : item(found),
    // The handoff: one stale sign-off (Contributions & Remittance L2, EBP-04), with an amber
    // notice in the thread of a note on that paper.
    paper_changed_after_signoff: found.anchor.startsWith("EBP-04"),
  };
}

function cell(level: number, spec: string): SignOffMatrixCellOut {
  if (spec === "—")
    return {
      hash_prefix: null,
      initials: null,
      level,
      signed_at: null,
      state: "not_required",
      version_no: null,
    };
  if (spec === "o")
    return {
      hash_prefix: null,
      initials: null,
      level,
      signed_at: null,
      state: "pending",
      version_no: null,
    };
  const stale = spec.startsWith("!");
  return {
    hash_prefix: "7f3a",
    initials: spec.replace("!", ""),
    level,
    signed_at: "2026-10-01T10:00:00-05:00",
    state: stale ? "stale" : "signed",
    version_no: 1,
  };
}

function row(
  section: SignOffMatrixRowOut["section"],
  code: string,
  title: string,
  cells: string,
): SignOffMatrixRowOut {
  return {
    cells: cells.split(" ").map((spec, i) => cell(i + 1, spec)),
    code,
    section,
    target_id: stableId(`workpaper:${code}`),
    target_type: "workpaper",
    title,
  };
}

export function aud17Matrix(): SignOffMatrixOut {
  return {
    footer: {
      changed_after_sign_off: 1,
      eqr_required: 6,
      eqr_signed: 0,
      partner_required: 13,
      partner_signed: 8,
      prepared: 25,
      reviewed: 24,
    },
    rows: [
      row("planning", "TB", "Trial Balance", "MD — HL — —"),
      row("planning", "MAT", "Materiality (v3)", "MD — HL MO o"),
      row("planning", "RISK", "Risk Assessment", "MD — HL MO o"),
      row("planning", "IC", "Internal Control", "MD — HL MO —"),
      row("planning", "SOC", "Service Organizations & SOC 1", "MD — HL MO —"),
      row("fieldwork", "SAMPLE", "Sample Selection (v2)", "MD — HL — —"),
      row("fieldwork", "EBP-03", "Eligibility Testing", "AC MD HL MO —"),
      row("fieldwork", "EBP-04", "Contributions & Remittance (v3)", "AC !MD o o —"),
      row("fieldwork", "EBP-05", "Distributions & Loans", "AC MD HL — —"),
      row("fieldwork", "EBP-07", "Form 5500 Tie-Out", "AC MD HL — —"),
      row("completion", "AUD-15", "Findings", "HL — — MO o"),
      row("completion", "AUD-16", "Misstatements & SUM", "HL — — o o"),
      row("completion", "AUD-19", "Completion Checklist", "o — — o —"),
      // TASK-3401 (DEC-2428): the 13 rows the handoff counts and doesn't draw, as the seed
      // makes them up to the footer's totals ("Show all 26").
      row("planning", "GAP-100", "General Audit Planning", "MD — HL MO —"),
      row("fieldwork", "MAP", "Account mapping", "MD — MO — —"),
      row("fieldwork", "EBP-01", "Plan profile & service providers", "AC MD HL — —"),
      row("fieldwork", "EBP-08", "Participant accounts summary", "AC MD HL — —"),
      row("fieldwork", "EBP-09", "Administrative expenses & operational compliance", "AC MD HL — —"),
      row("fieldwork", "T-100", "Parties in interest", "AC MD HL — —"),
      row("completion", "C-110", "Representation letter", "HL — — MO —"),
      row("completion", "C-120", "Subsequent events", "HL — — o —"),
      row("completion", "C-130", "Going concern", "HL — — — —"),
      row("reporting", "FS", "Financial statements", "MD — MO o o"),
      row("reporting", "R-100", "Auditor's report", "HL — — — o"),
      row("reporting", "R-110", "Supplemental schedules", "MD — HL — —"),
      row("reporting", "R-120", "Engagement completion memo", "MD — HL — —"),
    ],
  };
}

export function aud17Involvement(): EpInvolvementOut {
  const rows: [string, string, string][] = [
    ["2026-09-14", "Materiality v2", "decided (1.5% = $252,200)"],
    ["2026-09-16", "Significant risks", "approved"],
    ["2026-09-17", "AU-C 260 planning letter", "approved"],
    ["2026-09-25", "F-02 severity", "concluded"],
    ["2026-09-28", "F-01", "concluded Significant deficiency (after consultation C-03)"],
    ["2026-09-29", "Findings", "signed off (L4)"],
    ["2026-09-30", "Service Organizations & SOC 1", "signed off (L4) after the bridge letter"],
    ["2026-10-01", "Eligibility Testing and Internal Control", "signed off (L4)"],
  ];
  return {
    items: rows.map(([at, subject, outcome]) => ({
      at: `${at}T10:00:00-05:00`,
      by_name: "Margaret Okonkwo",
      kind: outcome.includes("signed off") ? "sign_off" : "decision",
      outcome,
      subject,
    })),
  };
}
