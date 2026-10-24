import type { TableColumn, TableRow } from "../data/types";
import type { CitationView } from "../tracing/types";
import { workpaperCell } from "../workpaper/workpaper";
import type { SourceDoc, WorkpaperTab } from "../workpaper/types";
import { NORTHWIND_PBC } from "./seed-figures";

// The Service Organizations & SOC 1 workpaper the T2b canvas draws (T2 handoff, Wave 0 Templates
// `SOC_TABS`), word for word, with the C-02 kit's sample organisations moved to the seed's
// (DEC recorded in docs/product/decision-log.md, F-05-T50): the recordkeeper is Keystone Retirement
// Services and the payroll provider PayGrid Payroll, and Keystone's bridge letter is the one still
// outstanding, as the seed's PBC list has it at E0. Match ids come from workpaper-cell locators.

const SHEET = "northwind-py2025-soc";
const LINKAGE = "northwind-py2025-linkage";

const text = (value: string) => ({ value });

const ORG: readonly TableColumn[] = [
  { key: "org", header: "Service organization", type: "label" },
  { key: "svc", header: "Services provided", type: "text" },
  { key: "rel", header: "Relevant", type: "text", width: 96 },
];

const ORGS: readonly TableRow[] = [
  {
    id: "keystone",
    label: "Keystone Retirement Services",
    cells: { svc: text("Recordkeeping"), rel: text("Yes") },
  },
  {
    id: "harborline",
    label: "Harborline Trust Company",
    cells: { svc: text("Custody and trustee"), rel: text("Yes") },
  },
  {
    id: "paygrid",
    label: "PayGrid Payroll",
    cells: { svc: text("Payroll processing"), rel: text("Yes") },
  },
  {
    id: "lumen",
    label: "Lumen Benefits Advisors",
    cells: { svc: text("Investment advice"), rel: text("No") },
  },
];

const SOC: readonly TableColumn[] = [
  { key: "org", header: "Organization", type: "label" },
  { key: "per", header: "Report period", type: "text", width: 196 },
  { key: "op", header: "Opinion", type: "text", width: 100 },
  { key: "br", header: "Bridge letter", type: "text", width: 108 },
];

const SOC_ROWS: readonly TableRow[] = [
  {
    id: "soc-keystone",
    label: "Keystone Retirement Services",
    cells: {
      per: text("Oct 1, 2024 – Sep 30, 2025"),
      op: text("Unmodified"),
      br: text("Requested"),
    },
  },
  {
    id: "soc-harborline",
    label: "Harborline Trust Company",
    cells: { per: text("Jan 1 – Dec 31, 2025"), op: text("Unmodified"), br: text("Not needed") },
  },
  {
    id: "soc-paygrid",
    label: "PayGrid Payroll",
    cells: {
      per: text("Oct 1, 2024 – Sep 30, 2025"),
      op: text("Unmodified"),
      br: text("Received"),
    },
  },
];

const SOC_CITES: readonly CitationView[] = [
  {
    n: 1,
    title: "AP-10: Audit Program for General Planning Procedures",
    quote:
      "4. Determine whether the plan uses a service organization and if the service organization’s services are relevant to the plan’s financial statements. If so, document the controls the plan relies on and complete AP-40.",
    loc: "BH Audit Methodology · EBP v3 · page 14",
    match: workpaperCell(SHEET, "keystone", "org"),
    kind: "workpaper",
  },
  {
    n: 2,
    title: "Keystone Retirement Services SOC 1 Type 2.pdf",
    quote:
      "Report on the recordkeeping system and the suitability of the design and operating effectiveness of its controls for the period October 1, 2024 to September 30, 2025.",
    loc: "Page 1 · Independent service auditor’s report",
    match: workpaperCell(SHEET, "soc-keystone", "per"),
    kind: "pdf",
  },
  {
    n: 3,
    title: "Bridge letter · PayGrid Payroll.pdf",
    quote:
      "No changes to the system or controls described in the SOC 1 report occurred from October 1 through December 31, 2025.",
    loc: "Signed Jan 14, 2026",
    match: workpaperCell(SHEET, "soc-paygrid", "br"),
    kind: "pdf",
  },
];

