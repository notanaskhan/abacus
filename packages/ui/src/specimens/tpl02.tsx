import { type JSX, type ReactNode, useState } from "react";
import { AgentText } from "../agent-text";
import { HumanAction } from "../attribution/human-action";
import { Button } from "../components/button";
import { SearchField } from "../components/inputs";
import { DoneCount } from "../components/pill";
import { EmptyState } from "../components/states";
import { DecisionCard } from "../gates/decision-card";
import { prose } from "../format";
import { PaneAction } from "../layout/pane";
import { RecordRail } from "../record";
import type { Phase, RailLink, RailSection } from "../record/types";
import { DockComposer, type DockView, RecordCockpit } from "../templates/record-cockpit";
import { SourceDocGroup, SourceDocRow } from "../workpaper/source-docs";
import type { SourceDoc } from "../workpaper/types";
import guards from "../../scope-guards.gen.json";
import { Artboard } from "./portal";
import {
  FIRM,
  NORTHWIND,
  NORTHWIND_FIGURES,
  NORTHWIND_PBC,
  NORTHWIND_PLAN,
  STAFF,
} from "./seed-figures";
import { pbcGroups } from "./workpaper-data";

// TPL-02 Record cockpit specimen, Northwind 401(k) audit (F-05-T51; handoff screens/TPL-02,
// Wave 0 Templates `#tpl02`): T2 with the dock at 9:41 AM, run #4127 started 9:24. The rail's
// "Source Documents · 11 of 24 received" is counted from the canvas's own rows (3 + 4 + 3 + 1), the
// documents are the seed's PBC list, and the trial balance tie reads the seed's figures. Every
// board is live: pick rail rows, collapse bands, search and sort the documents, open one in the
// viewer, Run and Retry. Dock content in a, c and d is the C-12 run kit's and the SHL-11 decision
// card's (P-04, P-09). F-05 R4: the run thread stays masked for parity (`data-parity-mask`) until
// C-12 lands (P-09); the decision card is unmasked with P-04-T49: in c the dock shows SHL-11's
// inline card (frame 5) for Materiality, read-only, with "Open decision" (the sheet decides).

const PERSON = { kind: "human", name: STAFF.hannah } as const;
// SHL-11 frame 5's question and two compact options, verbatim (P-04-T49; F-05 R4 unmask).
const MATERIALITY_QUESTION = "Which planning materiality should the Northwind PY2025 audit use?";
const MATERIALITY_OPTIONS = [
  { key: "1.0", label: "1.0% — $168,100" },
  { key: "1.5", label: "1.5% — $252,200", recommended: true },
] as const;
const TOOLBAR = {
  nav: guards.nav.map((label) => ({ label })),
  firm: FIRM,
  firmShort: "Brightwater",
  firmTitle: "Brightwater Hale LLP",
  active: "Audits",
} as const;

/** Received documents and requests: the rail's sub-line counts the canvas's rows. */
const RECEIVED = NORTHWIND_PBC.filter((d) => d.status === "received").length;
const RECEIVED_LINE = `${String(RECEIVED)} of ${String(NORTHWIND_PBC.length)} received`;

const LINKS: readonly RailLink[] = [
  { id: "client", icon: "user-round", title: "Client", sub: NORTHWIND },
  { id: "meth", icon: "layers", title: "Methodology", sub: "BH Audit Methodology · EBP v3" },
  { id: "std", icon: "book-open", title: "Standards set", sub: "GAAS nonissuer · AU-C 703" },
  { id: "docs", icon: "file", title: "Source Documents", sub: RECEIVED_LINE },
  { id: "team", icon: "users-round", title: "Team", sub: "MO · TW · HL · MD · AC" },
  { id: "act", icon: "clock", title: "Activity" },
];

/** The run projection of run #4127: 1 + 5 + 1 + 4 + 3 = 14 workpapers across 5 levels. */
export const RUN_PROJECTION = [
  { level: "Foundation", done: 1, total: 1 },
  { level: "Planning", done: 0, total: 5, note: "1 blocked · 1 running" },
  { level: "Sampling", done: 0, total: 1 },
  { level: "Testing", done: 0, total: 4 },
  { level: "Completion", done: 0, total: 3 },
] as const;
const WORKPAPERS = RUN_PROJECTION.reduce((n, l) => n + l.total, 0);

type Mode = "run" | "idle" | "fail" | "pills";

