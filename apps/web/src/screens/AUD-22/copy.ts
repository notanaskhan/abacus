// AUD-22's words and E0 rows, verbatim from the handoff spec (A-07-T29). The live rows and paper
// come from A-07-T26's service once the screen reads it (A-07-T33).

export interface CommRow {
  key: string;
  title: string;
  sub: string;
  disc: "half" | "ring" | "done";
  pill: string;
  tone: "neutral" | "success";
  note?: string;
  due?: string;
}

const PLANNING_260: CommRow = {
  key: "planning_260",
  title: "Planning communication",
  sub: "AU-C 260 · before fieldwork · Sep 21",
  disc: "half",
  pill: "Draft",
  tone: "neutral",
};
const COMPLETION_260: CommRow = {
  key: "completion_260",
  title: "Completion communication",
  sub: "AU-C 260 · before release · Oct 9",
  disc: "ring",
  pill: "Not started",
  tone: "neutral",
};
const SD_MW_265: CommRow = {
  key: "sd_mw_265",
  title: "Significant deficiencies and material weaknesses",
  sub: "AU-C 265 · written · ≤ 60 days after release",
  disc: "ring",
  pill: "Not started",
  tone: "neutral",
};
const REPORTABLE_703: CommRow = {
  key: "reportable_703",
  title: "Reportable findings",
  sub: "AU-C 703 · written · with the AU-C 265 letter",
  disc: "ring",
  pill: "Not started",
  tone: "neutral",
};
const MANAGEMENT_LETTER: CommRow = {
  key: "management_letter",
  title: "Management letter — other recommendations",
  sub: "Firm practice · optional",
  disc: "ring",
  pill: "Not started",
  tone: "neutral",
};

/** The row shown when a frame's selection is missing: the planning letter. */
export const FIRST_ROW: CommRow = PLANNING_260;

const ROWS_A: readonly CommRow[] = [
  { ...PLANNING_260, note: "Awaiting EP approval" },
  COMPLETION_260,
  SD_MW_265,
  REPORTABLE_703,
  MANAGEMENT_LETTER,
];

export const ROWS: Readonly<Record<"a" | "b" | "c", readonly CommRow[]>> = {
  a: ROWS_A,
  b: [
    {
      ...PLANNING_260,
      disc: "done",
      pill: "Sent Sep 18",
      tone: "success",
      note: "Acknowledged Sep 21 · Benefits Committee",
    },
    ...ROWS_A.slice(1),
  ],
  c: [
    { ...PLANNING_260, disc: "done", pill: "Acknowledged Sep 21", tone: "success" },
    { ...COMPLETION_260, disc: "done", pill: "Sent Oct 8", tone: "success" },
    {
      ...SD_MW_265,
      disc: "half",
      pill: "Draft",
      tone: "neutral",
      due: "Due Dec 8, 2026 · 60 days after release",
    },
    {
      ...REPORTABLE_703,
      disc: "half",
      pill: "Draft · combined with the AU-C 265 letter",
      tone: "neutral",
    },
    { ...MANAGEMENT_LETTER, disc: "half", pill: "Draft", tone: "neutral" },
  ],
};

export const SELECTED: Readonly<Record<"a" | "b" | "c", string>> = {
  a: "planning_260",
  b: "planning_260",
  c: "sd_mw_265",
};

export const RECIPIENTS: readonly [string, string][] = [
  ["Benefits Committee, Northwind Robotics 401(k) Plan", "Governance room"],
  ["Dana Kowalski · Plan Administrator", "Portal"],
  ["Channel", "Governance room + PDF"],
  ["Acknowledgement", "Required"],
];

export const BUILT_FROM = [
  "Risk register (AUD-08)",
  "Engagement letter",
  "Service organizations (AUD-10)",
  "Methodology “BH-EBP-110 General Planning”",
] as const;

export interface PaperSection {
  heading: string;
  body?: string;
  bullets?: readonly string[];
  after?: string;
}

export const PLANNING: {
  title: string;
  date: string;
  addressee: string;
  h3: string;
  sections: readonly PaperSection[];
  signature: string;
} = {
  title: "Planning communication",
  date: "September 17, 2026",
  addressee: "Members of the Benefits Committee · Northwind Robotics 401(k) Plan",
  h3: "Our planned audit of the plan's 2025 financial statements",
  sections: [
    {
      heading: "Our responsibilities",
      body: "We will audit the plan's financial statements as of December 31, 2025 and 2024 and for the year ended December 31, 2025, under auditing standards generally accepted in the United States of America. Management has elected an audit under ERISA section 103(a)(3)(C). For the investment information certified by Harborline Trust Company, we will perform the procedures AU-C 703 requires (comparing it to the certification and evaluating its presentation and disclosure) rather than audit it, and our report will describe this.",
    },
    {
      heading: "Planned scope and timing",
      bullets: [
        "Planning: September 14–18, 2026",
        "Fieldwork: September 21 – October 2, 2026",
        "Report expected: October 9, 2026",
        "Form 5500 due: October 15, 2026 (extended with Form 5558)",
      ],
    },
    {
      heading: "Significant risks we identified",
      bullets: [
        "Management override of controls (presumed under auditing standards)",
        "Contributions — completeness, cutoff and timeliness of remittances to the trust",
        "Participant eligibility and automatic enrollment under the plan's QACA provisions",
      ],
      after:
        "We rebutted the presumed risk of fraud in revenue recognition. The plan has no revenue transactions; contributions follow payroll and the plan's terms.",
    },
    {
      heading: "Our approach to internal control",
      body: "We will obtain an understanding of the controls over contributions, participant data and distributions, including those at Keystone Retirement Services. Keystone's SOC 1 Type 2 report covers October 1, 2024 to September 30, 2025, so we have asked Keystone for a bridge letter covering the rest of 2025. We do not express an opinion on internal control.",
    },
    {
      heading: "How we use technology",
      body: "Brightwater Hale prepares audit documentation in Accrued. Its agent drafts and tests documentation; members of our engagement team review and approve every conclusion.",
    },
    {
      heading: "Your input",
      body: "Please tell us about any fraud risks you are aware of, any late remittances, and any plan amendments or operational corrections since January 1, 2025.",
    },
  ],
  signature: "Margaret Okonkwo · Engagement Partner",
};

export const INTERNAL_CONTROL = {
  title: "Significant deficiencies and material weaknesses",
  h3: "Internal control and reportable findings — Northwind Robotics 401(k) Plan, 2025",
  sections: [
    {
      heading: "Significant deficiency",
      body: "Remittance of participant contributions — the December 26, 2025 payroll ($48,600) was remitted on January 9, 2026; the remittance file has no backup approver",
    },
    {
      heading: "Other deficiencies communicated to management",
      bullets: [
        "Monitoring of service organizations (F-02)",
        "Opt-out elections for auto-enrolled participants (F-03)",
      ],
    },
    {
      heading: "Reportable findings (AU-C 703)",
      bullets: [
        "late remittance of participant contributions (corrected under VFCP)",
        "missed deferrals for 4 auto-enrolled participants",
        "safe-harbor match not computed on bonus pay as the plan's compensation definition requires",
      ],
    },
  ] as readonly PaperSection[],
};

/** A-07-T29 remainder (DEC-3144): each communication kind's row title and clock, the screen's own
 * labels (not sample data), for the live list. */
export const KIND_ROW: Readonly<Record<string, CommRow>> = {
  planning_260: PLANNING_260,
  completion_260: COMPLETION_260,
  sd_mw_265: SD_MW_265,
  reportable_703: REPORTABLE_703,
  management_letter: MANAGEMENT_LETTER,
};