export const SOC_TABS: readonly WorkpaperTab[] = [
  {
    label: "Service Organizations",
    sheet: SHEET,
    sections: [
      {
        id: "s1",
        n: 1,
        title: "Service organizations",
        sign: "Prepared · Accrued Agent",
        caption:
          "Determines whether the plan uses a service organization and whether its controls are significant to the plan’s system of internal control.",
        rows: [
          {
            key: "Procedure performed",
            text: "AP-10 step 4. Identified the organizations that process plan transactions and assessed whether each is relevant to the financial statements.",
            cites: [1],
          },
          {
            key: "Result",
            text: "The plan uses four service organizations. Three are relevant to the financial statements.",
          },
        ],
        table: { columns: ORG, rows: ORGS },
        after: [{ key: "AP-40 required", text: "Yes" }],
      },
      {
        id: "s2",
        n: 2,
        title: "SOC 1 reports",
        caption:
          "Evaluates the SOC 1 Type 2 report for each relevant service organization and the period it covers.",
        rows: [
          {
            key: "Procedure performed",
            text: "AP-40 step 2. Obtained each SOC 1 Type 2 report, compared its period to the plan year and read the opinion and any exceptions noted.",
            cites: [2],
          },
        ],
        schedule: "Schedule 1100.04-A · SOC 1 report coverage",
        table: { columns: SOC, rows: SOC_ROWS },
        after: [
          {
            key: "Result",
            text: "Two reports end Sep 30, 2025. PayGrid’s bridge letter covers Oct 1 to Dec 31; Keystone’s is still outstanding.",
            cites: [3],
          },
        ],
      },
      {
        id: "s3",
        n: 3,
        title: "Complementary user entity controls",
        sign: "Prepared · Accrued Agent",
        collapsed: true,
        caption: "Confirms that the plan sponsor performs the controls each SOC 1 report assumes.",
        rows: [
          {
            key: "Procedure performed",
            text: "AP-40 step 5. Matched each complementary user entity control to a sponsor control and tested the ones over contributions and distributions.",
          },
          {
            key: "Result",
            text: "All 11 controls map to sponsor controls. The two tested had no exceptions.",
          },
          {
            key: "Conclusion",
            text: "Reliance on the SOC 1 reports is appropriate for the 2025 plan year.",
          },
        ],
      },
    ],
    citations: SOC_CITES,
    procedures: [
      { ref: "AP-10 step 4", title: "General Planning Procedures" },
      { ref: "AP-40 step 2", title: "Service Organization Procedures" },
      { ref: "AP-40 step 5", title: "Service Organization Procedures" },
    ],
  },
  {
    label: "Linkage",
    sheet: LINKAGE,
    sections: [
      {
        id: "l1",
        n: 1,
        title: "Risk linkage",
        caption:
          "Links each significant risk of material misstatement to the procedures that address it.",
        table: {
          columns: [
            { key: "risk", header: "Risk", type: "label" },
            { key: "as", header: "Assertion", type: "text", width: 116 },
            { key: "pr", header: "Procedures", type: "text", width: 168 },
          ],
          rows: [
            {
              id: "r1",
              label: "Investments are not measured at fair value",
              cells: { as: text("Valuation"), pr: text("AP-10 step 4 · AP-40") },
            },
            {
              id: "r2",
              label: "Contributions are not remitted on time",
              cells: { as: text("Completeness"), pr: text("AP-22 step 3") },
            },
            {
              id: "r3",
              label: "Distributions are paid to ineligible participants",
              cells: { as: text("Occurrence"), pr: text("AP-31 step 2") },
            },
          ],
        },
        after: [
          {
            key: "Conclusion",
            text: "Each significant risk maps to at least one procedure.",
            cites: [1],
          },
        ],
      },
    ],
    citations: [
      {
        n: 1,
        title: "Risk assessment memo · 2025.docx",
        quote:
          "Significant risks for the 2025 plan year: valuation of investments, timeliness of contributions and eligibility for distributions.",
        loc: "Section 3 · Significant risks",
        match: workpaperCell(LINKAGE, "r1", "risk"),
        kind: "docx",
      },
    ],
    procedures: [
      { ref: "AP-22 step 3", title: "Contributions" },
      { ref: "AP-31 step 2", title: "Distributions" },
    ],
  },
];

/** Northwind's PBC list grouped by category, in the seed's order, with its counts. */
export interface PbcGroup {
  title: string;
  received: number;
  total: number;
  docs: readonly SourceDoc[];
}

export function pbcGroups(): readonly PbcGroup[] {
  const groups: { title: string; docs: SourceDoc[] }[] = [];
  NORTHWIND_PBC.forEach((item, i) => {
    let group = groups.find((g) => g.title === item.category);
    if (group === undefined) {
      group = { title: item.category, docs: [] };
      groups.push(group);
    }
    group.docs.push({
      id: `pbc-${String(i + 1)}`,
      title: item.title,
      status: item.status,
      ...(item.path === undefined ? {} : { path: item.path }),
    });
  });
  return groups.map((g) => ({
    ...g,
    received: g.docs.filter((d) => d.status === "received").length,
    total: g.docs.length,
  }));
}
