import type { FieldItem } from "../data/fields";
import type { TableColumn, TableRow } from "../data/types";
import { matchIdOf } from "../tracing/match-store";
import type { MatchId } from "../tracing/types";

// The T3 evidence triad's worksheet and leadsheet lines on the Jonah & Claire Feld 2025 Form 1040,
// word for word from the T3 handoff (Wave 0 Foundations `#t3`): the frame's own figures, which
// foot (seed-figures FOOTINGS). TPL-03 (F-05-T54) draws the seed's Feld figures instead. Every
// match id is a document-text locator on the source the line was read from (INV-2): the field,
// the leadsheet line and the viewer's region share it.

export const FELD_RETURN = "2025 Form 1040";

/** The three source documents with files, and where each value sits on them. */
export const FELD_DOCS = {
  w2: {
    id: "feld-w2-2025",
    name: "Lakeview Medical Group W-2 2025.pdf",
    label: "Lakeview Medical W-2",
  },
  c1099: {
    id: "feld-1099-2025",
    name: "2025 Composite 1099 — Brokerage.pdf",
    label: "Brightline 1099",
  },
  m1098: {
    id: "feld-1098-2025",
    name: "Prairie State Bank 1098 2025.pdf",
    label: "Prairie State 1098",
  },
} as const;

type Doc = keyof typeof FELD_DOCS;

/** A box on page 1 of a source document. The bbox is the box's place on the page, in points. */
const BOXES: Record<string, { doc: Doc; bbox: readonly [number, number, number, number] }> = {
  "w2:1": { doc: "w2", bbox: [306, 96, 450, 120] },
  "w2:2": { doc: "w2", bbox: [450, 96, 594, 120] },
  // The 1099-DIV boxes sit where the E5 viewer specimen draws them (specimens/viewer.tsx).
  "1099:div-1a": { doc: "c1099", bbox: [294, 79, 441, 120] },
  "1099:div-1b": { doc: "c1099", bbox: [294, 120, 441, 161] },
  "1099:div-2a": { doc: "c1099", bbox: [294, 161, 441, 202] },
  "1099:div-7": { doc: "c1099", bbox: [294, 326, 441, 367] },
  "1099:int-1": { doc: "c1099", bbox: [294, 420, 441, 461] },
  "1098:1": { doc: "m1098", bbox: [306, 96, 450, 120] },
};

/** The match id of a box: the source's document-text locator. */
export function feldBox(key: string): MatchId {
  const box = BOXES[key];
  if (box === undefined) throw new Error(`no box ${key}`);
  return matchIdOf({
    kind: "document_text",
    evidence_version_id: FELD_DOCS[box.doc].id,
    page: 1,
    bbox: box.bbox,
  });
}

/** The boxes on one document: the viewer's regions. */
export function feldRegions(
  doc: Doc,
): readonly { key: string; match: MatchId; bbox: readonly [number, number, number, number] }[] {
  return Object.entries(BOXES)
    .filter(([, b]) => b.doc === doc)
    .map(([key, b]) => ({ key, match: feldBox(key), bbox: b.bbox }));
}

const C1 = "2025 Composite 1099 — Brokerage.pdf · page 1 · ";
const W2 = "Lakeview Medical Group W-2 2025.pdf · page 1 · box ";
const M8 = "Prairie State Bank 1098 2025.pdf · page 1 · box ";

function field(
  id: string,
  label: string,
  value: string,
  box: string,
  source: string,
  mismatch = false,
): FieldItem {
  return {
    id,
    label,
    value,
    format: "whole",
    match: feldBox(box),
    source,
    ...(mismatch ? { mismatch: true } : {}),
  };
}

/** The Worksheets tab: three blocks of field rows. `mismatch` is T3d (Line 3b reads 4,182). */
export function feldWorksheets(mismatch = false): readonly {
  title: string;
  meta: string;
  rows: readonly FieldItem[];
}[] {
  return [
    {
      title: "Wages",
      meta: "2025",
      rows: [
        field("ws-1a", "Line 1a · Wages", "142600", "w2:1", `${W2}1`),
        field("ws-25a", "Line 25a · Federal tax withheld", "21390", "w2:2", `${W2}2`),
      ],
    },
    {
      title: "Interest and dividends",
      meta: "2025",
      rows: [
        field("ws-2b", "Line 2b · Taxable interest", "1312", "1099:int-1", `${C1}1099-INT box 1`),
        field(
          "ws-3a",
          "Line 3a · Qualified dividends",
          "3960",
          "1099:div-1b",
          `${C1}1099-DIV box 1b`,
        ),
        field(
          "ws-3b",
          "Line 3b · Ordinary dividends",
          mismatch ? "4182" : "4812",
          "1099:div-1a",
          `${C1}1099-DIV box 1a`,
          mismatch,
        ),
        field("ws-sd13", "Schedule D · Line 13", "1205", "1099:div-2a", `${C1}1099-DIV box 2a`),
        field("ws-s3", "Schedule 3 · Line 1", "48", "1099:div-7", `${C1}1099-DIV box 7`),
      ],
    },
    {
      title: "Itemized deductions",
      meta: "2025",
      rows: [
        field("ws-a8a", "Schedule A · Line 8a · Mortgage interest", "18265", "1098:1", `${M8}1`),
      ],
    },
  ];
}

/** The Leadsheets tab: a line-number column, the label and the whole-dollar value. */
export const LEADSHEET_COLUMNS: readonly TableColumn[] = [
  { key: "line", header: "Line", type: "text", width: 52, line: true },
  { key: "label", header: "Description", type: "label" },
  { key: "value", header: "Amount", type: "num" },
];

const line = (
  id: string,
  no: string,
  label: string,
  value: string,
  kind: "item" | "total" = "item",
): TableRow => ({ id, kind, label, cells: { line: { value: no }, value: { value } } });

export const FELD_LEADSHEETS: readonly { id: string; title: string; rows: readonly TableRow[] }[] =
  [
    {
      id: "income",
      title: "Income",
      rows: [
        line("l1a", "1a", "Wages, salaries, tips (W-2, box 1)", "142600"),
        line("l2b", "2b", "Taxable interest", "1312"),
        line("l3b", "3b", "Ordinary dividends", "4812"),
        line("l7", "7", "Capital gain or (loss)", "1205"),
        line("l9", "9", "Total income", "149929", "total"),
      ],
    },
    {
      id: "payments",
      title: "Payments",
      rows: [
        line("l25a", "25a", "Federal income tax withheld, Forms W-2", "21390"),
        line("l26", "26", "Estimated tax payments", "0"),
        line("l33", "33", "Total payments", "21390", "total"),
      ],
    },
  ];

/** The box each leadsheet line was read from. */
const LINE_BOX: Readonly<Record<string, string>> = {
  l1a: "w2:1",
  l2b: "1099:int-1",
  l3b: "1099:div-1a",
  l7: "1099:div-2a",
  l25a: "w2:2",
};

export function leadsheetMatch(row: TableRow): MatchId | undefined {
  const box = LINE_BOX[row.id];
  return box === undefined ? undefined : feldBox(box);
}

/** The footings the T3 figures draw (checked with the specimen footings). */
export const FELD_T3_FOOTINGS = [
  {
    name: "T3 Feld total income (line 9)",
    parts: ["142600", "1312", "4812", "1205"],
    total: "149929",
  },
  { name: "T3 Feld total payments (line 33)", parts: ["21390", "0"], total: "21390" },
] as const;
