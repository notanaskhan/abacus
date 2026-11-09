// AUD-23's words and data, verbatim from the handoff canvas (`Wave 2 - Audit Completion.dc.html#aud23`;
// spec and revision R2). Fixture mode only (A-07-T34): the live report reads A-07-T27's service.

export type Mode = "audit" | "rev" | "comp";
export type Mod = "none" | "qual" | "adv" | "dis";

export const AT = {
  scope:
    "We have performed an audit of the financial statements of the Northwind Robotics 401(k) Plan, an employee benefit plan subject to ERISA, as permitted by ERISA section 103(a)(3)(C). The financial statements comprise the statements of net assets available for benefits as of December 31, 2025 and 2024, the related statement of changes in net assets available for benefits for the year ended December 31, 2025, and the related notes. Management, having determined it is permissible in the circumstances, elected to have the audit performed under section 103(a)(3)(C). The investment information it covers was certified by Harborline Trust Company, which management determined is a qualified institution.",
  op: "In our opinion, based on our audit and on the procedures described in the Auditor’s Responsibilities section: the amounts and disclosures in the accompanying financial statements, other than those agreed to or derived from the certified investment information, are presented fairly, in all material respects, in accordance with accounting principles generally accepted in the United States of America; and the information in the accompanying financial statements related to assets held by and certified to by a qualified institution agrees to, or is derived from, in all material respects, the information prepared and certified by that institution.",
  basis:
    "We conducted our audit under auditing standards generally accepted in the United States of America (GAAS). We are independent of the Plan, and the evidence we obtained supports our opinion.",
  mgmt: "Management is responsible for preparing and fairly presenting the financial statements under US GAAP and for the related internal control. Management is also responsible for determining that the section 103(a)(3)(C) election is permissible and for maintaining a current plan instrument, including all plan amendments.",
  aud1: "Our objectives are to obtain reasonable assurance about whether the financial statements as a whole are free from material misstatement, whether due to fraud or error, and to issue a report that includes our opinion. Reasonable assurance is a high level of assurance but is not absolute.",
  aud2: "In performing the audit, we exercised professional judgment and skepticism, assessed the risks of material misstatement and designed procedures responsive to them, and obtained an understanding of internal control relevant to the audit without expressing an opinion on its effectiveness. For the certified investment information, we compared it to the certification and evaluated its presentation and disclosure. We also evaluated whether conditions raise substantial doubt about the Plan’s ability to continue as a going concern, and we communicated with those charged with governance about the planned scope and timing of the audit and significant findings.",
  supp: "The supplemental schedules of delinquent participant contributions (Schedule H, line 4a) for the year ended December 31, 2025 and of assets (held at end of year) (Schedule H, line 4i) as of December 31, 2025 are presented for the purpose of additional analysis and are not a required part of the financial statements, but are supplementary information required by the Department of Labor’s Rules and Regulations for Reporting and Disclosure under ERISA. In our opinion, the information in the accompanying schedules, other than that agreed to or derived from the certified investment information, is presented fairly, in all material respects, in relation to the financial statements as a whole, and the form and content of that information are presented in conformity with the Department of Labor’s Rules and Regulations for Reporting and Disclosure under ERISA.",
  gc: "Drafted from the AUD-19 going-concern decision and the note that discloses the conditions. Illustrative only: AUD-19 concluded no substantial doubt for this plan (MO Sep 30).",
} as const;