// [id, title, disc, sub-line, idle-rail pill]
const PLAN = [
  ["tb", "Trial Balance", "done", "Complete · 9:26 AM", "Ready"],
  ["mat", "Materiality", "warn", "Blocked on a partner decision", "In progress"],
  ["ra", "Risk Assessment", "run", "Running", "In progress"],
  ["gap", "General Audit Planning", "half", "Waiting on inputs", "In progress"],
  ["ic", "Internal Control", "half", "Waiting on inputs", "In progress"],
  ["soc", "Service Organizations & SOC 1", "todo", "Queued", ""],
] as const;
const FIELD = [
  ["ss", "Sample Selection", "half", "Waiting on inputs", "In progress"],
  ["test", "Testing", "todo", "Not started", ""],
] as const;

type Row = (typeof PLAN)[number] | (typeof FIELD)[number];

function phase(row: Row, mode: Mode, retrying: boolean): Phase {
  const [id, title, disc, sub, pill] = row;
  const base = { id, title, ...(id === "test" ? { begin: true } : {}) };
  if (mode === "pills") {
    if (pill === "Ready") return { ...base, disc: "done", pill: { kind: "ready", text: pill } };
    if (pill === "In progress")
      return { ...base, disc: "half", pill: { kind: "progress", text: pill } };
    return base;
  }
  if (mode === "idle") return { ...base, disc: "todo", live: { text: "Not started" } };
  if (id === "ic" && retrying) return { ...base, disc: "run", live: { text: "Running" } };
  if (id === "ic" && mode === "fail")
    return { ...base, disc: "fail", live: { text: "Failed — see run" } };
  return {
    ...base,
    disc,
    live: { text: sub, ...(id === "mat" ? { tone: "amber" as const } : {}) },
  };
}

function sections(mode: Mode, retrying: boolean): RailSection[] {
  return [
    { id: "pl", title: "Planning", phases: PLAN.map((r) => phase(r, mode, retrying)) },
    { id: "fw", title: "Fieldwork", phases: FIELD.map((r) => phase(r, mode, retrying)) },
    { id: "co", title: "Completion", collapsed: true, phases: [] },
    { id: "re", title: "Reporting", collapsed: true, phases: [] },
  ];
}

/** What a rail pick other than the documents or Materiality opens. */
const OTHER: Record<string, string> = {
  tb: "Trial Balance",
  ra: "Risk Assessment",
  gap: "General Audit Planning",
  ic: "Internal Control",
  soc: "Service Organizations & SOC 1",
  ss: "Sample Selection",
  test: "Testing",
  client: "Client",
  meth: "Methodology",
  std: "Standards set",
  team: "Team",
  act: "Activity",
};

// ---- Canvas: Source Documents ---------------------------------------------------------------------

function SourceDocuments({
  query,
  receivedFirst,
  open,
  onOpen,
}: {
  query: string;
  receivedFirst: boolean;
  open: string | null;
  onOpen: (doc: SourceDoc) => void;
}): JSX.Element {
  const q = query.trim().toLowerCase();
  const rank = (d: SourceDoc): number => ((d.status === "received") === receivedFirst ? 0 : 1);
  const groups = pbcGroups()
    .map((g) => ({
      ...g,
      shown: g.docs
        .filter((d) => q === "" || d.title.toLowerCase().includes(q))
        // A stable sort: Missing first keeps the seed's order inside each half.
        .map((d, i) => ({ d, i }))
        .sort((a, b) => rank(a.d) - rank(b.d) || a.i - b.i)
        .map(({ d }) => d),
    }))
    .filter((g) => g.shown.length > 0);
  if (groups.length === 0) {
    return <EmptyState icon="search" title={`No documents match ‘${query.trim()}’.`} />;
  }
  return (
    <div data-tpl02="documents" className="flex flex-col">
      {groups.map((g) => (
        <SourceDocGroup key={g.title} title={g.title} received={g.received} total={g.total}>
          {g.shown.map((doc) => (
            <SourceDocRow key={doc.id} doc={doc} selected={open === doc.id} onOpen={onOpen} />
          ))}
        </SourceDocGroup>
      ))}
    </div>
  );
}

// ---- Dock -----------------------------------------------------------------------------------------

function Narration({ text }: { text: string }): JSX.Element {
  return (
    <div className="rounded-nested bg-card px-[12px] py-[10px] shadow-e1">
      <AgentText text={text} />
    </div>
  );
}

