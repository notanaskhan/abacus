import {
  AgentText,
  type CitationView,
  CiteMarker,
  DocumentOnWell,
  type DocumentVM,
  type KvSheetVM,
  type MatchId,
  RecordHeader,
  SegmentedGroup,
} from "@abacus/ui";
import type { JSX, ReactNode } from "react";
import { useSession } from "../../../app-core/session";
import { useFirmToolbar } from "../../../shell/firm/ToolbarData";
import type { FixtureParams } from "../../fixture-mode";
import { COPY } from "./copy";

// T10 Document on well, the template board (F-06-T14; docs/screens/T10.md; F-06.md §3 F4): a and b
// on the Ridgeline 2025 Form 1065, Deliverables tab. a: the agent drafting the return summary
// (three skeleton paragraphs, the header spinner, Regenerate and Approve disabled and saying why);
// b: the draft with its DRAFT watermark and citation markers [1]–[3], each lighting the row of the
// structure sheet it cites. The board's own data (canvas `#t10`, T10a and T10b), as the T16 board
// keeps its own (DECISIONS.md, F-06-T04): TPL-10 (F-06-T16) draws the seeded memo. c–e (approved,
// locked, email) are F-06-T15's. Registered for /components/screens/T10?st=a|b.

export const T10_STATES = ["a", "b"] as const;
export type T10State = (typeof T10_STATES)[number];

const RIDGELINE = "Ridgeline Property Partners, LP";

const m = (id: string): MatchId => `t10:${id}` as MatchId;

export const SHEET: KvSheetVM = {
  crumb: "Partnership › General Information",
  sections: [
    {
      title: "Entity",
      rows: [
        { key: "Legal name", value: RIDGELINE },
        { key: "EIN", value: "84-•••2716" },
        { key: "Address", value: "220 N Green Street, Suite 500, Chicago, IL 60607" },
        { key: "Business activity", value: "Rental real estate", match: m("activity") },
        { key: "Business code", value: "531120" },
        { key: "Date business started", value: "March 1, 2014" },
        { key: "Accounting method", value: "Accrual" },
      ],
    },
    {
      title: "Partners",
      rows: [
        { key: "Number of partners", value: "4", match: m("partners") },
        { key: "General partner", value: "Ridgeline GP, LLC", linkId: "ridgeline-gp" },
        { key: "Partnership representative", value: "Ridgeline GP, LLC", linkId: "ridgeline-gp" },
        { key: "Section 754 election", value: null },
      ],
    },
    {
      title: "Filing",
      rows: [
        { key: "Tax year", value: "Calendar 2025" },
        { key: "Due date", value: "September 15, 2026 · extended" },
        { key: "State returns", value: "Illinois · Colorado, Utah and Arizona composites" },
        { key: "Preparer", value: "Olivia Brandt" },
        { key: "Reviewer", value: "Daniel Reyes" },
        {
          key: "Prior-year return",
          value: "2024 Form 1065",
          linkId: "ridgeline-2024-1065",
          match: m("prior-year"),
        },
      ],
    },
  ],
};

/** Each marker cites a row of the sheet beside the paper: its locator is the row (INV-2). */
function cite(n: number, key: string, quote: string, match: MatchId): CitationView {
  return { n, title: SHEET.crumb, quote, loc: key, match };
}

const CITES = {
  priorYear: cite(1, "Prior-year return", "2024 Form 1065", m("prior-year")),
  activity: cite(2, "Business activity", "Rental real estate", m("activity")),
  partners: cite(3, "Number of partners", "4", m("partners")),
} as const;

export function t10Document(state: T10State): DocumentVM {
  return {
    status: state === "a" ? "drafting" : "draft",
    variant: "paper",
    structure: { kind: "kv", sheets: [SHEET] },
    title: "Return Summary",
    watermark: state === "b",
    actions: {
      edit: true,
      regenerate: true,
      approve: { actor: { kind: "human", name: "Samuel Ito" } },
    },
  };
}

