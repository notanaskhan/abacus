import type { JSX } from "react";
import { amount } from "../format";
import {
  type CitationView,
  CitationChip,
  CitationFooter,
  CitationPopover,
  CitationPopoverHost,
  CiteMarker,
  MATCH_CELL,
  MATCH_ROW,
  MatchScope,
  Matchable,
  matchIdOf,
} from "../tracing";
import { Held, Row, Sheet } from "./frame";
import { NORTHWIND_FIGURES, NORTHWIND_PLAN } from "./seed-figures";

// The C-07 Cite kit and the E1 and E2 engines (F-05-T41): the CiteMarker in prose, the 372
// CitationPopover, the footer chips, the light on rows, cells and regions, and the "wired" board
// (C-07·05) where a marker lights its cell and the host anchors the popover beside it. Figures are
// the seed's Northwind PY2025 net assets (seed-figures.ts); kit sample data is never ported. The
// ids come from typed C4 locators (INV-2).

const TB_FILE = "Northwind PY2025 trial balance.xlsx";
const NET = matchIdOf({ kind: "sheet_cell", file: TB_FILE, sheet: "Net assets", cell: "D8" });
const RECEIVABLE = matchIdOf({
  kind: "sheet_cell",
  file: TB_FILE,
  sheet: "Net assets",
  cell: "D9",
});
const TRUST = matchIdOf({
  kind: "document_text",
  evidence_version_id: "harborline-2025",
  page: 1,
});

const money = (v: string): string => amount(v, "money").text;

const CITES: readonly CitationView[] = [
  {
    n: 1,
    title: "Northwind PY2025 trial balance",
    quote: `Net assets available for benefits, unadjusted ${money(NORTHWIND_FIGURES.netAssetsUnadjusted)}`,
    loc: "Net assets!D8",
    match: NET,
    kind: "xlsx",
  },
  {
    n: 2,
    title: "Harborline certified trust report",
    quote: `Net trust assets ${money(NORTHWIND_FIGURES.netAssetsUnadjusted)}`,
    loc: "Page 1 · Statement of net assets",
    match: TRUST,
    kind: "pdf",
  },
  {
    n: 3,
    title: "BH Audit Methodology · EBP v3",
    quote: "Agree the plan's net assets to the trustee's certified report.",
    loc: "General planning procedures",
    match: null,
    kind: "workpaper",
  },
];

const [C1, C2, C3] = CITES as [CitationView, CitationView, CitationView];

export function CiteMarkerSpecimen(): JSX.Element {
  return (
    <Sheet title="CiteMarker" meta="17 · 10.5 / 500 · lights its match in 150ms, a click pins">
      <Row name="In prose" meaning="Message 13.5 / 1.45; body 12.5 / 1.55 ink-2">
        <MatchScope>
          <p className="max-w-[460px] text-chat">
            The trial balance
            <CiteMarker cite={C1} list={CITES} /> ties to the trustee&rsquo;s report
            <CiteMarker cite={C2} list={CITES} />
          </p>
          <p className="max-w-[460px] text-para text-ink-2">
            Planning follows the firm&rsquo;s general procedures
            <CiteMarker cite={C3} list={CITES} />
          </p>
        </MatchScope>
      </Row>
      <Row name="States" meaning="Default, hover, focus, open">
        <Held name="default">
          <CiteMarker cite={C1} />
        </Held>
        <Held name="hover">
          <CiteMarker cite={C1} forceState="hover" />
        </Held>
        <Held name="focus">
          <CiteMarker cite={C1} forceState="focus" />
        </Held>
        <Held name="open">
          <CiteMarker cite={C1} forceState="open" />
        </Held>
      </Row>
    </Sheet>
  );
}

export function CitationPopoverSpecimen(): JSX.Element {
  return (
    <Sheet title="CitationPopover" meta="372 · title, quote, location; ‹ 1 of 3 › re-lights">
      <Row name="One source" meaning="The location is always shown">
        <div className="w-[372px] overflow-hidden rounded-pane bg-card shadow-pop">
          <CitationPopover payload={{ list: [C2], index: 0 }} onOpenDialog={() => undefined} />
        </div>
      </Row>
      <Row name="Three sources" meaning="The stepper; the first source in view">
        <div className="w-[372px] overflow-hidden rounded-pane bg-card shadow-pop">
          <CitationPopover payload={{ list: CITES, index: 0 }} onOpenDialog={() => undefined} />
        </div>
      </Row>
    </Sheet>
  );
}

