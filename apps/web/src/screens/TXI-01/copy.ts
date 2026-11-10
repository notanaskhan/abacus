// TXI-01 copy and the IT-201 the artboards draw (T-04-T22; handoff TXI-01 spec, verbatim). The
// figures tie: line 33 615,605 = 598,030 + 1,550 + 16,025; line 37 599,555 = 615,605 − 16,050;
// tax after credits 52,805 = (41,070 − 11,279) + 23,014; payments 51,536 = 17,400 + 9,390 +
// 20,000 + 4,746; owed 1,269. Derived lines are code's (recomputed on every input change).

export type Frame = "a" | "b" | "c" | "d" | "e" | "f" | "g";
export const FRAMES: readonly Frame[] = ["a", "b", "c", "d", "e", "f", "g"];

export interface Field {
  key: string;
  label: string;
  tsj: "T" | "S" | "J";
  value: string;
  prior?: string; // the struck prior value of an updated field
  note?: string;
  chips?: string[];
  flag?: string;
  added?: boolean; // a green "+": created by the agent this year
  cited?: string; // the source region it lights (box 18A on page 3)
  engine?: boolean; // computed by the engine of record, not by code
}
export interface Section {
  key: string;
  title: string;
  fields: Field[];
}

export const IT201: readonly Section[] = [
  {
    key: "residency",
    title: "Residency",
    fields: [
      {
        key: "fs",
        label: "Filing status",
        tsj: "J",
        value: "Married filing jointly",
        note: "from Form 1040",
        chips: ["✓ KO"],
      },
      {
        key: "nys",
        label: "New York State resident",
        tsj: "J",
        value: "Full year",
        note: "from residency answers (Claire Feld, Sep 9)",
        flag: "⚑ SI",
      },
      {
        key: "nyc",
        label: "New York City resident (line D2)",
        tsj: "J",
        value: "12 months",
        note: "domicile 214 Prospect Park West, Brooklyn",
        flag: "⚑ SI",
      },
    ],
  },
  {
    key: "income",
    title: "Income and additions",
    fields: [
      {
        key: "19",
        label: "Federal adjusted gross income (line 19)",
        tsj: "J",
        value: "598,030",
        note: "from Form 1040 line 11",
        chips: ["✓ KO", "✓ OB"],
      },
      {
        key: "20",
        label: "Interest income on other states' bonds (line 20)",
        tsj: "T",
        value: "1,550",
        prior: "0",
        note: "from Box 18A of the Ridgeline K-1 statement: 0% New York obligations",
        chips: ["✓ SI 9:31"],
        cited: "18A",
      },
      {
        key: "22",
        label: "Other New York additions — IT-225 (line 22)",
        tsj: "T",
        value: "16,025",
        note: "A-219 NY PTET credit 4,746 + A-220 IL/CO PTE taxes 11,279 (Ridgeline PTET statement)",
      },
      {
        key: "33",
        label: "New York adjusted gross income (line 33)",
        tsj: "J",
        value: "615,605",
        prior: "614,055",
        note: "line 19 + line 20 + line 22",
      },
    ],
  },
  {
    key: "deductions",
    title: "Deductions",
    fields: [
      {
        key: "34",
        label: "Standard or itemized (line 34)",
        tsj: "J",
        value: "16,050",
        chips: ["✓ OB"],
      },
      {
        key: "37",
        label: "Taxable income (line 37)",
        tsj: "J",
        value: "599,555",
        note: "615,605 − 16,050",
      },
    ],
  },
  {
    key: "tax",
    title: "Tax",
    fields: [
      {
        key: "39",
        label: "New York State tax (line 39)",
        tsj: "J",
        value: "41,070",
        note: "from CCH Axcess",
        engine: true,
      },
      {
        key: "112r",
        label: "Resident credit (IT-112-R)",
        tsj: "J",
        value: "11,279",
        note: "Jonah's share of IL PTET 7,011 + CO PTET 4,268",
      },
      {
        key: "47a",
        label: "NYC resident tax (line 47a)",
        tsj: "J",
        value: "23,014",
        note: "from CCH Axcess",
        flag: "⚑ SI",
        engine: true,
      },
    ],
  },
  {
    key: "payments",
    title: "Payments and credits",
    fields: [
      {
        key: "72",
        label: "NYS tax withheld (line 72)",
        tsj: "S",
        value: "17,400",
        note: "from Box 17 of the W-2 (Mercer Hill Health)",
        chips: ["✓ KO", "✓ OB"],
      },
      {
        key: "73",
        label: "NYC tax withheld (line 73)",
        tsj: "S",
        value: "9,390",
        note: "from Box 19 of the W-2",
        chips: ["✓ KO", "✓ OB"],
      },
      {
        key: "75",
        label: "Estimated payments and IT-370 (line 75)",
        tsj: "J",
        value: "20,000",
        note: "4 × 3,500 per organizer + IT-370 6,000 (Apr 14)",
        flag: "⚑ KO",
      },
      {
        key: "653",
        label: "PTET credit (IT-653)",
        tsj: "T",
        value: "4,746",
        note: "New this year — Ridgeline elected New York PTET for 2025",
        added: true,
      },
      {
        key: "owed",
        label: "Amount owed",
        tsj: "J",
        value: "1,269",
        note: "52,805 tax after credits − 51,536 payments; interest from Apr 15",
      },
    ],
  },
];

export const W2 = [
  ["Box 1 Wages", "268,400"],
  ["Box 2 Federal tax withheld", "52,860"],
  ["Box 17 State tax", "17,400"],
  ["Box 19 Local tax (NYC)", "9,390"],
] as const;

export const TREE = [
  { key: "w2", title: "Wages (W-2) · Mercer Hill Health", tsj: "S" },
  { key: "schE", title: "Sch E p 2 · Ridgeline Property Partners, LP", tsj: "T", edited: true },
  { key: "it201", title: "IT-201 · resident + NYC", tsj: "J", edited: true },
  { key: "it653", title: "IT-653 · PTET credit", tsj: "T", added: true },
] as const;

export const COPY = {
  title: "2025 Form 1040",
  client: "Jonah & Claire Feld",
  sync: "Out of sync",
  toggle: ["Documents", "Worksheets"] as const,
  footer:
    "IT-203 is not used — it appears only if New York State residency becomes part-year (see Residency).",
  search: "Search fields",
  picker: "IT-201",
  tsjAll: "TSJ for all items J",
  edit: "Edit",
  reason: "Reason for the change",
  save: "Save",
  reasonRequired: "A reason is required to change a field",
  provenance:
    "Updated Sep 14, 9:31 AM · 0 → 1,550 · Set by Samuel Ito — approved Accrued Agent proposal (checkpoint 'K-1 box 18A')",
  signedOff: "Signed off · SI 9:52 AM",
  recomputed: "Recomputed by CCH Axcess after import",
  it3601: "IT-360.1 · change of resident status",
  viewer: "Ridgeline_2025_K1_Statement_p3.pdf",
  box18a: "Box 18A · 1,550",
} as const;
