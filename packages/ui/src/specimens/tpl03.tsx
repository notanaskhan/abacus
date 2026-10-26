import { type JSX, useState } from "react";
import { cn } from "../cn";
import { IconButton } from "../components/button";
import { Picker, SearchField } from "../components/inputs";
import { Pill } from "../components/pill";
import { Toast } from "../components/toast";
import { EvidenceTable } from "../data/evidence";
import type { TableColumn, TableRow } from "../data/types";
import { amount } from "../format";
import { Icon } from "../icons";
import {
  EvidenceTriad,
  type TriadDoc,
  type TriadGroup,
  type TriadPreset,
  TriadFooter,
  TriadTree,
} from "../templates/evidence-triad";
import { useMatch } from "../tracing/match";
import { createMatchStore, matchIdOf } from "../tracing/match-store";
import type { CitationPayload, MatchId } from "../tracing/types";
import { SourceViewer } from "../viewer/source-viewer";
import type { PtRect, ViewerFile } from "../viewer/types";
import guards from "../../scope-guards.gen.json";
import { Artboard } from "./portal";
import { FELD, FELD_1040_LINES, FELD_K1, FIRM, RIDGELINE, STAFF } from "./seed-figures";
import { FORM_PAGE_PNG } from "./viewer-pages";

// TPL-03 Evidence triad specimen · Feld 1040 review (F-05-T54; Wave 0 - Templates `#tpl03`): the
// T3 frame for Samuel Ito on the Jonah & Claire Feld 2025 Form 1040, drawn from the seed's figures
// (seed-figures FELD_K1, FELD_HALVARD, FELD_1040_LINES; blueprint 01 §9.4, footed in the app's
// seed test). The draft Ridgeline K-1 sits beside the Sch E - K-1 matrix; box 5 and "Interest
// Income $4,600" share one match id, the K-1's document-text locator (INV-2), so they light
// together. Every board is live: hover or click a box or a row, pick a document, switch presets,
// and Approve or Unapprove (the Review count moves 37 to 36 and back).

const PERSON = { kind: "human", name: STAFF.samuel } as const;
const TOOLBAR = {
  nav: guards.nav.map((label) => ({ label })),
  firm: FIRM,
  firmShort: "Brightwater",
  firmTitle: "Brightwater Hale LLP",
  active: "Tax Returns",
} as const;

/** The layout menu, named with each preset's widths (TPL-03 Tabsbar). */
const VIEWS = [
  { v: "review", label: "Review layout · 452 × 3", icon: "columns-3" as const },
  { v: "prepare", label: "Prepare layout · 214 · 571 · 571", icon: "panel-left" as const },
];

// ---- The two documents with files and their boxes ------------------------------------------------

export const K1_FILE = "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf";
const K1_ID = "feld-ridgeline-k1-2025-draft";
export const HALVARD_FILE = "Halvard_2025_Consolidated_1099_Feld.pdf";
const HALVARD_ID = "feld-halvard-1099-2025";

/** A box on page 1 of a document: its place in points, and its match (the C4 locator, INV-2). */
const box = (doc: string, bbox: PtRect): { match: MatchId; bbox: PtRect } => ({
  match: matchIdOf({ kind: "document_text", evidence_version_id: doc, page: 1, bbox }),
  bbox,
});

export const K1_BOXES = {
  box2: box(K1_ID, [294, 326, 441, 346]),
  box5: box(K1_ID, [294, 350, 441, 370]),
  box18a: box(K1_ID, [294, 374, 441, 394]),
  box19a: box(K1_ID, [294, 398, 441, 418]),
} as const;

export const HALVARD_BOXES = {
  div1a: box(HALVARD_ID, [294, 79, 441, 120]),
  div1b: box(HALVARD_ID, [294, 120, 441, 161]),
  int1: box(HALVARD_ID, [294, 420, 441, 461]),
} as const;

const PAGES = [1, 2, 3].map((n) => ({
  n,
  width_pt: 612,
  height_pt: 792,
  rotation: 0 as const,
  src: FORM_PAGE_PNG,
}));

const whole = (v: string): string => amount(v, "whole").text;

