import { MatchScope, SourceViewer, type ViewerFile } from "@abacus/ui";
import { type JSX, useState } from "react";
import {
  AnalyticsTable,
  AttributesCard,
  CardWell,
  ConfirmationDrawer,
  CriteriaTable,
  DeviationLog,
  ExpandTestingSheet,
  FIELDWORK_COPY,
  NewConfirmationSheet,
  PopulationCard,
  type RunRow,
  RunRows,
  SelectedEntriesCard,
  type SelectedEntry,
  SsarsRail,
  TestGrid,
  TestingFooter,
} from "../domain/audits";
import {
  GRANITE_PEAK_CRITERIA,
  GRANITE_PEAK_LINES,
  GRANITE_PEAK_UNIQUE_FLAGGED,
  LAKESHORE_LINES,
} from "../fixtures/seed/fieldwork";
import {
  ALPINE_RIDGE_DETAIL,
  ALPINE_RIDGE_WHY,
  ATTRIBUTES_17994,
  INTEREST_MATCH,
  NORTHWIND_GRID,
  NORTHWIND_HEADERS,
  SELECTED_PAGE,
  SSARS_STEPS,
} from "./kit-a08-data";
import { type FixtureParams, registerScreen } from "../gallery/fixture-mode";

// KIT-A08: the fieldwork L3 kit's gallery board (A-08-T26). Every component in each state the
// handoff draws (AUD-12 a, d to h; AUD-13 a; AUD-14 a, e; AUD-26 a, c, d), on the seed figures.
// `?st=` holds one: je (default), agent, exception, expand, awaiting, details, controls,
// analytics, confirmations, new-confirmation, ssars.

// A one-pixel page stands in for the server's rendered page in the gallery; the region lights.
const PAGE_PNG =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=";
const NOTICE: ViewerFile = {
  name: "Front Range Bank — Interest notice Q4 FY2026.pdf",
  pages: [
    { n: 1, width_pt: 612, height_pt: 792, rotation: 0, src: PAGE_PNG },
    { n: 2, width_pt: 612, height_pt: 792, rotation: 0, src: PAGE_PNG },
  ],
  regions: [
    {
      match: INTEREST_MATCH,
      page: 1,
      rects: [[340, 402, 560, 418]],
      label: "Apr 1 – Jun 30, 2026 · $6,200,000.00 · 6.55% · $101,246.85",
      band: true,
    },
  ],
};
const RUNS: RunRow[] = [
  { id: "prelim", label: "Preliminary analytics", meta: "Run Sep 8 · 14 lines", state: "done" },
  { id: "substantive", label: "Substantive analytics", meta: "Running", state: "running" },
];
const HANNAH = { id: "hannah", name: "Hannah Leclerc" };
export const KIT_A08_STATES = [
  "je",
  "agent",
  "exception",
  "expand",
  "awaiting",
  "details",
  "controls",
  "analytics",
  "confirmations",
  "new-confirmation",
  "ssars",
] as const; // fmt: skip
type KitState = (typeof KIT_A08_STATES)[number];

function rowsFor(state: KitState): SelectedEntry[] {
  if (state === "agent") return SELECTED_PAGE.map((r) => ({ ...r, result: "running" as const }));
  if (state === "exception" || state === "expand") {
    return SELECTED_PAGE.map((r) =>
      r.position === 3 ? { ...r, result: "exception" as const } : r,
    );
  }
  return SELECTED_PAGE;
}

