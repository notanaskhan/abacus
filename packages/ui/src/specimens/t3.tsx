import { type JSX, useState } from "react";
import { Picker } from "../components/inputs";
import { DataGrid } from "../data/data-grid";
import { EvidenceTable } from "../data/evidence";
import { FieldBlock } from "../data/fields";
import type { TableColumn, TableRow } from "../data/types";
import {
  EvidenceTriad,
  type TriadDoc,
  type TriadGroup,
  type TriadPreset,
  TriadFooter,
  TriadSheetBar,
  TriadTree,
} from "../templates/evidence-triad";
import { SourceViewer } from "../viewer/source-viewer";
import type { ViewerFile } from "../viewer/types";
import guards from "../../scope-guards.gen.json";
import { SearchField } from "../components/inputs";
import { amount } from "../format";
import {
  FELD_DOCS,
  FELD_LEADSHEETS,
  FELD_RETURN,
  LEADSHEET_COLUMNS,
  feldRegions,
  feldWorksheets,
  leadsheetMatch,
} from "./feld-t3";
import { Artboard } from "./portal";
import { FELD, FIRM, STAFF } from "./seed-figures";
import { FORM_PAGE_PNG } from "./viewer-pages";

// T3 EvidenceTriad (F-05-T53; T3 handoff, Wave 0 Foundations #t3): the Jonah & Claire Feld 2025
// Form 1040 in the three presets, states T3a to T3e. Every board is live: hover a worksheet field
// or a box on the page and both light together; open documents from the tree, approve one or raise
// an issue, switch sheet tabs, and pick a preset from the ViewToggle. The figures are the T3
// handoff's (feld-t3.ts); TPL-03 (F-05-T54) draws the seed's.

const PERSON = { kind: "human", name: STAFF.samuel } as const;
const TOOLBAR = {
  nav: guards.nav.map((label) => ({ label })),
  firm: FIRM,
  firmShort: "Brightwater",
  firmTitle: "Brightwater Hale LLP",
  active: "Tax Returns",
} as const;

type DocKey = keyof typeof FELD_DOCS;

const PAGE = { n: 1, width_pt: 612, height_pt: 792, rotation: 0, src: FORM_PAGE_PNG } as const;

/** The worksheet field each box feeds: the linked figure the viewer shows beside the region. */
function viewerFile(doc: DocKey, mismatch: boolean): ViewerFile {
  const fields = feldWorksheets(mismatch).flatMap((b) => b.rows);
  return {
    name: FELD_DOCS[doc].name,
    pages: [PAGE],
    regions: feldRegions(doc).map((r) => {
      const f = fields.find((x) => x.match === r.match);
      return {
        match: r.match,
        page: 1,
        rects: [r.bbox],
        ...(f === undefined || f.value === null
          ? {}
          : { linkedFigure: { label: f.label, value: `$${amount(f.value, "whole").text}` } }),
      };
    }),
  };
}

/** The viewer's ⋯ menu: Download lives here, never in the bar. */
const VIEWER_MENU = [
  { label: "Download", onSelect: () => undefined },
  { label: "Open in Files", onSelect: () => undefined },
];

interface DocState {
  approved?: boolean;
  flags?: number;
}

const TREE = (state: Readonly<Record<string, DocState>>): readonly TriadGroup[] => {
  const doc = (id: string, label: string, requested = false): TriadDoc => ({
    id,
    label,
    ...(requested ? { requested } : {}),
    ...(state[id]?.approved === true ? { approved: true } : {}),
    ...((state[id]?.flags ?? 0) > 0 ? { flags: state[id]?.flags ?? 0 } : {}),
  });
  return [
    {
      id: "inc",
      label: "Income",
      subs: [
        { id: "wages", label: "Wages", docs: [doc("w2", FELD_DOCS.w2.label)] },
        {
          id: "intdiv",
          label: "Interest and dividends",
          docs: [doc("c1099", FELD_DOCS.c1099.label)],
        },
      ],
    },
    {
      id: "ded",
      label: "Deductions",
      subs: [
        { id: "mort", label: "Mortgage interest", docs: [doc("m1098", FELD_DOCS.m1098.label)] },
        { id: "ptaxs", label: "Property tax", docs: [doc("ptax", "Property tax bill", true)] },
        {
          id: "gifts",
          label: "Charitable gifts",
          docs: [doc("char", "Charitable receipts", true)],
        },
      ],
    },
  ];
};

