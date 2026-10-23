import { type JSX, useState } from "react";
import { Pane } from "../layout/pane";
import { MATCH_CELL, MATCH_ROW, MatchScope, useMatch } from "../tracing/match";
import { matchIdOf } from "../tracing/match-store";
import type { MatchId } from "../tracing/types";
import { FileChip, ReviewTree, SourceViewer } from "../viewer/source-viewer";
import type {
  PtRect,
  RevealedValue,
  ViewerFile,
  ViewerRegion,
  ViewerStatus,
} from "../viewer/types";
import { Held, Row, Sheet } from "./frame";
import { STAFF } from "./seed-figures";
import { FORM_PAGE_PNG, STATEMENT_PAGE_PNG } from "./viewer-pages";

// E5 SourceViewer shell (F-05-T47): the C-08 Doc Kit's two galleries on server page images. The
// Feld TY2025 Form 1040 review (Jonah & Claire Feld's 2025 Composite 1099 from Brightline, as the
// kit's reference maps it to the seed) and the Northwind evidence variant (the Harborline trust
// statement). The pages are synthetic grey-rule PNGs (viewer-pages.ts) standing in for the
// server's masked renders: no client file, no text layer. Regions sit at C4 page-point rects with
// match ids derived as the server derives them (INV-2).

const FELD_1099 = "c3a1e2f0-5d6b-4c7e-8f9a-0b1c2d3e4f51";
const HARBORLINE = "d4b2f3a1-6e7c-4d8f-9a0b-1c2d3e4f5a62";

const at = (version: string, page: number, bbox: PtRect): MatchId =>
  matchIdOf({ kind: "document_text", evidence_version_id: version, page, bbox });

const BOX_1A: PtRect = [294, 79, 441, 120];
const BOX_1B: PtRect = [294, 120, 441, 161];
const BOX_2A: PtRect = [294, 161, 441, 202];
const BOX_7: PtRect = [294, 326, 441, 367];

const DIV_1A = at(FELD_1099, 1, BOX_1A);
const DIV_1B = at(FELD_1099, 1, BOX_1B);
const DIV_2A = at(FELD_1099, 1, BOX_2A);
const DIV_7 = at(FELD_1099, 1, BOX_7);

const FELD_REGIONS: readonly ViewerRegion[] = [
  {
    match: DIV_1A,
    page: 1,
    rects: [BOX_1A],
    label: "1a Total ordinary dividends",
    linkedFigure: { label: "Form 1040 · Line 3b", value: "$4,812" },
  },
  {
    match: DIV_1B,
    page: 1,
    rects: [BOX_1B],
    label: "1b Qualified dividends",
    linkedFigure: { label: "Form 1040 · Line 3a", value: "$3,960" },
  },
  {
    match: DIV_2A,
    page: 1,
    rects: [BOX_2A],
    label: "2a Total capital gain distr.",
    linkedFigure: { label: "Schedule D · Line 13", value: "$1,205" },
  },
  {
    match: DIV_7,
    page: 1,
    rects: [BOX_7],
    label: "7 Foreign tax paid",
    linkedFigure: { label: "Schedule 3 · Line 1", value: "$48" },
  },
  // The statement total on page 2 lights with box 1a, as a band.
  { match: DIV_1A, page: 2, rects: [[43, 340, 569, 356]], band: true },
];

const PAGE = { width_pt: 612, height_pt: 792, rotation: 0 } as const;

export const FELD_FILE: ViewerFile = {
  name: "2025 Composite 1099 — Brokerage.pdf",
  pages: [
    { n: 1, ...PAGE, src: FORM_PAGE_PNG },
    { n: 2, ...PAGE, src: STATEMENT_PAGE_PNG },
  ],
  regions: FELD_REGIONS,
  masks: [
    {
      id: "mask-recipient-tin",
      page: 1,
      rect: [170, 166, 290, 198],
      kind: "ssn",
      display: "•••-••-4417",
    },
  ],
};

const NET_ASSETS = at(HARBORLINE, 2, [43, 436, 569, 452]);

export const HARBORLINE_FILE: ViewerFile = {
  name: "Harborline Net Trust Assets 12-31-2025.pdf",
  pages: [
    { n: 1, ...PAGE, src: STATEMENT_PAGE_PNG },
    { n: 2, ...PAGE, src: STATEMENT_PAGE_PNG },
    { n: 3, ...PAGE, src: STATEMENT_PAGE_PNG },
  ],
  regions: [
    {
      match: NET_ASSETS,
      page: 2,
      rects: [[43, 436, 569, 452]],
      band: true,
      label: "Net assets held in trust",
    },
  ],
};

const MENU = [
  { label: "Download", icon: "download" as const, onSelect: () => undefined },
  { label: "Open in Files", icon: "folder-open" as const, onSelect: () => undefined },
];

/** "Revealed by Samuel Ito · 9:31 AM · logged to the audit trail" (C4 §8). */
const REVEAL_NOTE = `Revealed by ${STAFF.samuel} · 9:31 AM · logged to the audit trail`;

