import { type JSX, type ReactNode, useState } from "react";
import { AgentText } from "../agent-text";
import { HumanAction } from "../attribution/human-action";
import { Button } from "../components/button";
import { EmptyState } from "../components/states";
import { Segmented } from "../components/tabs";
import { DataGrid } from "../data/data-grid";
import { PaneAction } from "../layout/pane";
import {
  AboutCard,
  GroupBand,
  OverviewCard,
  PhaseRow,
  RailRow,
  RecordRail,
  RecordSummary,
  StatusDropdownPill,
} from "../record";
import type { Phase, RailLink, RailSection } from "../record/types";
import {
  type CockpitCanvas,
  DockComposer,
  type DockView,
  RecordCockpit,
} from "../templates/record-cockpit";
import guards from "../../scope-guards.gen.json";
import { WorkpaperPane } from "../workpaper/workpaper";
import { LEDGER_COLUMNS, LEDGER_ROWS } from "./data";
import { Held, Row, Sheet } from "./frame";
import { Artboard } from "./portal";
import {
  COPPERLEAF,
  FIRM,
  NORTHWIND,
  NORTHWIND_PLAN,
  REQUEST_COUNTS,
  STAFF,
} from "./seed-figures";
import { SOC_TABS } from "./workpaper-data";

// C-03 Rail kit, C-04 Record kit and the T2 RecordCockpit frame (F-05-T40). The names and counts
// are the Brightwater Hale seed's (seed-figures.ts); the T2 artboards' words are the T2 handoff's
// (Northwind Robotics 401(k) Plan, PY2025 EBP audit, Mon Sep 14, 2026). Kit sample data is never
// ported. T2b's canvas is the C-02 Workpaper kit (F-05-T50); the dock holds slot notes where its
// kits (C-12 run rows, SHL-11 decision card) are later tasks.

// A named person: human-only verbs render only through HumanAction (INV-1).
const PERSON = { kind: "human", name: STAFF.hannah } as const;
const NAV = guards.nav.map((label) => ({ label }));
const TOOLBAR = {
  nav: NAV,
  firm: FIRM,
  firmShort: "Brightwater",
  firmTitle: "Brightwater Hale LLP",
  active: "Audits",
} as const;

const NW = REQUEST_COUNTS.northwind;
const LINKS: readonly RailLink[] = [
  { id: "client", icon: "user-round", title: "Client", sub: NORTHWIND },
  {
    id: "requests",
    icon: "inbox",
    title: "Requests",
    sub: `PBC ${String(NW.received)} of ${String(NW.total)} received`,
    elsewhere: true,
  },
  {
    id: "methodology",
    icon: "notebook-text",
    title: "Methodology",
    sub: "BH Audit Methodology · EBP v3",
    elsewhere: true,
  },
  { id: "source", icon: "folder", title: "Source Documents", elsewhere: true },
];

const READY = { kind: "ready", text: "Ready" } as const;
const IN_PROGRESS = { kind: "progress", text: "In progress" } as const;

function done(id: string, title: string, at: string): Phase {
  return { id, title, disc: "done", live: { text: `Complete · ${at}` } };
}

/** The rail's sections for one artboard: Planning's six phases, then the later groups. */
function sections(planning: readonly Phase[]): RailSection[] {
  return [
    { id: "planning", title: "Planning", phases: planning },
    {
      id: "fieldwork",
      title: "Fieldwork",
      phases: [done("plan-review", "Plan Review", "Sep 11")],
    },
    { id: "testing", title: "Testing", collapsed: true, phases: [] },
    { id: "completion", title: "Completion", collapsed: true, phases: [] },
    { id: "reporting", title: "Reporting", collapsed: true, phases: [] },
  ];
}

const TB: Phase = { id: "tb", title: "Trial Balance", disc: "prepared", pill: READY };
const GAP: Phase = { id: "gap", title: "General Audit Planning", disc: "half", pill: IN_PROGRESS };

interface Board {
  state: string;
  meta?: string;
  planning: readonly Phase[];
  selected: string;
}