// The 2-Year Comparison: the T3 handoff's six lines with the change the server would send.
const CMP_COLUMNS: readonly TableColumn[] = [
  { key: "item", header: "Line", type: "label" },
  { key: "py", header: "2024", width: 88, format: "whole" },
  { key: "cy", header: "2025", width: 88, format: "whole" },
  { key: "d", header: "Change", type: "variance", width: 160, format: "whole" },
];
const cmp = (
  id: string,
  label: string,
  py: string,
  cy: string,
  d: string,
  ratio: string,
  th: string,
): TableRow => ({
  id,
  label,
  cells: {
    py: { value: py },
    cy: { value: cy },
    d: { value: d, variance: { value: d, ratio, threshold: th } },
  },
});
const CMP_ROWS: readonly TableRow[] = [
  cmp("c1a", "Wages", "136900", "142600", "5700", "0.0416", "10000"),
  cmp("c2b", "Taxable interest", "618", "1312", "694", "1.1230", "500"),
  cmp("c3b", "Ordinary dividends", "4402", "4812", "410", "0.0931", "1000"),
  cmp("c7", "Capital gain distributions", "2950", "1205", "-1745", "-0.5915", "1000"),
  cmp("ca8", "Mortgage interest", "18910", "18265", "-645", "-0.0341", "1000"),
  cmp("c25", "Federal tax withheld", "20118", "21390", "1272", "0.0632", "2500"),
];

interface Board {
  id: string;
  badge: string;
  name: string;
  note: string;
  preset: TriadPreset;
  sheet: string;
  docs: Readonly<Record<string, DocState>>;
  mismatch?: boolean;
  loading?: boolean;
}

const BASE: Readonly<Record<string, DocState>> = { w2: { approved: true } };

const BOARDS: readonly Board[] = [
  {
    id: "t3a",
    badge: "T3a",
    name: "Prepare · unapproved",
    note: "Tree 214 · viewer 571 · sheet 571. The 1099’s ✓ is neutral, with no count",
    preset: "prepare",
    sheet: "Worksheets",
    docs: BASE,
  },
  {
    id: "t3b",
    badge: "T3b",
    name: "Review · approved",
    note: "452 × 3 on the Leadsheets tab. The 1099 is approved: ✓ 1 in ink",
    preset: "review",
    sheet: "Leadsheets",
    docs: { ...BASE, c1099: { approved: true } },
  },
  {
    id: "t3c",
    badge: "T3c",
    name: "Prepare · flagged",
    note: "An issue raised on the 1099 shows ⚑ 1 in amber",
    preset: "prepare",
    sheet: "Worksheets",
    docs: { ...BASE, c1099: { flags: 1 } },
  },
  {
    id: "t3d",
    badge: "T3d",
    name: "Two-pane · mismatch",
    note: "Sheet beside a 490 viewer. Line 3b reads 4,182 against 4,812.37 on the 1099",
    preset: "two",
    sheet: "Worksheets",
    docs: BASE,
    mismatch: true,
  },
  {
    id: "t3e",
    badge: "T3e",
    name: "Review · loading pages",
    note: "Header and toolbar are real; the pages are skeleton blocks until a document is picked",
    preset: "review",
    sheet: "Worksheets",
    docs: BASE,
    loading: true,
  },
];

const SHEETS = [
  { label: "Worksheets", icon: "panels-top-left" as const },
  { label: "Leadsheets", icon: "layers" as const },
  { label: "2-Year Comparison", icon: "chart-column" as const },
];