export const K1_VIEW: ViewerFile = {
  name: K1_FILE,
  pages: PAGES,
  regions: [
    {
      match: K1_BOXES.box2.match,
      page: 1,
      rects: [K1_BOXES.box2.bbox],
      label: "2 Net rental real estate income",
    },
    {
      match: K1_BOXES.box5.match,
      page: 1,
      rects: [K1_BOXES.box5.bbox],
      label: "5 Interest income",
    },
    {
      match: K1_BOXES.box18a.match,
      page: 1,
      rects: [K1_BOXES.box18a.bbox],
      label: "18A Tax-exempt interest income",
    },
    {
      match: K1_BOXES.box19a.match,
      page: 1,
      rects: [K1_BOXES.box19a.bbox],
      label: "19A Distributions",
    },
  ],
  // The partnership's EIN and the partner's TIN, masked (never a full TIN).
  masks: [
    { id: "k1-ein", page: 1, rect: [92, 118, 220, 134], kind: "ein", display: "••-•••0287" },
    { id: "k1-tin", page: 1, rect: [92, 236, 220, 252], kind: "ssn", display: "•••-••-4417" },
  ],
};

const HALVARD_VIEW: ViewerFile = {
  name: HALVARD_FILE,
  pages: PAGES,
  regions: [
    {
      match: HALVARD_BOXES.div1a.match,
      page: 1,
      rects: [HALVARD_BOXES.div1a.bbox],
      label: "1a Total ordinary dividends",
      linkedFigure: { label: "Form 1040 · Line 3b", value: whole(FELD_1040_LINES.line3b) },
    },
    {
      match: HALVARD_BOXES.div1b.match,
      page: 1,
      rects: [HALVARD_BOXES.div1b.bbox],
      label: "1b Qualified dividends",
      linkedFigure: { label: "Form 1040 · Line 3a", value: whole(FELD_1040_LINES.line3a) },
    },
    {
      match: HALVARD_BOXES.int1.match,
      page: 1,
      rects: [HALVARD_BOXES.int1.bbox],
      label: "1 Interest income (1099-INT)",
    },
  ],
};

/** The viewer's ⋯ menu: Download lives here, never in the bar. */
const VIEWER_MENU = [
  { label: "Download", onSelect: () => undefined },
  { label: "Open in Files", onSelect: () => undefined },
];

// ---- The review tree --------------------------------------------------------------------------

export const K1_DOC = `${RIDGELINE} 2025 K-1 [Draft K-1 · pre-release]`;

interface DocState {
  approved?: boolean;
  flags?: number;
}

/** Documents with no page in this specimen: the viewer names them and shows the page frame. */
const FILES: Readonly<Record<string, ViewerFile>> = { k1: K1_VIEW, halvard: HALVARD_VIEW };

const TREE = (state: Readonly<Record<string, DocState>>): readonly TriadGroup[] => {
  const doc = (id: string, label: string, extra: Partial<TriadDoc> = {}): TriadDoc => ({
    id,
    label,
    ...extra,
    ...(state[id]?.approved === true ? { approved: true } : {}),
    ...((state[id]?.flags ?? 0) > 0
      ? { flags: state[id]?.flags ?? 0, flagsNote: "Opens TAX-06 · Return issues" }
      : {}),
  });
  return [
    {
      id: "general",
      label: "General",
      subs: [
        {
          id: "basic",
          label: "Basic Data",
          docs: [
            doc("py1040", "Feld 2024 Form 1040 (prior year, from CCH Axcess)"),
            doc("c7216", "§7216 consents (use · AI disclosure) — signed Feb 2, 2026"),
          ],
        },
      ],
    },
    {
      id: "income",
      label: "Income",
      subs: [
        {
          id: "w2s",
          label: "Wages, Salaries and Tips (W-2)",
          docs: [doc("w2", "2025 W-2 From Mercer Hill Health [Claire]")],
        },
        {
          id: "intdiv",
          label: "Interest & Dividends (1099-INT, 1099-DIV)",
          docs: [doc("halvard", "Halvard Securities 2025 Consolidated 1099 [Acct ••3318]")],
        },
        {
          id: "sche",
          label: "Sch E, p 2 - Partnership Passthrough (K-1 1065)",
          docs: [doc("k1", K1_DOC, { info: true })],
        },
      ],
    },
    {
      id: "deductions",
      label: "Deductions",
      subs: [
        {
          id: "scha",
          label: "Sch A - Itemized Deductions",
          docs: [
            doc("charity", "2025 Charitable Contributions Summary — Feld"),
            doc("m1098", "2025 Form 1098 — Brooklyn co-op mortgage interest"),
          ],
        },
      ],
    },
    {
      id: "state",
      label: "State",
      subs: [
        {
          id: "ny",
          label: "New York (IT-201, NYC resident)",
          docs: [
            doc("nyc", "2025 NYC resident tax worksheet — Feld", {
              info: true,
              checkable: false,
            }),
          ],
        },
      ],
    },
  ];
};