const BOARDS: Record<"a" | "b" | "c" | "d" | "e", Board> = {
  a: {
    state: "Planning",
    selected: "tb",
    planning: [
      TB,
      { id: "mat", title: "Materiality" },
      { id: "risk", title: "Risk Assessment", begin: true },
      GAP,
      { id: "ic", title: "Internal Control" },
      { id: "soc", title: "Service Organizations & SOC 1" },
    ],
  },
  b: {
    state: "Processing",
    meta: "Started 9:24 AM",
    selected: "soc",
    planning: [
      TB,
      { id: "mat", title: "Materiality", disc: "run", live: { text: "Running" } },
      { id: "risk", title: "Risk Assessment", disc: "run", live: { text: "Running" } },
      GAP,
      { id: "ic", title: "Internal Control", live: { text: "Queued" } },
      done("soc", "Service Organizations & SOC 1", "9:36 AM"),
    ],
  },
  c: {
    state: "Processing",
    meta: "Started 9:24 AM",
    selected: "mat",
    planning: [
      TB,
      {
        id: "mat",
        title: "Materiality",
        disc: "warn",
        live: { text: "Blocked on a partner decision", tone: "amber" },
      },
      done("risk", "Risk Assessment", "9:38 AM"),
      GAP,
      { id: "ic", title: "Internal Control", disc: "run", live: { text: "Running" } },
      done("soc", "Service Organizations & SOC 1", "9:36 AM"),
    ],
  },
  d: {
    state: "Planning",
    meta: "Stopped 9:40 AM",
    selected: "ic",
    planning: [
      TB,
      done("mat", "Materiality", "9:39 AM"),
      done("risk", "Risk Assessment", "9:38 AM"),
      GAP,
      { id: "ic", title: "Internal Control", disc: "fail", live: { text: "Failed — see run" } },
      done("soc", "Service Organizations & SOC 1", "9:36 AM"),
    ],
  },
  e: {
    state: "Planning",
    selected: "risk",
    planning: [
      TB,
      { id: "mat", title: "Materiality" },
      { id: "risk", title: "Risk Assessment", begin: true },
      GAP,
      { id: "ic", title: "Internal Control" },
      { id: "soc", title: "Service Organizations & SOC 1" },
    ],
  },
};

/** Where a later kit fills the frame: said in words, in the slot it fills. */
function SlotNote({ children }: { children: ReactNode }): JSX.Element {
  return (
    <p data-slot-note="" className="px-[14px] py-[12px] text-meta text-ink-3">
      {children}
    </p>
  );
}

/** One agent narration card in the dock (C-10 sizes): the words through AgentText. */
function Narration({ text }: { text: string }): JSX.Element {
  return (
    <div className="mx-[10px] mt-[10px] rounded-nested bg-card px-[12px] py-[10px] shadow-e1">
      <AgentText text={text} />
    </div>
  );
}

function Rail({ board }: { board: Board }): JSX.Element {
  return (
    <RecordRail
      card={{
        kind: "audit",
        title: NORTHWIND_PLAN,
        sub: `PY2025 · ${NORTHWIND}`,
        state: board.state,
      }}
      links={LINKS}
      sections={sections(board.planning)}
      selected={board.selected}
    />
  );
}

const ACTIONS = (
  <>
    <PaneAction icon="pencil" label="Edit" />
    <HumanAction verb="Sign off" actor={PERSON} variant="secondary" size="sm" opensDialog />
    <PaneAction icon="file-text" label="Source Docs" />
  </>
);

function Cockpit({
  id,
  name,
  note,
  board,
  title,
  canvas,
  dock,
}: {
  id: string;
  name: string;
  note: string;
  board: Board;
  title: string;
  canvas: Omit<CockpitCanvas, "title">;
  dock?: { live?: boolean; run?: boolean; body: ReactNode } | undefined;
}): JSX.Element {
  const [view, setView] = useState<DockView>("Agent");
  return (
    <Artboard id={id} badge={id.toUpperCase()} name={name} note={note}>
      <RecordCockpit
        embedded
        height={860}
        toolbar={TOOLBAR}
        record={{
          title: NORTHWIND_PLAN,
          context: "PY2025 EBP Audit",
          chip: "BH Audit Methodology · EBP v3",
          state: board.state,
          ...(board.meta === undefined ? {} : { meta: board.meta }),
        }}
        rail={<Rail board={board} />}
        canvas={{ title, ...canvas }}
        defaultDockOpen={dock !== undefined}
        dock={{
          view,
          onView: setView,
          live: dock?.live === true,
          ...(dock?.run === true
            ? {
                action: (
                  <Button size="lg" variant="primary">
                    Run
                  </Button>
                ),
              }
            : {}),
          composer: <DockComposer placeholder="Message Accrued Agent" />,
          children:
            view === "Agent" ? (
              dock?.body
            ) : (
              <SlotNote>{`${view}: the ${view === "Viewer" ? "C-08 SourceViewer" : "notes"} kit fills this view.`}</SlotNote>
            ),
        }}
      />
    </Artboard>
  );
}