export const RV = {
  intro:
    "We have reviewed the accompanying financial statements of Lakeshore Literacy Alliance, which comprise the statement of financial position as of June 30, 2026, the related statements of activities, functional expenses and cash flows for the year then ended, and the related notes. A review consists mainly of analytical procedures applied to management’s financial data and inquiries of management. It is substantially less in scope than an audit, whose objective is an opinion on the financial statements as a whole, so we do not express an opinion.",
  mgmt: "Management is responsible for preparing and fairly presenting these financial statements under US GAAP, including the internal control relevant to them.",
  acct: "We performed the review under Statements on Standards for Accounting and Review Services issued by the AICPA. Those standards require procedures that give us limited assurance as a basis for reporting whether we are aware of any material modifications the financial statements need. We are independent of Lakeshore Literacy Alliance.",
  concl:
    "Based on our review, we are not aware of any material modifications that should be made to the accompanying financial statements for them to be in accordance with accounting principles generally accepted in the United States of America.",
  comp: "Management is responsible for the accompanying financial statements of Lakeshore Literacy Alliance, which comprise the statement of financial position as of June 30, 2026, the related statements of activities, functional expenses and cash flows for the year then ended, and the related notes, under accounting principles generally accepted in the United States of America. We performed a compilation engagement under Statements on Standards for Accounting and Review Services issued by the AICPA. We did not audit or review the financial statements and were not required to verify the information management provided, so we do not express an opinion, a conclusion or any other assurance on them.",
} as const;

/** The O1 reason codes: code, title, sub. */
export const CODES: readonly (readonly [string, string, string])[] = [
  [
    "ERISA-SUPP",
    "Supplemental schedules required by ERISA",
    "AU-C 703 section · Schedule H line 4a · line 4i",
  ],
  ["EOM-GC", "Emphasis of matter · going concern", "Going-concern doubt alleviated and disclosed"],
  [
    "EOM-CHG",
    "Emphasis of matter · change in accounting principle",
    "Cites the note that describes the change",
  ],
  ["OM-OTHER", "Other matter", "Prior-period auditor, restricted use or another matter"],
];
/** The codes each paragraph may take. */
export const CODES_FOR: Readonly<Record<"supp" | "eom" | "om", readonly string[]>> = {
  supp: ["ERISA-SUPP"],
  eom: ["EOM-CHG"],
  om: ["OM-OTHER"],
};

export const MODS: readonly (readonly [Mod, string])[] = [
  ["none", "None — unmodified"],
  ["qual", "Qualified"],
  ["adv", "Adverse"],
  ["dis", "Disclaimer"],
];
export const OPH: Readonly<Record<Mod, string>> = {
  none: "Opinion",
  qual: "Qualified Opinion",
  adv: "Adverse Opinion",
  dis: "Disclaimer of Opinion",
};
export const MODW: Readonly<Record<Exclude<Mod, "none">, string>> = {
  qual: "qualified opinion",
  adv: "adverse opinion",
  dis: "disclaimer of opinion",
};

/** A citation marker: the rows it lights, its tooltip's two lines. */
export type Marker = readonly [readonly string[], string, string];
/** A version row: number, who (AG is the Agent), what, when. */
export type VersionRow = readonly [string, "AG" | "HL" | "MO", string, string];

export interface ModeCopy {
  ttl: string;
  title: string;
  meth: string;
  target: string;
  h3: string;
  addressee: string;
  date: string;
  vers: readonly VersionRow[];
  mk: Readonly<Record<number, Marker>>;
}