const allDocs = (groups: readonly TriadGroup[]): readonly TriadDoc[] =>
  groups.flatMap((g) => g.subs.flatMap((s) => s.docs));

// ---- The Sch E - K-1 matrix -------------------------------------------------------------------

interface MatrixRow {
  id: string;
  label: string;
  /** The cell: a formatted value, or `pill` (the K-1 status pill) or `dash` (none). */
  value: string;
  match?: MatchId;
  note?: string;
}

const usd = (v: string): string => `$${whole(v)}`;

/** The K-1 matrix rows, word for word from the TPL-03 spec, figures from FELD_K1. */
export const K1_MATRIX: readonly MatrixRow[] = [
  { id: "type", label: "Entity Type", value: "Partnership" },
  { id: "tsj", label: "Taxpayer/Spouse/Joint", value: "T" },
  { id: "fs", label: "Federal/State", value: "F" },
  { id: "passive", label: "Passive/Nonpassive", value: "Passive" },
  { id: "mp", label: "Material Participation", value: "No" },
  { id: "final", label: "Final-Year K-1", value: "No" },
  { id: "status", label: "K-1 status", value: "pill" },
  { id: "obi", label: "Ordinary Business Income", value: usd("0") },
  {
    id: "rental",
    label: "Net Rental Real Estate Income",
    value: usd(FELD_K1.box2),
    match: K1_BOXES.box2.match,
  },
  { id: "gp", label: "Guaranteed Payments", value: "dash" },
  {
    id: "interest",
    label: "Interest Income",
    value: usd(FELD_K1.box5),
    match: K1_BOXES.box5.match,
  },
  {
    id: "taxexempt",
    label: "Tax-Exempt Interest",
    value: usd(FELD_K1.box18a),
    match: K1_BOXES.box18a.match,
  },
  { id: "divs", label: "Ordinary Dividends", value: usd("0") },
  { id: "qbi", label: "Section 199A Qualified Business Income", value: usd(FELD_K1.box2) },
  {
    id: "dist",
    label: "Distributions — Cash",
    value: usd(FELD_K1.box19a),
    match: K1_BOXES.box19a.match,
  },
  { id: "begin", label: "Beginning Capital Account", value: usd(FELD_K1.beginningCapital) },
  { id: "contrib", label: "Capital Contributed", value: usd(FELD_K1.capitalContributed) },
  {
    id: "ending",
    label: "Ending Capital Account",
    value: usd(FELD_K1.endingCapital),
    note: "Ridgeline M-2 is off 6,200 — Item L will change",
  },
];

const NO_MATCH = "" as MatchId;

function MatrixLine({ row }: { row: MatrixRow }): JSX.Element {
  const { lit, bind, pin } = useMatch(row.match ?? NO_MATCH, "row");
  const events = row.match === undefined ? {} : bind;
  return (
    <li
      {...events}
      data-k1-row={row.id}
      onClick={(event) => {
        if (row.match !== undefined) pin(event.currentTarget);
      }}
      className={cn(
        "flex min-h-[41px] flex-col justify-center px-[14px] py-[6px] text-body hairline-t",
        "transition-[background-color] duration-[360ms]",
        lit && "bg-match-bg",
      )}
    >
      <span className="flex items-center gap-[8px]">
        <span className={cn("min-w-0 flex-1", lit && "font-medium")}>{row.label}</span>
        {row.note !== undefined && (
          <Icon name="flag" size={12} aria-label="Flagged" className="flex-none text-amber" />
        )}
        {row.value === "pill" ? (
          <Pill variant="amber" size="sm">
            Draft K-1 · pre-release
          </Pill>
        ) : row.value === "dash" ? (
          <span className="text-ink-4">—</span>
        ) : (
          <span className="tabular-nums">{row.value}</span>
        )}
      </span>
      {row.note !== undefined && (
        <span className="pt-[2px] text-meta text-amber-ink">{row.note}</span>
      )}
    </li>
  );
}

function K1Matrix(): JSX.Element {
  return (
    <section data-tpl03="k1-matrix" aria-label="Sch E - K-1" className="flex flex-col">
      <header className="flex min-h-[41px] items-center gap-[8px] bg-band-hd px-[14px] text-body font-medium">
        <span className="flex-1">K-1 Entities</span>
        <span>{RIDGELINE.toUpperCase()}</span>
      </header>
      <ul className="flex flex-col">
        {K1_MATRIX.map((row) => (
          <MatrixLine key={row.id} row={row} />
        ))}
      </ul>
    </section>
  );
}