export function RecordCockpitSpecimen(): JSX.Element {
  // T2b: the canvas's control row drives the workpaper's tab (chrome={false}, C-02 §1).
  const [socTab, setSocTab] = useState(SOC_TABS[0]?.label ?? "");
  return (
    <div className="flex flex-col gap-6">
      <Cockpit
        id="t2a"
        name="Idle"
        note="No run yet, so Run sits in the dock header. Trial Balance is open"
        board={BOARDS.a}
        title="Trial Balance"
        canvas={{
          actions: ACTIONS,
          controls: (
            <>
              <Segmented size="small" label="View" options={["Statement", "Workbook"]} />
              <span className="ml-auto">
                <PaneAction kind="meta" icon="file-spreadsheet" label="Open in Excel" />
              </span>
            </>
          ),
          children: (
            <DataGrid label="Northwind net assets" columns={LEDGER_COLUMNS} rows={LEDGER_ROWS} />
          ),
        }}
        dock={{
          run: true,
          body: (
            <Narration text="When you run Planning, I'll work through service organizations, risk assessment, materiality and internal control. I'll stop when a step needs a partner or manager to decide." />
          ),
        }}
      />
      <Cockpit
        id="t2b"
        name="Running"
        note="Started 9:24 AM. Spinner rows in the rail, the live dot in the dock"
        board={BOARDS.b}
        title="Service Organizations & SOC 1"
        canvas={{
          actions: ACTIONS,
          controls: (
            <Segmented
              size="small"
              label="Workpaper"
              options={SOC_TABS.map((t) => t.label)}
              active={socTab}
              onChange={setSocTab}
            />
          ),
          children: <WorkpaperPane tabs={SOC_TABS} chrome={false} active={socTab} />,
        }}
        dock={{
          live: true,
          body: (
            <Narration text="I'm running Planning for the PY2025 audit, starting with service organizations, risk assessment and materiality." />
          ),
        }}
      />
      <Cockpit
        id="t2c"
        name="Blocked on a role decision"
        note="Materiality waits for the engagement partner to choose a benchmark"
        board={BOARDS.c}
        title="Materiality"
        canvas={{
          actions: ACTIONS,
          well: true,
          children: <SlotNote>The benchmark card and materiality tiles fill the canvas.</SlotNote>,
        }}
        dock={{
          live: true,
          body: (
            <>
              <Narration text="Materiality needs the engagement partner to choose a benchmark." />
              <SlotNote>{`The decision card (SHL-11) asks ${STAFF.margaret} here.`}</SlotNote>
            </>
          ),
        }}
      />
      <Cockpit
        id="t2d"
        name="Failed step"
        note="Internal Control stopped on a locked file; Retry is in the run"
        board={BOARDS.d}
        title="Internal Control"
        canvas={{
          actions: <PaneAction icon="file-text" label="Source Docs" />,
          children: (
            <EmptyState
              tone="error"
              icon="lock"
              title="Internal Control didn’t finish"
              action={
                <Button variant="secondary" size="sm">
                  Retry
                </Button>
              }
            >
              Accrued Agent couldn’t open Walkthrough narrative 2025.docx because it’s password
              protected. Upload an unlocked copy, then retry.
            </EmptyState>
          ),
        }}
        dock={{
          body: (
            <Narration text="Internal Control stopped because I couldn't open the walkthrough narrative. Upload an unlocked copy and choose Retry, and I'll pick up from there." />
          ),
        }}
      />
      <Cockpit
        id="t2e"
        name="Empty canvas"
        note="Risk Assessment hasn’t started. The dock is closed, so the canvas runs to x1388"
        board={BOARDS.e}
        title="Risk Assessment"
        canvas={{
          actions: (
            <>
              <PaneAction icon="file-text" label="Source Docs" />
              <PaneAction kind="icon" icon="ellipsis" label="More" />
            </>
          ),
          state: { kind: "empty" },
          empty: {
            icon: "file-text",
            title: "Risk Assessment hasn’t started",
            body: "Begin this phase and Accrued Agent drafts its workpaper from the binder and source documents.",
            action: (
              <Button variant="secondary" size="sm">
                Begin…
              </Button>
            ),
          },
        }}
      />
    </div>
  );
}