function JeBoard({ state }: { state: KitState }): JSX.Element {
  const [filter, setFilter] = useState<(typeof GRANITE_PEAK_CRITERIA)[number]["key"] | null>(null);
  const [selected, setSelected] = useState("JE-26-17994");
  const [expand, setExpand] = useState(state === "expand");
  const K = FIELDWORK_COPY.criteria;
  return (
    <MatchScope className="flex gap-[12px]">
      <div className="flex w-[536px] flex-col">
        <CardWell>
          <PopulationCard
            source="NetSuite GL detail FY2026"
            entries={18426}
            lines={412903}
            periodStart="2025-07-01"
            periodEnd="2026-06-30"
            postCloseThrough="2026-07-15"
            tie={{ accounts_tied: 214, accounts_total: 214, difference: "0.00", result: "tie" }}
          />
          <CriteriaTable
            criteria={GRANITE_PEAK_CRITERIA}
            uniqueFlagged={GRANITE_PEAK_UNIQUE_FLAGGED}
            filter={filter}
            onFilter={setFilter}
            detail={{
              round_amount: "≥ $50,000",
              post_close: "(after Jun 30)",
              keywords: '("plug", "adjust")',
            }}
            footer={K.footer(40, 34, 61, 6) + K.approved("HL", "Oct 2")}
          />
          <SelectedEntriesCard
            rows={rowsFor(state)}
            total={40}
            from={1}
            selectedRef={selected}
            onSelect={setSelected}
            onReview={() => undefined}
            pending={state === "awaiting" ? { add: 10, initials: "HL" } : undefined}
          />
          <AttributesCard entryRef="JE-26-17994" rows={ATTRIBUTES_17994} />
        </CardWell>
        <TestingFooter
          onExpand={() => {
            setExpand(true);
          }}
          waitingOn={state === "awaiting" ? HANNAH.name : undefined}
        />
      </div>
      <div className="w-[490px]">
        <SourceViewer file={NOTICE} height={720} loading={state === "agent"} scrollToLit />
      </div>
      <ExpandTestingSheet
        open={expand}
        onOpenChange={setExpand}
        base={40}
        approvers={[HANNAH]}
        viewer={{ kind: "human", name: "Simone Baptiste" }}
        held={state === "expand"}
      />
    </MatchScope>
  );
}

export function KitA08Board({ params }: { params: FixtureParams }): JSX.Element {
  const state: KitState = (KIT_A08_STATES as readonly string[]).includes(params.st ?? "")
    ? (params.st as KitState)
    : "je";
  const [drawer, setDrawer] = useState(true);
  const [sheet, setSheet] = useState(true);
  return (
    <div data-kit="A-08" data-state={state} className="bg-shell p-[12px]">
      {["je", "agent", "exception", "expand", "awaiting"].includes(state) && (
        <JeBoard state={state} />
      )}
      {(state === "details" || state === "controls") && (
        <div className="flex w-[536px] flex-col">
          <CardWell>
            <TestGrid
              variant={state}
              title={
                state === "details"
                  ? "Contribution testing, Dec 12, 2025 payroll"
                  : "Credit approval, revenue cycle"
              }
              grid={NORTHWIND_GRID}
              headers={NORTHWIND_HEADERS}
            />
            {state === "controls" && <DeviationLog deviations={[]} udl="8.8%" tolerable="10%" />}
          </CardWell>
          <TestingFooter expandPrimary={state === "details"} />
        </div>
      )}
      {state === "analytics" && (
        <div className="flex w-[696px] flex-col">
          <CardWell>
            <RunRows rows={RUNS} />
            <AnalyticsTable title="Granite Peak · FY2026" lines={GRANITE_PEAK_LINES} />
            <AnalyticsTable title="Lakeshore Literacy Alliance · FY2026" lines={LAKESHORE_LINES} />
          </CardWell>
        </div>
      )}
      {state === "confirmations" && (
        <ConfirmationDrawer
          open={drawer}
          onOpenChange={setDrawer}
          detail={ALPINE_RIDGE_DETAIL}
          why={ALPINE_RIDGE_WHY}
          held
        />
      )}
      {state === "new-confirmation" && (
        <NewConfirmationSheet
          open={sheet}
          onOpenChange={setSheet}
          held
          initial={{
            respondentOrg: "Cascade Peak Outfitters",
            address: "ap@cascadepeak.example",
            method: "From the client's AR listing",
            sources: ["client_supplied"],
          }}
        />
      )}
      {state === "ssars" && (
        <div className="flex gap-[12px]">
          <SsarsRail mode="review" steps={SSARS_STEPS.review} />
          <SsarsRail mode="compilation" steps={SSARS_STEPS.compilation} />
          <SsarsRail mode="preparation" steps={SSARS_STEPS.preparation} />
        </div>
      )}
    </div>
  );
}

registerScreen("KIT-A08", {
  title: "Fieldwork kit · JE testing, test grids, analytics, confirmations, SSARS",
  Component: KitA08Board,
});