// ---- The Form 1040 leadsheet (Prepare preset) --------------------------------------------------

const LINE_COLUMNS: readonly TableColumn[] = [
  { key: "label", header: "Line", type: "label" },
  { key: "value", header: "Amount", type: "num" },
];

const line = (id: string, label: string, value: string): TableRow => ({
  id,
  label,
  cells: { value: { value } },
});

export const FORM_1040_BLOCKS = [
  {
    id: "interest",
    title: "2. Interest",
    columns: LINE_COLUMNS,
    rows: [
      line("2a", "2a Tax-exempt interest", FELD_1040_LINES.line2a),
      line("2b", "2b Taxable interest", FELD_1040_LINES.line2b),
    ],
  },
  {
    id: "dividends",
    title: "3. Dividends",
    columns: LINE_COLUMNS,
    rows: [
      line("3a", "3a Qualified dividends", FELD_1040_LINES.line3a),
      line("3b", "3b Ordinary dividends", FELD_1040_LINES.line3b),
    ],
  },
];

/** 1099-DIV box 1a feeds line 3b and box 1b line 3a (the Prepare preset's cross-highlight). */
const LINE_MATCH: Readonly<Record<string, MatchId>> = {
  "3b": HALVARD_BOXES.div1a.match,
  "3a": HALVARD_BOXES.div1b.match,
};

// ---- The boards ---------------------------------------------------------------------------------

interface Board {
  id: string;
  badge: string;
  name: string;
  note: string;
  preset: TriadPreset;
  selected: string;
  docs: Readonly<Record<string, DocState>>;
  /** Lit (pinned) when the board opens. */
  lit?: MatchId;
  loading?: boolean;
}

/** E0: the W-2 and the Halvard 1099 approved; one issue open on the draft K-1. */
const E0_DOCS: Readonly<Record<string, DocState>> = {
  w2: { approved: true },
  halvard: { approved: true },
  k1: { flags: 1 },
};

export const REVIEW_COUNT = 37;
const E0_APPROVED = Object.values(E0_DOCS).filter((d) => d.approved === true).length;

const BOARDS: readonly Board[] = [
  {
    id: "tpl-03a",
    badge: "TPL-03a",
    name: "Review preset",
    note: "The draft Ridgeline K-1 selected; box 5 lights with Interest Income",
    preset: "review",
    selected: "k1",
    docs: E0_DOCS,
    lit: K1_BOXES.box5.match,
  },
  {
    id: "tpl-03b",
    badge: "TPL-03b",
    name: "Prepare preset",
    note: "Halvard 1099: boxes 1a and 1b light lines 3b and 3a",
    preset: "prepare",
    selected: "halvard",
    docs: E0_DOCS,
    lit: HALVARD_BOXES.div1a.match,
  },
  {
    id: "tpl-03c",
    badge: "TPL-03c",
    name: "Approved",
    note: "✓ 1 on the row, Review 36, Unapprove in the footer",
    preset: "review",
    selected: "k1",
    docs: { ...E0_DOCS, k1: { flags: 1, approved: true } },
    lit: K1_BOXES.box5.match,
  },
  {
    id: "tpl-03d",
    badge: "TPL-03d",
    name: "Flagged",
    note: "⚑ 1 on the row opens the issue in TAX-06",
    preset: "review",
    selected: "k1",
    docs: E0_DOCS,
    lit: K1_BOXES.box5.match,
  },
  {
    id: "tpl-03e",
    badge: "TPL-03e",
    name: "Loading pages",
    note: "Gray page skeleton",
    preset: "review",
    selected: "k1",
    docs: E0_DOCS,
    loading: true,
  },
];

const SHEETS = [
  { label: "Worksheets", icon: "panels-top-left" as const },
  { label: "Leadsheets", icon: "layers" as const },
  { label: "2-Year Comparison", icon: "chart-column" as const },
];

const PICKS = [
  { value: "k1", label: "Sch E - K-1" },
  { value: "1040", label: "Form 1040" },
];