// ---- C-03 Rail kit ------------------------------------------------------------------------------

const STATE_PHASES: readonly { name: string; phase: Phase }[] = [
  { name: "Ready (pill)", phase: TB },
  { name: "In progress (pill)", phase: GAP },
  {
    name: "Waiting on inputs (pill)",
    phase: {
      id: "w",
      title: "Sample Selection",
      disc: "todo",
      pill: { kind: "waiting", text: "Waiting on inputs" },
    },
  },
  { name: "Complete (live)", phase: done("c", "Plan Review", "Sep 11") },
  { name: "Running (live)", phase: BOARDS.b.planning[1] ?? TB },
  { name: "Queued (live)", phase: BOARDS.b.planning[4] ?? TB },
  { name: "Blocked (amber live)", phase: BOARDS.c.planning[1] ?? TB },
  { name: "Failed (fail disc, red title)", phase: BOARDS.d.planning[4] ?? TB },
  { name: "Begin…", phase: { id: "b", title: "Risk Assessment", begin: true } },
];

export function RailKitSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <Sheet title="RecordRail: default" meta="330 · header 46 · card · links · bands">
        <Row name="Audit" meaning="Testing, Completion and Reporting start collapsed">
          <div className="flex h-[620px] rounded-pane bg-shell p-[10px]">
            <RecordRail
              card={{
                kind: "audit",
                title: NORTHWIND_PLAN,
                sub: `PY2025 · ${NORTHWIND}`,
                state: "Planning",
              }}
              links={LINKS}
              sections={[
                { id: "activity", title: "Activity", nav: true },
                ...sections(BOARDS.a.planning),
              ]}
              selected="tb"
            />
          </div>
        </Row>
        <Row name="Outline" meaning="Audit program: uppercase headers, 13px titles, no collapse">
          <div className="flex h-[360px] rounded-pane bg-shell p-[10px]">
            <RecordRail
              variant="outline"
              sections={[
                { id: "p", title: "Planning", phases: BOARDS.c.planning.slice(0, 3) },
                {
                  id: "f",
                  title: "Fieldwork",
                  phases: [
                    {
                      ...done("pr", "Plan Review", "Sep 11"),
                      children: [
                        done("pr-2", "Version 2", "Sep 11"),
                        done("pr-1", "Version 1", "Sep 10"),
                      ],
                    },
                  ],
                },
              ]}
            />
          </div>
        </Row>
      </Sheet>
      <Sheet title="Rows" meta="38 min · disc and words, never colour alone">
        <Row name="Phase rows" meaning="Every second line">
          <div className="flex w-[330px] flex-col rounded-pane bg-card shadow-e2">
            {STATE_PHASES.map(({ name, phase }) => (
              <div key={name} className="contents" title={name}>
                <PhaseRow phase={phase} />
              </div>
            ))}
          </div>
        </Row>
        <Row name="Row states" meaning="Hover, pressed, selected, focus">
          {(["hover", "pressed", "focus"] as const).map((s) => (
            <Held key={s} name={s}>
              <div className="w-[330px] rounded-pane bg-card shadow-e2">
                <PhaseRow phase={{ id: s, title: "Internal Control" }} forceState={s} />
              </div>
            </Held>
          ))}
          <Held name="selected">
            <div className="w-[330px] rounded-pane bg-card shadow-e2">
              <PhaseRow phase={TB} selected />
            </div>
          </Held>
        </Row>
        <Row name="Links" meaning="Chevron in place, arrow elsewhere; compact uses discs">
          <div className="w-[330px] rounded-pane bg-card shadow-e2">
            {LINKS.map((link) => (
              <RailRow key={link.id} link={link} />
            ))}
            <RailRow link={{ id: "k", title: "Client", sub: NORTHWIND, disc: "done" }} compact />
          </div>
        </Row>
        <Row name="Bands" meaning="Navigating, open, collapsed">
          <div className="w-[330px] rounded-pane bg-card shadow-e2">
            <GroupBand title="Activity" nav />
            <GroupBand title="Planning" open />
            <GroupBand title="Testing" open={false} />
          </div>
        </Row>
        <Row name="Row menu" meaning="Open · Assign… · Mark as Done · Skip phase…">
          <div className="h-[200px] w-[330px]">
            <div className="rounded-pane bg-card shadow-e2">
              <PhaseRow phase={GAP} menuForceState="open" />
            </div>
          </div>
        </Row>
      </Sheet>
    </div>
  );
}