export function CitationChipSpecimen(): JSX.Element {
  return (
    <Sheet title="CitationChip footer" meta="Chip 28 · menu 280 upward · rows 32">
      <Row name="Footer" meaning="Pinned at the workpaper's bottom left">
        <div className="w-[520px] overflow-hidden rounded-pane shadow-e2">
          <CitationFooter>
            <CitationChip kind="citations" citations={CITES} />
            <CitationChip
              kind="procedures"
              procedures={[{ ref: "AP-10 step 4", title: "General planning procedures" }]}
            />
          </CitationFooter>
        </div>
      </Row>
      <Row name="States" meaning="Hover; the menu open (hovering a row lights its cell)">
        <Held name="hover">
          <CitationChip kind="citations" citations={CITES} forceState="hover" />
        </Held>
        <div className="flex h-[150px] items-end">
          <Held name="open">
            <CitationChip kind="citations" citations={CITES} forceState="open" />
          </Held>
        </div>
      </Row>
    </Sheet>
  );
}

const ROWS = [
  {
    id: NET,
    label: "Net assets available for benefits, unadjusted",
    value: NORTHWIND_FIGURES.netAssetsUnadjusted,
  },
  {
    id: RECEIVABLE,
    label: "Contributions receivable",
    value: NORTHWIND_FIGURES.contributionsReceivable,
  },
];

const C4: CitationView = {
  n: 4,
  title: "Northwind PY2025 trial balance",
  quote: `Contributions receivable ${money(NORTHWIND_FIGURES.contributionsReceivable)}`,
  loc: "Net assets!D9",
  match: RECEIVABLE,
  kind: "xlsx",
};

/** C-07·05: the marker lights the cited cell; the host anchors the popover 8px beside it. */
export function MatchWiredSpecimen(): JSX.Element {
  return (
    <Sheet
      title="Wired to the MatchProvider"
      meta="One match per scope · 120 / 150 / 140 ms · Esc"
    >
      <Row name="Statement and note" meaning="Hover a marker or a row; click to pin">
        <MatchScope className="block">
          <div data-specimen="wired" className="flex items-start gap-[24px]">
            <table className="w-[460px] border-collapse text-cell">
              <caption className="sr-only">{NORTHWIND_PLAN}</caption>
              <tbody>
                {ROWS.map((row) => (
                  <Matchable key={row.id} id={row.id} as="tr" className="hairline-b">
                    <td className="h-[30px] px-[10px]">{row.label}</td>
                    <Matchable
                      id={row.id}
                      kind="cell"
                      as="td"
                      className="px-[10px] text-right tabular-nums"
                    >
                      {money(row.value)}
                    </Matchable>
                  </Matchable>
                ))}
              </tbody>
            </table>
            <p className="max-w-[300px] text-para text-ink-2">
              Net assets agree to the trial balance
              <CiteMarker cite={C1} list={CITES} />
              and to the trustee&rsquo;s report
              <CiteMarker cite={C2} list={CITES} />.
            </p>
          </div>
          <CitationPopoverHost />
        </MatchScope>
      </Row>
      <Row name="At the right edge" meaning="No room on the right: the popover flips left">
        <MatchScope className="block w-[1080px] max-w-full">
          <div data-specimen="edge" className="flex w-full items-center">
            <p className="text-para text-ink-2">
              Contributions receivable
              <CiteMarker cite={C4} />
            </p>
            <Matchable
              id={RECEIVABLE}
              kind="cell"
              className="ml-auto px-[10px] py-[6px] text-cell tabular-nums"
            >
              {money(NORTHWIND_FIGURES.contributionsReceivable)}
            </Matchable>
          </div>
          <CitationPopoverHost />
        </MatchScope>
      </Row>
    </Sheet>
  );
}

/** The light itself: a row, an exact cell and a page region, each held lit. */
export function MatchLightSpecimen(): JSX.Element {
  return (
    <Sheet title="Match light" meta="Purple is tracing only · one 360ms fade">
      <Row name="Row" meaning="The match fill">
        <span data-lit="" className={`${MATCH_ROW} rounded-value px-[8px] py-[4px] text-cell`}>
          Contributions receivable
        </span>
      </Row>
      <Row name="Exact cell" meaning="Deeper fill, 1.5 inset line, match ink at 500">
        <span
          data-lit=""
          className={`${MATCH_CELL} rounded-value px-[8px] py-[4px] text-cell tabular-nums`}
        >
          {money(NORTHWIND_FIGURES.contributionsReceivable)}
        </span>
      </Row>
    </Sheet>
  );
}
