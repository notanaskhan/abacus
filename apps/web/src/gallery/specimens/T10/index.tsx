import {
  AgentText,
  type CitationView,
  CiteMarker,
  type DocBlock,
  DocBlocks,
  DocumentOnWell,
  type DocumentVM,
  type KvSheetVM,
  type MatchId,
  RecordHeader,
  SegmentedGroup,
} from "@abacus/ui";
import type { JSX, ReactNode } from "react";
import { useSession } from "../../../app-core/session";
import type { FixtureParams } from "../../fixture-mode";
import { specimenToolbar } from "../firm-toolbar";
import { COPY } from "./copy";

// T10 Document on well, the template board (F-06-T14; docs/screens/T10.md; F-06.md §3 F4): a and b
// on the Ridgeline 2025 Form 1065, Deliverables tab. a: the agent drafting the return summary
// (three skeleton paragraphs, the header spinner, Regenerate and Approve disabled and saying why);
// b: the draft with its DRAFT watermark and citation markers [1]–[3], each lighting the row of the
// structure sheet it cites. The board's own data (canvas `#t10`, T10a to T10e), as the T16 board
// keeps its own (DECISIONS.md, F-06-T04): TPL-10 (F-06-T16) draws the seeded memo. F-06-T22 adds
// the letter and email boards on F-06-T15's DocBlocks: c the Feld transmittal letter approved by
// Samuel Ito, d the Harborview K-1 cover letter locked while the return is out for signature, e
// the Whitley document reminder email as a draft. Letters and the email are template text only
// (ADR P-25 off). Registered for /components/screens/T10?st=a…e.

export const T10_STATES = ["a", "b", "c", "d", "e"] as const;
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
        // eslint-disable-next-line no-restricted-syntax -- handoff data: the accounting method, not the product's name
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

const SAMUEL = { kind: "human", name: "Samuel Ito" } as const;

/** c, d, e: the letter and email boards' structure, verbatim from the artboards. */
const CLAUSES: Readonly<Record<"c" | "d" | "e", DocumentVM["structure"]>> = {
  c: {
    kind: "clauses",
    clauses: [
      {
        id: "greeting",
        label: "Greeting and summary",
        on: true,
        reason: "Always included",
        required: true,
      },
      {
        id: "balance",
        label: "Balance due and how to pay",
        on: true,
        reason: "Balance due of 3,482",
      },
      {
        id: "estimates",
        label: "2026 estimated payments",
        on: true,
        reason: "Safe harbor applies",
      },
      { id: "filing", label: "Filing instructions", on: true, reason: "E-file after you sign" },
      { id: "extension", label: "Extension notice", on: false, reason: "Not on extension" },
    ],
    variables: [
      { id: "client", label: "Client", value: "Jonah & Claire Feld" },
      { id: "salutation", label: "Salutation", value: "Dear Jonah and Claire" },
      { id: "balance", label: "Balance due", value: "3,482" },
      { id: "pay_by", label: "Pay by", value: "October 15, 2026" },
      { id: "signer", label: "Signer", value: "Daniel Reyes" },
      { id: "preparer", label: "Prepared by", value: "Kevin Osei" },
    ],
  },
  d: {
    kind: "clauses",
    clauses: [
      { id: "greeting", label: "Greeting", on: true, reason: "Always included", required: true },
      { id: "what_to_do", label: "What to do with your K-1", on: true, reason: "All partners" },
      { id: "state", label: "State K-1s", on: true, reason: "Illinois partners" },
      { id: "basis", label: "Basis reminder", on: false, reason: "No losses this year" },
    ],
    variables: [
      { id: "partnership", label: "Partnership", value: "Harborview Dental Properties, LP" },
      { id: "partners", label: "Partners", value: "6" },
      { id: "sent", label: "Sent", value: "September 10, 2026" },
      { id: "signer", label: "Signer", value: "Daniel Reyes" },
    ],
  },
  e: {
    kind: "clauses",
    clauses: [
      { id: "greeting", label: "Greeting", on: true, reason: "Always included", required: true },
      { id: "open", label: "Open requests", on: true, reason: "5 still open" },
      { id: "due", label: "Due date reminder", on: true, reason: "September 30" },
      { id: "button", label: "Portal button", on: true, reason: "Opens the binder" },
      { id: "questions", label: "Questions line", on: false, reason: "Off for reminders" },
    ],
    variables: [
      { id: "client", label: "Client", value: "Marcus & Dana Whitley" },
      { id: "open", label: "Open requests", value: "5" },
      { id: "due_by", label: "Due by", value: "September 30, 2026" },
      { id: "button", label: "Button", value: "Open Your Binder" },
      { id: "from", label: "From", value: "Kevin Osei" },
    ],
  },
};