function WorksheetRow({
  label,
  value,
  match,
}: {
  label: string;
  value: string;
  match: MatchId;
}): JSX.Element {
  const { bind, pin } = useMatch(match, "row");
  return (
    <li
      {...bind}
      onClick={(e) => {
        pin(e.currentTarget);
      }}
      className={`${MATCH_ROW} flex min-h-[40px] items-center justify-between gap-[10px] px-[12px] text-body hairline-b`}
    >
      <span>{label}</span>
      <span
        {...(bind["data-lit"] === undefined ? {} : { "data-lit": "" })}
        className={`${MATCH_CELL} rounded-[3px] px-[4px] tabular-nums`}
      >
        {value}
      </span>
    </li>
  );
}

function TaxReview({ revealable }: { revealable: boolean }): JSX.Element {
  const [revealed, setRevealed] = useState<Record<string, RevealedValue>>({});
  return (
    <MatchScope>
      <div className="flex h-[640px] gap-[10px] bg-shell p-[10px]">
        <Pane width={214} title="Review">
          <ReviewTree
            groups={[
              {
                label: "Income",
                docs: [
                  { id: "w2", name: "W-2 · Northwind Robotics", checks: 1 },
                  {
                    id: "1099",
                    name: "Composite 1099 · Brightline",
                    checks: 0,
                    leaves: [
                      { label: "Ordinary dividends 1a", match: DIV_1A },
                      { label: "Qualified dividends 1b", match: DIV_1B },
                      { label: "Capital gain distr. 2a", match: DIV_2A },
                      { label: "Foreign tax paid 7", match: DIV_7 },
                    ],
                  },
                ],
              },
              {
                label: "Deductions",
                docs: [{ id: "1098", name: "1098 · Mortgage interest", checks: 2 }],
              },
            ]}
          />
        </Pane>
        <section className="pane flex min-w-0 flex-[1_1_0%] flex-col overflow-hidden">
          <SourceViewer
            file={FELD_FILE}
            menu={MENU}
            pageWidth={500}
            reveal={{
              allowed: revealable,
              onReveal: (id) => {
                setRevealed((r) => ({ ...r, [id]: { value: "000-00-4417", note: REVEAL_NOTE } }));
              },
              revealed,
            }}
          />
        </section>
        <Pane width={300} title="Worksheet">
          <div className="flex flex-col gap-[10px] p-[10px]">
            <section className="overflow-hidden rounded-nested bg-card shadow-e1">
              <h3 className="flex h-[33px] items-center justify-between bg-band-hd px-[12px] text-section hairline-b">
                Interest and dividends{" "}
                <span className="text-dense font-normal text-ink-3">2025</span>
              </h3>
              <ul>
                <WorksheetRow label="Line 3a · Qualified dividends" value="3,960" match={DIV_1B} />
                <WorksheetRow label="Line 3b · Ordinary dividends" value="4,812" match={DIV_1A} />
                <WorksheetRow label="Schedule D · Line 13" value="1,205" match={DIV_2A} />
                <WorksheetRow label="Schedule 3 · Line 1" value="48" match={DIV_7} />
              </ul>
            </section>
            <div className="flex flex-col gap-[8px] rounded-nested bg-card p-[12px] shadow-e1">
              <p className="text-section">Issue 6 · Foreign tax credit without Form 1116</p>
              <FileChip
                name={FELD_FILE.name}
                location="Box 7"
                matches={[DIV_1A, DIV_1B, DIV_2A, DIV_7]}
              />
            </div>
          </div>
        </Pane>
      </div>
    </MatchScope>
  );
}

function Status({ status }: { status: ViewerStatus }): JSX.Element {
  return (
    <div className="h-[260px] w-[420px] overflow-hidden rounded-pane shadow-e1">
      <SourceViewer
        file={{ ...HARBORLINE_FILE, regions: [] }}
        variant="evidence"
        status={status}
      />
    </div>
  );
}

/** C-08 SourceViewer: full and evidence variants, regions, linked figures, the reveal slot and
 * every viewer state. */
export function SourceViewerSpecimen(): JSX.Element {
  return (
    <Sheet
      title="SourceViewer (E5)"
      meta="Server page images only · regions invisible until lit · linked figure tag · Download only in ⋯ · Reveal (logged) calls the caller once per click"
    >
      <Row
        name="Full, tax review"
        meaning="Hover a leaf, a region or a worksheet line: they light together, the tag shows, the file chip lights"
      >
        <div data-viewer-specimen="full" className="w-full">
          <TaxReview revealable />
        </div>
      </Row>
      <Row name="Evidence" meaning="The narrow audit bar; a statement row lights as a band">
        <div
          data-viewer-specimen="evidence"
          className="h-[560px] w-[440px] overflow-hidden rounded-pane shadow-e1"
        >
          <MatchScope>
            <SourceViewer file={HARBORLINE_FILE} variant="evidence" menu={MENU.slice(0, 1)} />
          </MatchScope>
        </div>
      </Row>
      <Row name="States" meaning="Words from the status registry (C4 viewer codes)">
        <Held name="Processing">
          <Status status="processing" />
        </Held>
        <Held name="Password-protected">
          <Status status="password_protected" />
        </Held>
        <Held name="Can't preview">
          <Status status="not_previewable" />
        </Held>
        <Held name="Loading">
          <div className="h-[260px] w-[420px] overflow-hidden rounded-pane shadow-e1">
            <SourceViewer file={HARBORLINE_FILE} variant="evidence" loading pageWidth={300} />
          </div>
        </Held>
      </Row>
    </Sheet>
  );
}