function Projection(): JSX.Element {
  return (
    <div
      data-tpl02="projection"
      className="flex flex-col gap-[6px] rounded-nested bg-card px-[12px] py-[10px] text-dense shadow-e1"
    >
      <p className="font-medium">
        {`Run projection · ${String(WORKPAPERS)} workpapers · ${String(RUN_PROJECTION.length)} levels`}
      </p>
      {RUN_PROJECTION.map((l) => (
        <div key={l.level} className="flex items-center gap-[8px]">
          <span className="flex-1 text-ink-2">{l.level}</span>
          {"note" in l && <span className="text-pill-sm font-normal text-ink-3">{l.note}</span>}
          <DoneCount done={l.done} total={l.total} />
        </div>
      ))}
    </div>
  );
}

const money = (v: string): string => prose(v, "money");
const whole = (v: string): string => `$${prose(v, "whole")}`;

function Thread({ failed }: { failed: boolean }): JSX.Element {
  return (
    <div data-parity-mask="" className="flex flex-col gap-[8px] p-[10px]">
      <Projection />
      <p className="self-end rounded-dialog bg-espresso px-[12px] py-[8px] text-dense text-on-dark">
        yes, run it
      </p>
      <Narration text="Foundation level. Dispatching the Trial Balance workpaper first, in the order the run projection returns." />
      <Narration
        text={`Trial Balance is complete and agreed to the Harborline Trust Company net trust assets: ${money(NORTHWIND_FIGURES.netAssetsUnadjusted)} at 12/31/2025 (investments ${money(NORTHWIND_FIGURES.investmentsAtFairValue)} + participant notes ${money(NORTHWIND_FIGURES.participantNotes)}).`}
      />
      <Narration
        text={`Materiality v1 is proposed on unadjusted net assets of ${whole(NORTHWIND_FIGURES.netAssetsUnadjusted)}. Planning materiality is blocked on a partner decision (${STAFF.margaret}), so I am continuing with the branches it does not affect.`}
      />
      <Narration text="Sampling level is held until the census completeness tie and materiality are approved." />
      <p data-slot-note="" className="px-[4px] text-meta text-ink-3">
        {failed
          ? "The C-12 run rows fill this thread (P-04); the failed Internal Control row carries Retry."
          : "The C-12 run rows fill this thread (P-04)."}
      </p>
    </div>
  );
}

// ---- Boards ---------------------------------------------------------------------------------------

interface Board {
  id: string;
  badge: string;
  name: string;
  note: string;
  mode: Mode;
  sel: string;
}

const BOARDS: readonly Board[] = [
  {
    id: "tpl-02a",
    badge: "TPL-02a",
    name: "Default · 9:41 AM",
    note: "Run #4127 under way; Materiality is blocked",
    mode: "run",
    sel: "docs",
  },
  {
    id: "tpl-02b",
    badge: "TPL-02b",
    name: "Idle",
    note: "Before 9:24: ready to run 14 workpapers",
    mode: "idle",
    sel: "docs",
  },
  {
    id: "tpl-02c",
    badge: "TPL-02c",
    name: "Blocked focus",
    note: `Materiality picked: waiting on ${STAFF.margaret}`,
    mode: "run",
    sel: "mat",
  },
  {
    id: "tpl-02d",
    badge: "TPL-02d",
    name: "Failed step",
    note: "Internal Control failed; Retry in the dock",
    mode: "fail",
    sel: "docs",
  },
  {
    id: "tpl-02e",
    badge: "TPL-02e",
    name: "Idle rail variant",
    note: "Phase rows carry Ready and In progress pills",
    mode: "pills",
    sel: "docs",
  },
];