function Tpl03({ board }: { board: Board }): JSX.Element {
  const [preset, setPreset] = useState<TriadPreset>(board.preset);
  const [sheet, setSheet] = useState("Leadsheets");
  const [pick, setPick] = useState(board.selected === "halvard" ? "1040" : "k1");
  const [sel, setSel] = useState(board.selected);
  const [docs, setDocs] = useState<Readonly<Record<string, DocState>>>(board.docs);
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [store] = useState(() => {
    const s = createMatchStore<CitationPayload>();
    if (board.lit !== undefined) s.togglePin(board.lit, null);
    return s;
  });
  const tree = TREE(docs);
  const current = docs[sel] ?? {};
  const approvedCount = Object.values(docs).filter((d) => d.approved === true).length;
  // E0 has two documents approved; each one approved here moves Review down by one (37 → 36).
  const review = REVIEW_COUNT - (approvedCount - E0_APPROVED);
  const label = allDocs(tree).find((d) => d.id === sel)?.label ?? "";
  const file = FILES[sel] ?? { name: label, pages: PAGES.slice(0, 1), regions: [] };
  const patch = (next: DocState): void => {
    setDocs((d) => ({ ...d, [sel]: { ...d[sel], ...next } }));
  };

  return (
    <Artboard id={board.id} badge={board.badge} name={board.name} note={board.note}>
      <div className="relative">
        <EvidenceTriad
          embedded
          height={860}
          store={store}
          toolbar={TOOLBAR}
          record={{
            title: "2025 Form 1040",
            context: FELD,
            state: "In review · Manager",
            sync: "synced",
            syncDate: "Sep 10",
          }}
          tabs={{
            label: "Return",
            active: "Review",
            options: [
              "Overview",
              { label: "Intake", count: 2 },
              { label: "Review", count: review },
              { label: "Issues", count: 4, bad: true },
              "Activity",
            ],
          }}
          views={VIEWS}
          preset={preset}
          onPreset={setPreset}
          tree={{
            title: "Review",
            search:
              preset === "review" ? (
                <>
                  <SearchField
                    label="Search documents"
                    placeholder="Search"
                    value={query}
                    onChange={setQuery}
                    className="w-[120px]"
                  />
                  <IconButton icon="list-filter" label="Filter documents" variant="white" />
                </>
              ) : (
                <IconButton icon="list-filter" label="Filter documents" variant="white" />
              ),
            body: (
              <TriadTree
                groups={tree}
                selected={sel}
                query={query}
                onSelect={(d) => {
                  setSel(d.id);
                  setPick(d.id === "halvard" ? "1040" : "k1");
                }}
              />
            ),
            footer: (stacked) => (
              <TriadFooter
                actor={PERSON}
                approved={current.approved === true}
                stacked={stacked}
                onApprove={() => {
                  patch({ approved: true });
                  if (sel === "k1") setToast("Approved Ridgeline K-1 (draft) for review");
                }}
                onUnapprove={() => {
                  patch({ approved: false });
                  setToast(null);
                }}
                onIssue={() => {
                  patch({ flags: (current.flags ?? 0) + 1 });
                }}
              />
            ),
          }}
          viewer={<SourceViewer file={file} loading={board.loading === true} menu={VIEWER_MENU} />}
          sheet={{
            tabs: SHEETS,
            active: sheet,
            onTab: setSheet,
            bar: (
              <>
                <IconButton icon="list-filter" label="Filter lines" variant="white" />
                <span className="flex flex-1 justify-center">
                  <Picker
                    label="Leadsheet"
                    variant="white"
                    options={PICKS}
                    value={pick}
                    onChange={setPick}
                  />
                </span>
                <IconButton
                  icon="refresh-cw"
                  label="Refresh from the tax engine"
                  variant="white"
                />
                <IconButton icon="upload" label="Export" variant="white" />
              </>
            ),
            children:
              sheet !== "Leadsheets" ? null : pick === "k1" ? (
                <K1Matrix />
              ) : (
                <div className="px-[10px] pb-[12px]">
                  <EvidenceTable
                    label="Form 1040"
                    grammar="leadsheet"
                    blocks={FORM_1040_BLOCKS}
                    rowMatch={(row) => LINE_MATCH[row.id]}
                  />
                </div>
              ),
          }}
        />
        {toast !== null && (
          <div className="pointer-events-none absolute bottom-[24px] left-1/2 -translate-x-1/2">
            <Toast kind="success" text={toast} still />
          </div>
        )}
      </div>
    </Artboard>
  );
}

/** One artboard on its own (the tests render a single board). */
export function Tpl03Board({ id }: { id: string }): JSX.Element | null {
  const board = BOARDS.find((b) => b.id === id);
  return board === undefined ? null : <Tpl03 board={board} />;
}

export function Tpl03Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {BOARDS.map((b) => (
        <Tpl03 key={b.id} board={b} />
      ))}
    </div>
  );
}