export function t10Document(state: T10State): DocumentVM {
  if (state === "c") {
    return {
      status: "approved",
      variant: "letter",
      structure: CLAUSES.c,
      title: "Transmittal Letter",
      watermark: false,
      approvedBy: { actor: SAMUEL, when: "Sep 12" },
      actions: { approve: { actor: SAMUEL } },
    };
  }
  if (state === "d") {
    return {
      status: "locked",
      variant: "letter",
      structure: CLAUSES.d,
      title: "K-1 Cover Letter",
      watermark: false,
      lockedReason: "Out for signature since Sep 10",
      actions: {},
    };
  }
  if (state === "e") {
    return {
      status: "draft",
      variant: "email",
      structure: CLAUSES.e,
      title: "Document Reminder Email",
      watermark: true,
      actions: {
        edit: true,
        regenerate: true,
        approve: { actor: { kind: "human", name: "Kevin Osei" } },
      },
    };
  }
  return {
    status: state === "a" ? "drafting" : "draft",
    variant: "paper",
    structure: { kind: "kv", sheets: [SHEET] },
    title: "Return Summary",
    watermark: state === "b",
    actions: {
      edit: true,
      regenerate: true,
      approve: { actor: SAMUEL },
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

const t = (text: string): { kind: "text"; text: string } => ({ kind: "text", text });
const f = (text: string): { kind: "fact"; text: string } => ({ kind: "fact", text });
const tp = (...segments: { kind: "text" | "fact"; text: string }[]): DocBlock => ({
  kind: "p",
  provenance: "template",
  segments,
});
const h4 = (text: string): DocBlock => ({ kind: "h", level: 4, text, provenance: "template" });
const LETTERHEAD: DocBlock = {
  kind: "letterhead",
  firm: "Brightwater Hale LLP",
  lines: ["233 S Wacker Drive, Suite 4400 · Chicago, IL 60606"],
};
const DANIEL_SIGNS: DocBlock = {
  kind: "signature",
  name: "Daniel Reyes, CPA",
  title: "Tax Partner",
};

/** T10c: the Feld transmittal letter (template text; the balance cites its variable). */
const TRANSMITTAL: readonly DocBlock[] = [
  LETTERHEAD,
  tp(t("September 12, 2026")),
  tp(t("Jonah & Claire Feld · 2214 N Hoyne Avenue · Chicago, IL 60647")),
  tp(t("Dear Jonah and Claire,")),
  tp(
    t(
      "Your 2025 federal and Illinois income tax returns are ready for your review and signature. We prepared them from the documents you uploaded to your portal.",
    ),
  ),
  h4("Balance due"),
  {
    kind: "p",
    provenance: "template",
    segments: [
      t("Your federal return shows a balance due of "),
      f("3,482"),
      {
        kind: "cite",
        n: 1,
        verified: true,
        citation: {
          n: 1,
          title: "Letters › Transmittal Letter",
          quote: "3,482",
          loc: "Balance due",
          match: m("balance"),
        },
      },
      t(". Please pay by "),
      f("October 15, 2026"),
      t(" through IRS Direct Pay or with the enclosed voucher."),
    ],
  },
  h4("2026 estimated payments"),
  tp(
    t(
      "To avoid an underpayment penalty next year, we recommend four federal estimated payments of ",
    ),
    f("2,950"),
    t(" each."),
  ),
  h4("Filing"),
  tp(t("Once you sign Form 8879 in the portal, we will file both returns electronically.")),
  tp(t("Thank you for working with Brightwater Hale. Please reach out with any questions.")),
  DANIEL_SIGNS,
];

/** T10d: the Harborview K-1 cover letter, locked while the return is out for signature. */
const K1_COVER: readonly DocBlock[] = [
  LETTERHEAD,
  tp(t("September 10, 2026")),
  tp(t("To the partners of Harborview Dental Properties, LP")),
  tp(
    t(
      "Enclosed is your 2025 Schedule K-1 (Form 1065) from Harborview Dental Properties, LP. Keep it with your 2025 tax records.",
    ),
  ),
  h4("What to do with your K-1"),
  {
    kind: "ul",
    provenance: "template",
    items: [
      [t("Give it to whoever prepares your 2025 return")],
      [t("Report the amounts in boxes 1 and 2 on Schedule E")],
      [t("Check Item L for your ending capital account")],
    ],
  },
  h4("State K-1s"),
  tp(t("Illinois partners also receive a Schedule K-1-P for their Illinois return.")),
  DANIEL_SIGNS,
];

/** T10e: the Whitley document reminder email (draft), one dark call to action. */
const REMINDER: readonly DocBlock[] = [
  {
    kind: "h",
    level: 3,
    text: "Your 2025 tax documents are due September 30",
    provenance: "template",
  },
  tp(t("From Kevin Osei, Brightwater Hale · to Marcus & Dana Whitley")),
  tp(t("Hi Marcus and Dana,")),
  tp(t("We still need these documents for your 2025 return:")),
  {
    kind: "ul",
    provenance: "template",
    items: [
      [t("2025 Form 1099-INT from Bellco Credit Union")],
      [t("2025 Property tax statement · Denver County")],
      [t("2025 Form 5498 from Fidelity Investments")],
      [t("2025 Form 5498-SA from HealthEquity")],
      [t("Receipts for gifts of $250 or more")],
    ],
  },
  tp(
    t("Please upload them by "),
    f("September 30, 2026"),
    t(" so we can finish your return before the October 15 deadline."),
  ),
];

function LetterBody({ state }: { state: "c" | "d" | "e" }): JSX.Element {
  if (state === "e") {
    return (
      <div data-document="blocks">
        <DocBlocks blocks={REMINDER} variant="email" />
        <span
          data-email="cta"
          className="mt-[8px] inline-flex h-[34px] items-center rounded-pill bg-espresso px-[16px] text-body font-medium text-on-dark"
        >
          Open Your Binder
        </span>
        <p className="mt-[24px] pt-[14px] text-meta text-ink-3 hairline-t">
          Brightwater Hale LLP · 1700 Lincoln Street, Suite 2100, Denver, CO 80203
        </p>
      </div>
    );
  }
  return <DocBlocks blocks={state === "c" ? TRANSMITTAL : K1_COVER} variant="letter" />;
}

/** The record each board sits in (the artboards' headers and tabs, verbatim). */
const RECORD: Readonly<
  Record<
    T10State,
    {
      title: string;
      context: string;
      state: string;
      tabs: readonly (string | { label: string; count: number; bad?: boolean })[];
    }
  >
> = {
  a: { title: "2025 Form 1065", context: RIDGELINE, state: "In review · Partner", tabs: [] },
  b: { title: "2025 Form 1065", context: RIDGELINE, state: "In review · Partner", tabs: [] },
  c: {
    title: "2025 Form 1040",
    context: "Jonah & Claire Feld",
    state: "In review · Manager",
    tabs: [
      "Overview",
      { label: "Intake", count: 2 },
      { label: "Review", count: 37 },
      { label: "Issues", count: 4, bad: true },
      "Deliverables",
      "Activity",
    ],
  },
  d: {
    title: "2025 Form 1065",
    context: "Harborview Dental Properties, LP",
    state: "Awaiting signature",
    tabs: ["Agent", "Issues", "Workpaper", "Review", "Deliverables"],
  },
  e: {
    title: "2025 Form 1040",
    context: "Marcus & Dana Whitley",
    state: "Gathering",
    tabs: [
      "Overview",
      { label: "Intake", count: 9 },
      { label: "Review", count: 0 },
      { label: "Issues", count: 0, bad: true },
      "Deliverables",
      "Activity",
    ],
  },
};

const ENTITY_TABS = [
  "Agent",
  { label: "Issues", count: 9, bad: true },
  "Workpaper",
  "Review",
  "Deliverables",
];

export function T10Board({ state }: { state: T10State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const rec = RECORD[state];
  const letter = state === "c" || state === "d" || state === "e";
  return (
    <DocumentOnWell
      frame
      height={860}
      document={t10Document(state)}
      copy={{
        edit: COPY.edit,
        regenerate: COPY.regenerate,
        approved: COPY.approved,
        drafting: COPY.drafting,
        rendering: COPY.rendering,
        watermark: COPY.watermark,
        variables: COPY.variables,
      }}
      toolbar={specimenToolbar(firm, "Tax Returns")}
      record={
        <RecordHeader
          title={rec.title}
          context={rec.context}
          state={rec.state}
          checkpoints
          sync="synced"
          syncDate="Sep 11"
          assistant
        />
      }
      tabs={
        <div
          data-shell="tabsbar"
          className="flex h-(--tabs-h) flex-none items-center justify-center px-[12px]"
        >
          <SegmentedGroup
            size="small"
            label={letter ? rec.title : "Partnership return"}
            options={letter ? rec.tabs : ENTITY_TABS}
            active="Deliverables"
          />
        </div>
      }
      onApprove={() => undefined}
      onEdit={() => undefined}
      onRegenerate={() => undefined}
      onOpenLink={() => undefined}
    >
      {letter ? <LetterBody state={state} /> : <ReturnSummary />}
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