function Triad({ board }: { board: Board }): JSX.Element {
  const [preset, setPreset] = useState<TriadPreset>(board.preset);
  const [sheet, setSheet] = useState(board.sheet);
  const [sel, setSel] = useState<string>("c1099");
  const [docs, setDocs] = useState<Readonly<Record<string, DocState>>>(board.docs);
  const [treeQuery, setTreeQuery] = useState("");
  const [fieldQuery, setFieldQuery] = useState("");
  const [loading, setLoading] = useState(board.loading === true);
  const file = sel in FELD_DOCS ? (sel as DocKey) : null;
  const current = docs[sel] ?? {};
  const patch = (next: DocState): void => {
    setDocs((d) => ({ ...d, [sel]: { ...d[sel], ...next } }));
  };
  const q = fieldQuery.trim().toLowerCase();
  const worksheets = feldWorksheets(board.mismatch === true)
    .map((b) => ({
      ...b,
      rows: b.rows.filter((r) => q === "" || r.label.toLowerCase().includes(q)),
    }))
    .filter((b) => b.rows.length > 0);

  return (
    <Artboard id={board.id} badge={board.badge} name={board.name} note={board.note}>
      <EvidenceTriad
        embedded
        height={860}
        toolbar={TOOLBAR}
        record={{
          title: FELD_RETURN,
          context: FELD,
          state: "In review · Manager",
          sync: "synced",
          syncDate: "Sep 11",
        }}
        tabs={{
          label: "Return",
          active: "Review",
          options: [
            "Overview",
            { label: "Intake", count: 2 },
            { label: "Review", count: 37 },
            { label: "Issues", count: 4, bad: true },
            "Activity",
          ],
        }}
        preset={preset}
        onPreset={setPreset}
        tree={{
          title: "Review",
          search: (
            <SearchField
              label="Search documents"
              placeholder="Search"
              value={treeQuery}
              onChange={setTreeQuery}
              className={preset === "review" ? "w-[120px]" : "w-[28px]"}
            />
          ),
          body: (
            <TriadTree
              groups={TREE(docs)}
              selected={sel}
              query={treeQuery}
              onSelect={(d) => {
                setSel(d.id);
                setLoading(false);
              }}
            />
          ),
          footer: (stacked) => (
            <TriadFooter
              actor={PERSON}
              approved={current.approved === true}
              disabled={file === null}
              stacked={stacked}
              onApprove={() => {
                patch({ approved: true });
              }}
              onIssue={() => {
                patch({ flags: (current.flags ?? 0) + 1 });
              }}
            />
          ),
        }}
        viewer={
          file === null ? (
            <SourceViewer
              file={{
                name:
                  TREE(docs)
                    .flatMap((g) => g.subs.flatMap((s) => s.docs))
                    .find((d) => d.id === sel)?.label ?? "",
                pages: [],
                regions: [],
              }}
              status="not_previewable"
            />
          ) : (
            <SourceViewer
              file={viewerFile(file, board.mismatch === true)}
              loading={loading}
              menu={VIEWER_MENU}
            />
          )
        }
        sheet={{
          tabs: SHEETS,
          active: sheet,
          onTab: setSheet,
          bar: (
            <TriadSheetBar
              query={fieldQuery}
              onQuery={setFieldQuery}
              picker={
                <Picker
                  label="Taxpayer"
                  variant="white"
                  options={[{ value: "feld", label: FELD }]}
                  defaultValue="feld"
                />
              }
            />
          ),
          children:
            sheet === "Worksheets" ? (
              <div data-triad-sheet="worksheets" className="flex flex-col gap-[16px] pb-[12px]">
                {worksheets.map((b) => (
                  <FieldBlock
                    key={b.title}
                    title={b.title}
                    meta={b.meta}
                    rows={b.rows}
                    valueWidth={140}
                  />
                ))}
              </div>
            ) : sheet === "Leadsheets" ? (
              <EvidenceTable
                label="Leadsheet"
                grammar="leadsheet"
                card={false}
                blocks={FELD_LEADSHEETS.map((b) => ({ ...b, columns: LEADSHEET_COLUMNS }))}
                rowMatch={leadsheetMatch}
              />
            ) : (
              <DataGrid label="2-Year Comparison" columns={CMP_COLUMNS} rows={CMP_ROWS} />
            ),
        }}
      />
    </Artboard>
  );
}

/** One artboard on its own (the tests render a single board). */
export function T3Board({ id }: { id: string }): JSX.Element | null {
  const board = BOARDS.find((b) => b.id === id);
  return board === undefined ? null : <Triad board={board} />;
}

export function T3Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {BOARDS.map((b) => (
        <Triad key={b.id} board={b} />
      ))}
    </div>
  );
}