export const E: Readonly<Record<Mode, ModeCopy>> = {
  audit: {
    ttl: "Independent auditor’s report",
    title: "PY2025 Employee Benefit Plan Audit",
    meth: "BH Audit Methodology · EBP v3",
    target: "Report target Oct 9",
    h3: "Independent Auditor’s Report",
    addressee: "To the Plan Administrator and Participants of the Northwind Robotics 401(k) Plan",
    date: "October 9, 2026",
    vers: [
      ["v1", "AG", "drafted the report from the engagement record · run #4181", "Oct 2, 8:30 AM"],
      [
        "v2",
        "HL",
        "adopted the draft and added the supplemental schedules section (ERISA-SUPP)",
        "Oct 2, 11:20 AM",
      ],
    ],
    mk: {
      1: [
        ["type"],
        "Engagement letter · §103(a)(3)(C) election",
        "Harborline Trust Company certification · December 31, 2025",
      ],
      2: [
        ["form", "cites"],
        "Decision · Opinion form · MO Oct 2",
        "AU-C 703 · ERISA §103(a)(3)(C) form · unmodified",
      ],
      3: [["supp"], "Reason code ERISA-SUPP", "AUD-20 · Schedule H line 4a and line 4i"],
    },
  },
  rev: {
    ttl: "Independent accountant’s review report",
    title: "FY2026 Review Engagement",
    meth: "BH Methodology · SSARS v2",
    target: "Report target Nov 13",
    h3: "Independent Accountant’s Review Report",
    addressee: "To the Board of Directors of Lakeshore Literacy Alliance",
    date: "November 12, 2026",
    vers: [
      [
        "v1",
        "AG",
        "drafted the review report from the AUD-26 workspace · run #5032",
        "Nov 10, 9:40 AM",
      ],
    ],
    mk: {
      1: [["type"], "Engagement letter · review engagement", "AR-C 90 · limited assurance"],
      2: [["form", "cites"], "AUD-26 · review conclusion", "No material modifications identified"],
    },
  },
  comp: {
    ttl: "Accountant’s compilation report",
    title: "FY2026 Compilation Engagement",
    meth: "BH Methodology · SSARS v2",
    target: "Report target Nov 13",
    h3: "Accountant’s Compilation Report",
    addressee: "To the Board of Directors of Lakeshore Literacy Alliance",
    date: "November 12, 2026",
    vers: [
      [
        "v1",
        "AG",
        "drafted the compilation report from the AUD-26 workspace · run #5033",
        "Nov 10, 9:45 AM",
      ],
    ],
    mk: {
      1: [
        ["type", "form"],
        "Engagement letter · compilation engagement",
        "AR-C 80 · no assurance",
      ],
    },
  },
};

export const NAMES: Readonly<Record<VersionRow[1], string>> = {
  AG: "Accrued Agent",
  HL: "Hannah Leclerc",
  MO: "Margaret Okonkwo",
};

export type Frame = "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j";

/** Each artboard's opening state (the canvas's FR tuples). */
export interface FrameSeed {
  m: Mode;
  now: string;
  appr?: boolean;
  mod?: Mod;
  gc?: boolean;
  re?: boolean;
  gen?: "run" | "done";
  toast?: boolean;
  stale?: boolean;
}

export const FRAMES: Readonly<Record<Frame, FrameSeed>> = {
  a: { m: "audit", now: "Oct 6, 10:10 AM" },
  b: { m: "audit", now: "Oct 7, 4:25 PM", appr: true },
  c: { m: "audit", now: "Oct 6, 10:10 AM", mod: "qual" },
  d: { m: "audit", now: "Oct 6, 10:10 AM", gc: true },
  e: { m: "rev", now: "Nov 10, 2:00 PM" },
  f: { m: "comp", now: "Nov 10, 2:05 PM" },
  g: { m: "audit", now: "Jan 15, 2027, 11:00 AM", appr: true, re: true },
  h: { m: "audit", now: "Oct 6, 10:10 AM", gen: "run" },
  i: { m: "audit", now: "Oct 6, 10:10 AM", gen: "done", toast: true },
  j: { m: "audit", now: "Oct 6, 10:10 AM", gen: "done", stale: true },
};

export const APPROVED_AT = "Oct 7, 4:20 PM";
export const REISSUE_VERSION: VersionRow = [
  "v3",
  "HL",
  "prepared the reissue · dual date for Note 12 (AUD-30)",
  "Jan 14, 2027, 3:30 PM",
];
export const DUAL_DATE_LINE =
  "October 9, 2026, except for Note 12, as to which the date is January 15, 2027";
export const TEMPLATE = "BH Report · EBP 103(a)(3)(C) v3";
export const LETTERHEAD = [
  "Brightwater Hale LLP",
  "311 West Brannock Street, Chicago, IL",
] as const;
