// TXI-03 copy and the Feld residency facts and allocation the artboards draw (T-04-T41; handoff
// TXI-03 spec, verbatim). The tables foot to the acceptance checklist: 268,400 + 6,910 + 14,820 +
// 307,900 = 598,030; + 1,550 + 16,025 = 615,605; 141,634 + 96,989 + 69,277 = 307,900; PTET 7,011 +
// 4,268 + 4,746 = 16,025 of entity 28,044 + 17,070 + 18,982 = 64,096; IT-112-R min(11,279, 15,920)
// = 11,279. Totals are the server's, never summed in the browser (ADR-050). No "$" in the tables.

export type Frame = "a" | "b" | "c" | "d" | "e";
export const FRAMES: readonly Frame[] = ["a", "b", "c", "d", "e"];

export const COPY = {
  subbar: {
    checkpoints: "☰ Checkpoints",
    sync: "Out of sync",
    form: "2025 Form 1040",
    client: "Jonah & Claire Feld",
    state: "In review · Manager",
    assistant: "Assistant",
  },
  tabs: ["Overview", "Intake 2", "Review 37", "Issues 3", "Activity"],
  subtabs: ["Worksheets", "Residency & states", "2-Year Comparison"],
  control: ["Residency", "Allocation", "Credits"],
  title: "New York residency & state allocation",
  excel: "Open in Excel",
  residencyHeader: "Residency facts",
  allocationHeader: "State allocation · 2025",
  askTitle: "Which residency applies for 2025?",
  recommended: "Recommended",
  askClient: "Ask the client…",
  confirm: "Confirm residency",
  confirmed: "Residency confirmed by Samuel Ito · Sep 15, 4:55 PM",
  actionRequired:
    "Action required — the facts point to a domicile change on Jul 1; NYC part-year (IT-360.1)",
  sheetTo: "Claire Feld",
  sheetQuestion: "Which home did your family treat as its main home after July 1, 2025?",
  sheetOptions: ["Brooklyn", "Rhinebeck", "Both"],
  send: "Send",
  loading: "Sourcing by property…",
  table1: "Income by jurisdiction",
  table2: "Credits",
} as const;

export interface Tally {
  key: string;
  label: string;
  value: string;
  tone?: "green" | "amber";
}

export const TALLIES: readonly Tally[] = [
  { key: "agi", label: "NY AGI", value: "615,605" },
  { key: "ridgeline", label: "Ridgeline sourced", value: "tie 307,900", tone: "green" },
  { key: "ptet", label: "PTET credits", value: "16,025" },
  { key: "nyc", label: "NYC resident tax", value: "23,014" },
  { key: "residency", label: "Residency", value: "Review point", tone: "amber" },
];

export interface Fact {
  key: string;
  label: string;
  value: string;
  chip: string;
}

export const FACTS: readonly Fact[] = [
  {
    key: "domicile",
    label: "Domicile (proposed)",
    value: "214 Prospect Park West, Apt 6B, Brooklyn, NY 11215 · co-op owned since 2014",
    chip: "Co-op stmt",
  },
  {
    key: "second_residence",
    label: "Second residence",
    value: "41 Mill Road, Rhinebeck, NY 12572 · bought Jun 6, 2025",
    chip: "Deed",
  },
  {
    key: "days",
    label: "Days in 2025",
    value: "New York City 281 · Rhinebeck (Dutchess County) 72 · outside New York 12 · total 365",
    chip: "Answers Sep 9",
  },
  {
    key: "work_location",
    label: "Claire's work location",
    value: 'Mercer Hill Health, Manhattan (W-2 box 20 "NYC")',
    chip: "W-2",
  },
  {
    key: "voter_registration",
    label: "Voter registration",
    value: "Kings County (both spouses)",
    chip: "Voter record",
  },
  {
    key: "drivers_licenses",
    label: "Driver's licenses",
    value: "Brooklyn address (both)",
    chip: "Licenses",
  },
  {
    key: "trigger",
    label: "What triggered the question",
    value: "Halvard Securities mailing address changed to Rhinebeck on Jul 1, 2025",
    chip: "1099 p. 1",
  },
];