function Cockpit({ board }: { board: Board }): JSX.Element {
  const [mode, setMode] = useState<Mode>(board.mode);
  const [sel, setSel] = useState(board.sel);
  const [query, setQuery] = useState("");
  const [receivedFirst, setReceivedFirst] = useState(false);
  const [doc, setDoc] = useState<SourceDoc | null>(null);
  const [view, setView] = useState<DockView>("Agent");
  const [retrying, setRetrying] = useState(false);
  const idle = mode === "idle" || mode === "pills";
  const failed = mode === "fail" && !retrying;

  let canvas: { title: string; children: ReactNode; well?: boolean; docs?: boolean };
  if (sel === "docs") {
    canvas = {
      title: "Source Documents",
      docs: true,
      children: (
        <SourceDocuments
          query={query}
          receivedFirst={receivedFirst}
          open={doc?.id ?? null}
          onOpen={(d) => {
            setDoc(d);
            setView("Viewer");
          }}
        />
      ),
    };
  } else if (sel === "mat") {
    canvas = {
      title: "Materiality",
      well: true,
      children: (
        <EmptyState
          icon="triangle-alert"
          title={`Waiting on ${STAFF.margaret}`}
          className="m-auto max-w-[282px] flex-none rounded-pane bg-card shadow-e1"
          action={
            <Button variant="secondary" size="sm">
              Open decision →
            </Button>
          }
        >
          The engagement partner chooses the benchmark for planning materiality.
        </EmptyState>
      ),
    };
  } else {
    canvas = {
      title: OTHER[sel] ?? sel,
      children: (
        <EmptyState icon="file-text" title={OTHER[sel] ?? sel}>
          Opens in its own workpaper view.
        </EmptyState>
      ),
    };
  }

  const views: readonly DockView[] = doc === null ? ["Agent"] : ["Agent", "Viewer"];
  const dockBody =
    view === "Viewer" && doc !== null ? (
      <p data-slot-note="" className="px-[14px] py-[12px] text-meta text-ink-3">
        {`The C-08 SourceViewer opens ${doc.title} here (SHL-08).`}
      </p>
    ) : idle ? (
      <div className="flex flex-col items-center gap-[12px] px-[14px] pt-[28px] text-center">
        <p className="text-dense text-ink-2">
          {`Ready to run ${String(WORKPAPERS)} workpapers across ${String(RUN_PROJECTION.length)} levels`}
        </p>
        <Button
          size="lg"
          variant="primary"
          onClick={() => {
            setMode("run");
          }}
        >
          Run
        </Button>
      </div>
    ) : (
      <>
        {sel === "mat" && (
          <div className="px-[10px] pt-[10px]">
            <DecisionCard
              title={MATERIALITY_QUESTION}
              reservedNote={`Reserved to Engagement Partner · ${STAFF.margaret}`}
              options={MATERIALITY_OPTIONS}
              actor={PERSON}
              recommendationLabel="Recommended by Accrued Agent"
              openDecision={{ label: "Open decision", onOpen: () => undefined }}
            />
          </div>
        )}
        <Thread failed={failed} />
        {failed && (
          <div className="px-[10px] pb-[10px]">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setRetrying(true);
              }}
            >
              Retry
            </Button>
          </div>
        )}
      </>
    );

  return (
    <Artboard id={board.id} badge={board.badge} name={board.name} note={board.note}>
      <RecordCockpit
        embedded
        height={860}
        toolbar={TOOLBAR}
        record={{
          title: "PY2025 Employee Benefit Plan Audit",
          chip: "BH Audit Methodology · EBP v3",
          state: "Planning",
          ...(idle ? {} : { meta: "Started 9:24 AM" }),
        }}
        rail={
          <RecordRail
            card={{
              kind: "audit",
              title: NORTHWIND_PLAN,
              sub: `PY2025 · ${NORTHWIND}`,
              state: idle ? "Planning" : "Processing",
            }}
            links={LINKS}
            sections={sections(mode, retrying)}
            selected={sel}
            onOpen={(item) => {
              setSel(item.id);
            }}
          />
        }
        canvas={{
          title: canvas.title,
          ...(canvas.well === true ? { well: true } : {}),
          ...(canvas.docs === true
            ? {
                actions: (
                  <>
                    <PaneAction kind="icon" icon="list-filter" label="Filter" />
                    <PaneAction icon="file-plus" label="Add" />
                  </>
                ),
                controls: (
                  <>
                    <SearchField
                      label="Search"
                      placeholder="Search"
                      value={query}
                      onChange={setQuery}
                      className="min-w-0 flex-1"
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      icon="arrow-up-down"
                      onClick={() => {
                        setReceivedFirst(!receivedFirst);
                      }}
                    >
                      {receivedFirst ? "Received first" : "Missing first"}
                    </Button>
                  </>
                ),
              }
            : {}),
          children: canvas.children,
        }}
        dock={{
          view: views.includes(view) ? view : "Agent",
          views,
          onView: setView,
          live: !idle,
          action: (
            <HumanAction
              verb="Sign off"
              object="run"
              actor={PERSON}
              variant="secondary"
              size="sm"
              disabled
            />
          ),
          composer: <DockComposer placeholder="Message" />,
          children: dockBody,
        }}
      />
    </Artboard>
  );
}

/** One artboard on its own (the tests render a single board). */
export function Tpl02Board({ id }: { id: string }): JSX.Element | null {
  const board = BOARDS.find((b) => b.id === id);
  return board === undefined ? null : <Cockpit board={board} />;
}

export function Tpl02Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {BOARDS.map((b) => (
        <Cockpit key={b.id} board={b} />
      ))}
    </div>
  );
}