/** Agent prose with the code-rendered figures between its segments (P-24: numbers by reference). */
function Prose({ children }: { children: ReactNode }): JSX.Element {
  return <p className="mb-[12px] text-[12px] leading-[1.55] text-ink">{children}</p>;
}

const fig = (value: string): JSX.Element => (
  <strong className="font-medium tabular-nums">{value}</strong>
);
const say = (text: string): JSX.Element => <AgentText inline text={text} />;

/** T10b's paper: the agent's 2025 Return Summary for partner review. */
export function ReturnSummary(): JSX.Element {
  return (
    <div data-document="blocks">
      <h3 className="text-[16px] font-medium">2025 Return Summary</h3>
      <p className="mt-[6px] mb-[16px] text-meta text-ink-3">
        {RIDGELINE} · Form 1065 · for partner review
      </p>
      <h4 className="mb-[6px] text-[13.5px] font-medium">Income</h4>
      <Prose>
        {say("Net rental real estate income was ")}
        {fig("384,120")}
        {say(", up ")}
        {fig("22,220")}
        {say(" from 2024")}
        <CiteMarker cite={CITES.priorYear} />
        {say(". Interest income was ")}
        {fig("28,480")}
        <CiteMarker cite={CITES.activity} />
        {say(".")}
      </Prose>
      <h4 className="mb-[6px] text-[13.5px] font-medium">Partners&apos; capital</h4>
      <Prose>
        {say("Ending capital is ")}
        {fig("1,896,082")}
        {say(" across four partners. Marrow Point Holdings, LLC contributed ")}
        {fig("40,000")}
        {say(" on April 2")}
        <CiteMarker cite={CITES.partners} />
        {say(".")}
      </Prose>
      <ul className="mb-[12px] list-disc pl-[18px] text-[12px] leading-[1.55]">
        <li>
          {say("Distributions of ")}
          {fig("300,000")}
          {say(", paid quarterly")}
        </li>
        <li>{say("Capital accounts tie to Schedule M-2 and Schedule L")}</li>
      </ul>
      <h4 className="mb-[6px] text-[13.5px] font-medium">Open items</h4>
      <Prose>
        {say(
          "Nine issues are open and seven of them wait on the client. The partners still need to decide on the Section 754 election before filing.",
        )}
      </Prose>
      <h4 className="mb-[6px] text-[13.5px] font-medium">Filing</h4>
      <Prose>
        {say("Due ")}
        {fig("September 15, 2026")}
        {say(
          " on extension. The Colorado, Utah and Arizona composite returns file with the federal return.",
        )}
      </Prose>
    </div>
  );
}

const ENTITY_TABS = [
  "Agent",
  { label: "Issues", count: 9, bad: true },
  "Workpaper",
  "Review",
  "Deliverables",
];

export function T10Board({ state }: { state: T10State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/tax-returns" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <DocumentOnWell
      frame
      height={860}
      document={t10Document(state)}
      copy={{
        edit: COPY.edit,
        regenerate: COPY.regenerate,
        drafting: COPY.drafting,
        rendering: COPY.rendering,
        watermark: COPY.watermark,
        variables: COPY.variables,
      }}
      toolbar={bar.toolbar}
      record={
        <RecordHeader
          title="2025 Form 1065"
          context={RIDGELINE}
          state="In review · Partner"
          checkpoints
          sync="synced"
          syncDate="Sep 11"
          assistant
        />
      }
      tabs={
        <div data-shell="tabsbar" className="flex h-(--tabs-h) flex-none items-center justify-center px-[12px]">
          <SegmentedGroup
            size="small"
            label="Partnership return"
            options={ENTITY_TABS}
            active="Deliverables"
          />
        </div>
      }
      onApprove={() => undefined}
      onEdit={() => undefined}
      onRegenerate={() => undefined}
      onOpenLink={() => undefined}
    >
      <ReturnSummary />
    </DocumentOnWell>
  );
}

export function T10Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: T10State = T10_STATES.find((s) => s === params.st) ?? "b";
  return (
    <div data-artboard={state}>
      <T10Board state={state} />
    </div>
  );
}