export interface Option {
  key: "full_year_nys_nyc" | "full_year_nys_part_year_nyc" | "part_year_nys";
  title: string;
  detail: string;
}

export const OPTIONS: readonly Option[] = [
  {
    key: "full_year_nys_nyc",
    title: "Full-year New York State and New York City residents",
    detail:
      "Proposed by Accrued Agent. Brooklyn remained the family home: work, voting, licenses and 281 NYC days. IT-201 with NYC resident tax 23,014.",
  },
  {
    key: "full_year_nys_part_year_nyc",
    title: "Full-year New York State residents; part-year NYC residents from Jul 1",
    detail:
      "Only if the family moved its home to Rhinebeck. IT-201 + IT-360.1; CCH Axcess recomputes the NYC tax after import.",
  },
  {
    key: "part_year_nys",
    title: "Part-year New York State residents",
    detail: "Only if domicile left New York State. Uses IT-203. Not supported by these facts.",
  },
];

export const INCOME_COLUMNS = [
  "Item",
  "Federal",
  "New York (resident)",
  "NYC (resident)",
  "Illinois source",
  "Colorado source",
] as const;

/** Income by jurisdiction: [item, federal, NY, NYC, IL, CO]; "—" where none. */
export const INCOME: readonly (readonly [string, string, string, string, string, string])[] = [
  ["Wages — Claire, Mercer Hill Health", "268,400", "268,400", "268,400", "—", "—"],
  ["Taxable interest", "6,910", "6,910", "6,910", "—", "—"],
  ["Ordinary dividends", "14,820", "14,820", "14,820", "—", "—"],
  ["Ridgeline rental (Schedule E)", "307,900", "307,900", "307,900", "141,634", "96,989"],
  ["NY addition — other states' bond interest", "—", "1,550", "1,550", "—", "—"],
  [
    "NY additions — IT-225 A-219 + A-220 (PTET credits claimed)",
    "—",
    "16,025",
    "16,025",
    "—",
    "—",
  ],
  ["TOTAL", "598,030", "615,605", "615,605", "141,634", "96,989"],
];

export const CREDIT_COLUMNS = [
  "State",
  "Source income",
  "PTET rate",
  "Entity PTET",
  "Feld share (25%)",
  "Where it goes",
] as const;

export const CREDITS: readonly (readonly [string, string, string, string, string, string])[] = [
  [
    "Illinois",
    "141,634",
    "4.95%",
    "28,044",
    "7,011",
    "IL-1040 PTE credit = IL tax 7,011 → 0 due; also in NY resident credit base",
  ],
  [
    "Colorado",
    "96,989",
    "4.40%",
    "17,070",
    "4,268",
    "DR 0104PN credit (covers CO tax); also in NY resident credit base",
  ],
  ["New York", "69,277", "6.85%", "18,982", "4,746", "IT-653 refundable credit on IT-201"],
  ["TOTAL", "307,900", "", "64,096", "16,025", ""],
];

export const NOTES: readonly (readonly [string, string])[] = [
  [
    "NY resident credit (IT-112-R)",
    "lesser of 11,279 (IL 7,011 + CO 4,268) and 15,920 (NY tax 41,070 × 238,623 ÷ 615,605) = 11,279",
  ],
  [
    "NY add-backs (IT-225)",
    "A-219 4,746 + A-220 11,279 = 16,025, added in 2025, the year the credits are claimed",
  ],
  ["NYC", "No credit for other-state taxes against the NYC resident tax"],
  [
    "Federal",
    "Ridgeline paid no PTET in 2025: its TY2024 Illinois PTET was paid through 2024 estimates (deducted on the 2024 return), and the TY2025 IL, CO and NY PTET (64,096) was paid Mar 12, 2026, so Ridgeline deducts it on its 2026 return. Box 2 (307,900) carries no PTET deduction.",
  ],
];

/** Where a table cell deep-links: the TXI-01 field it shows, or TXI-02's treatment 7. */
export const CELL_LINKS: Readonly<Record<string, string>> = {
  "Illinois source": "TXI-01:il1040_schnr",
  "New York (resident)": "TXI-01:it201",
  "NYC (resident)": "TXI-01:it201",
  PTET: "TXI-02:7",
};