// ---- C-04 Record kit ----------------------------------------------------------------------------

const PEOPLE = [STAFF.priya, STAFF.raj, STAFF.daniel];

export function RecordKitSpecimen(): JSX.Element {
  const [status, setStatus] = useState("In progress");
  const [preparer, setPreparer] = useState<{ name: string; signed: boolean }>({
    name: STAFF.raj,
    signed: true,
  });
  return (
    <div className="flex flex-col gap-3">
      <Sheet title="OverviewCard" meta="Recessed, centred · tile 34 espresso · state pill 21">
        <Row name="Kinds and tones" meaning="Audit, tax, close; in flight, done, ready, muted">
          <div className="w-[330px] rounded-pane bg-card shadow-e2">
            <OverviewCard
              kind="audit"
              title={NORTHWIND_PLAN}
              sub={`PY2025 · ${NORTHWIND}`}
              state="Processing"
            />
          </div>
          <div className="w-[330px] rounded-pane bg-card shadow-e2">
            <OverviewCard kind="tax" title={COPPERLEAF} sub="TY2025 · Form 1120-S" state="Filed" />
          </div>
          <div className="w-[330px] rounded-pane bg-card shadow-e2">
            <OverviewCard kind="close" title={COPPERLEAF} sub="August 2026" state="Not started" />
          </div>
          <div className="w-[330px] rounded-pane bg-card shadow-e2">
            <OverviewCard
              kind="audit"
              title={NORTHWIND_PLAN}
              sub="PY2025"
              state="Waiting on inputs"
            />
          </div>
        </Row>
        <Row name="AboutCard" meaning="Tile 44 · 14.5 title · 12.5 body">
          <div className="w-[330px] rounded-pane bg-card shadow-e2">
            <AboutCard
              icon="atom"
              title="Agents"
              body="Agents follow written instructions, cite every source they use and wait for your approval before anything posts."
            />
          </div>
        </Row>
      </Sheet>
      <Sheet title="Close summary" meta="Status pill 25 · stats ≤ 15px · bands 31 · KV 33">
        <Row name="Summary" meaning="Allowed transitions only; a new person clears the sign-off">
          <div className="w-[330px] rounded-pane bg-card shadow-e2">
            <RecordSummary
              period="August 2026 Close"
              status={status}
              onStatus={(next) => {
                setStatus(next);
              }}
              stats={[
                { id: "issues", value: "7", caption: "Open issues" },
                { id: "progress", value: "43% (9 / 21)", caption: "Tasks complete" },
                { id: "due", value: "4 days", caption: "Past Due (Sep 10)", overdue: true },
              ]}
              people={PEOPLE}
              onAssign={(_, name) => {
                setPreparer({ name, signed: false });
              }}
              groups={[
                {
                  title: "Details",
                  rows: [
                    { id: "client", label: "Client", value: COPPERLEAF, kind: "link" },
                    { id: "period", label: "Period", value: "August 2026" },
                  ],
                },
                {
                  title: "Review and Delivery",
                  rows: [
                    {
                      id: "preparer",
                      label: "Preparer",
                      value: preparer.name,
                      kind: "person",
                      signed: preparer.signed,
                    },
                    {
                      id: "reviewer",
                      label: "Reviewer",
                      value: STAFF.priya,
                      kind: "person",
                      signed: false,
                    },
                    {
                      id: "binder",
                      label: "Binder",
                      value: "August 2026",
                      kind: "link",
                      trail: "arrow",
                    },
                  ],
                },
              ]}
            />
          </div>
        </Row>
        <Row name="Status menu" meaning="In progress moves to In review or Not started">
          <div className="h-[140px]">
            <StatusDropdownPill status="In progress" forceState="open" />
          </div>
        </Row>
      </Sheet>
    </div>
  );
}
