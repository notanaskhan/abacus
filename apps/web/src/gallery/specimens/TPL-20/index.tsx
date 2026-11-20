import {
  type Actor,
  amount,
  Button,
  type CitationView,
  date,
  HumanAction,
  PersonAvatar,
  RecordCockpit,
  RecordRail,
  type RowDrawerTab,
  SheetLayout,
  type SheetGridColumn,
  type SheetGridRow,
  type SheetLayoutProps,
  type SheetRowSignOffs,
  type SheetRunSource,
  type SheetSection,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useSession } from "../../../app-core/session";
import { P } from "../../../fixtures/seed/collaboration";
import { SURL_SHEET } from "../../../fixtures/seed/granite-peak-fy2026-surl-sheet";
import type { FixtureParams } from "../../fixture-mode";
import { specimenToolbar } from "../firm-toolbar";
import { COPY } from "./copy";

// TPL-20 T18 Sheet specimen, Granite Peak FY2026 BH-FS-430 (F-08-T09; docs/screens/TPL-20.md):
// the SURL sheet on SheetLayout inside the T2 cockpit (audit bar 59 · rail 330 · canvas 1036;
// dock 330), viewer Cole Hart. Every figure is the F-08-T02 seed's (granite-peak-fy2026-surl-sheet,
// footed by granite-peak-fy2026.foot.test.ts); the specimen formats and never adds (ADR-050).
//
//   a  Mon Sep 28, 5:00 PM   every conclusion suggested, 0 adopted; Simone Baptiste on SURL-12
//   b  Sun Sep 27, 6:20 PM   the agent column running on the last two rows; 38 of 40 evidence;
//                            the screening flag on Granite Rock Logistics
//   c  Mon Sep 28, 5:00 PM   the row drawer on SURL-05, Agents tab: Improperly excluded, 2 citations
//   d  Mon Sep 28, 5:00 PM   the Exceptions view: SURL-05 alone, stratum 2 collapsed (0)
//   e  Thu Oct 1, 4:30 PM    P CH · R HL on every row, every row locked; "Signed off"
//   f  Thu Sep 24, 10:12 AM  empty from template
//   g  Mon Sep 28, 5:00 PM   the Agents dock open on the auto-started run (cockpit canvas 696)
//
// Registered for /components/screens/TPL-20?st=a…g. A P or R slot only opens the sign-off; the
// kit never signs (P-07), and Adopt in c only reports the intent (P-35, never optimistic).

export const TPL20_STATES = ["a", "b", "c", "d", "e", "f", "g"] as const;
export type Tpl20State = (typeof TPL20_STATES)[number];

/** The spec clock of each letter (F-08 §5 "Fixture scenarios"; spec epochs win, CT). */
export const TPL20_SCENARIOS: Record<Tpl20State, { clock: string; label: string }> = {
  a: { clock: "2026-09-28T17:00:00-05:00", label: "Mon Sep 28, 5:00 PM" },
  b: { clock: "2026-09-27T18:20:00-05:00", label: "Sun Sep 27, 6:20 PM" },
  c: { clock: "2026-09-28T17:00:00-05:00", label: "Mon Sep 28, 5:00 PM" },
  d: { clock: "2026-09-28T17:00:00-05:00", label: "Mon Sep 28, 5:00 PM" },
  e: { clock: "2026-10-01T16:30:00-05:00", label: "Thu Oct 1, 4:30 PM" },
  f: { clock: "2026-09-24T10:12:00-05:00", label: "Thu Sep 24, 10:12 AM" },
  g: { clock: "2026-09-28T17:00:00-05:00", label: "Mon Sep 28, 5:00 PM" },
};
export const TPL20_PERSONA = "cole-hart";

const EXCEPTION_ROW = "SURL-05";
const PRESENCE_ROW = "SURL-12";
/** b: the rows whose conclusion the run is still filling (two of 40 without evidence yet). */
const RUNNING_ROWS: ReadonlySet<string> = new Set(["SURL-13", "SURL-14"]);
const SCREENED_VENDOR = "Granite Rock Logistics";
const SIGNED_AT = "Oct 1, 4:30 PM";

const whole = (n: number): string => amount(String(n), "whole").text;

/** "2026-07-02" to "Jul 2" through format.ts (SPEC-048), in the scenario's year. */
const day = (iso: string): string => date(iso, { now: Date.parse("2026-09-28T17:00:00-05:00") });

export const TPL20_COLUMNS: readonly SheetGridColumn[] = [
  { key: "key", type: "text", label: COPY.columns.key, width: 96, frozen: true },
  { key: "vendor", type: "text", label: COPY.columns.vendor, width: 200 },
  { key: "paidOn", type: "date", label: COPY.columns.paidOn, width: 84 },
  { key: "amount", type: "currency", label: COPY.columns.amount, width: 104 },
  { key: "invoiceOn", type: "date", label: COPY.columns.invoiceOn, width: 104 },
  { key: "servicePeriod", type: "text", label: COPY.columns.servicePeriod, width: 150 },
  { key: "recordedIn", type: "text", label: COPY.columns.recordedIn, width: 120 },
  {
    key: "conclusion",
    type: "agent",
    label: COPY.columns.conclusion,
    width: 180,
    agent: { name: COPY.agentColumn },
  },
];

type SurlRow = (typeof SURL_SHEET.rows)[number];

/** SURL-05's two citations, from the seed row's own fields (typed locators, INV-2). */
export function surlCitations(r: SurlRow): CitationView[] {
  return [
    {
      n: 1,
      title: COPY.citations.posting,
      quote: r.recordedIn,
      loc: r.key,
      match: null,
    },
    {
      n: 2,
      title: COPY.citations.invoice,
      quote: `${day(r.invoiceOn)} · ${r.servicePeriod}`,
      loc: r.vendor,
      match: null,
      kind: "pdf",
    },
  ];
}

function conclusionCell(r: SurlRow, state: Tpl20State): SheetGridRow["cells"][string] {
  if (state === "b" && RUNNING_ROWS.has(r.key)) return { value: "", state: "empty" };
  const exception = r.conclusion.value === "improperly_excluded";
  const base = {
    value: COPY.conclusion[r.conclusion.value],
    ...(exception ? { exception: true, citations: surlCitations(r) } : {}),
  };
  if (state === "e") {
    return { ...base, state: "adopted", by: { kind: "human", name: P.cole.name }, at: "Oct 1" };
  }
  return { ...base, state: "suggested" };
}

export function tpl20Rows(state: Tpl20State): SheetGridRow[] {
  if (state === "f") return [];
  const rows =
    state === "d" ? SURL_SHEET.rows.filter((r) => r.key === EXCEPTION_ROW) : SURL_SHEET.rows;
  return rows.map((r) => ({
    key: r.key,
    sectionKey: r.sectionKey,
    locked: state === "e",
    version: 1,
    cells: {
      key: { value: r.key, state: "human" },
      vendor: { value: r.vendor, state: "human" },
      paidOn: { value: day(r.paidOn), state: "human", raw: r.paidOn },
      amount: { value: whole(r.amount), state: "human" },
      invoiceOn: { value: day(r.invoiceOn), state: "human", raw: r.invoiceOn },
      servicePeriod: { value: r.servicePeriod, state: "human" },
      recordedIn: { value: r.recordedIn, state: "human" },
      conclusion: conclusionCell(r, state),
    },
  }));
}

export function tpl20Sections(state: Tpl20State): SheetSection[] {
  if (state === "f") return [];
  return SURL_SHEET.sections.map((s) => {
    if (state !== "d")
      return { key: s.key, title: s.title, count: s.count, total: whole(s.total) };
    // d: the Exceptions view counts what it shows; stratum 2 collapses to (0).
    const count = tpl20Rows("d").filter((r) => r.sectionKey === s.key).length;
    return { key: s.key, title: s.title, count };
  });
}

export function tpl20SignOffs(state: Tpl20State): Record<string, SheetRowSignOffs> {
  if (state !== "e") return {};
  const chip = (who: typeof P.cole) => ({
    level: "",
    initials: who.initials,
    name: who.name,
    when: SIGNED_AT,
  });
  return Object.fromEntries(
    tpl20Rows("e").map((r) => [r.key, { P: chip(P.cole), R: chip(P.hannah) }]),
  );
}

function runSource(state: Tpl20State): SheetRunSource | undefined {
  if (state !== "b") return undefined;
  const snapshot = { running: true, pendingRowKeys: RUNNING_ROWS };
  return { subscribe: () => () => undefined, getSnapshot: () => snapshot };
}

function status(state: Tpl20State): SheetLayoutProps["grid"]["status"] {
  if (state === "f") return { rows: 0, exceptions: 0, view: COPY.views.all };
  const adopted = tpl20Rows(state).filter((r) => r.cells.conclusion?.state === "adopted").length;
  return {
    rows: SURL_SHEET.status.rows,
    exceptions: SURL_SHEET.status.exceptions,
    view: state === "d" ? COPY.views.exceptions : COPY.views.all,
    agentSummary: COPY.adopted(adopted),
    ...(state === "b" ? { agentRunning: true } : {}),
  };
}

function AgentsTab({
  viewer,
  onIntent,
}: {
  viewer: Actor;
  onIntent: (intent: string) => void;
}): JSX.Element {
  const r = SURL_SHEET.rows.find((x) => x.key === EXCEPTION_ROW);
  if (r === undefined) return <></>;
  const cites = surlCitations(r);
  return (
    <div data-drawer-agents="" className="flex flex-col gap-[10px] text-dense">
      <p className="text-body font-medium text-ink-2">{COPY.conclusion[r.conclusion.value]}</p>
      <p className="text-ink-3">{COPY.drawer.suggested}</p>
      <ol aria-label="Citations" className="flex flex-col gap-[4px]">
        {cites.map((c) => (
          <li key={c.n} data-citation={c.n} className="text-ink-2">
            {`${String(c.n)}. ${c.title} · ${c.loc}`}
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap gap-[6px]">
        <HumanAction
          verb={COPY.drawer.adopt}
          actor={viewer}
          variant="secondary"
          size="sm"
          onClick={() => {
            onIntent("adopt");
          }}
        />
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            onIntent("edit");
          }}
        >
          {COPY.drawer.edit}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          opensDialog
          onClick={() => {
            onIntent("raise");
          }}
        >
          {COPY.drawer.raise}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            onIntent("expand");
          }}
        >
          {COPY.drawer.expand}
        </Button>
      </div>
    </div>
  );
}

export interface Tpl20BoardProps {
  state: Tpl20State;
  onOpenSignOff?: (rowKeys: readonly string[], level: "P" | "R") => void;
  onIntent?: (intent: string) => void;
}

export function Tpl20Board({ state, onOpenSignOff, onIntent }: Tpl20BoardProps): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const viewer: Actor = { kind: "human", name: P.cole.name };
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<RowDrawerTab>("Agents");
  const [drawerOpen, setDrawerOpen] = useState(state === "c");
  const intent = onIntent ?? (() => undefined);
  const dockOpen = state === "g";
  const exception = SURL_SHEET.rows.find((x) => x.key === EXCEPTION_ROW);
  const run = runSource(state);
  const layout: SheetLayoutProps = {
    variant: dockOpen ? "cockpit" : "full",
    view: state === "f" ? "empty" : "ready",
    toolbar: {
      view: state === "d" ? COPY.views.exceptions : COPY.views.all,
      savedViews: COPY.savedViews,
      filters: state === "d" ? 1 : 0,
      search,
      onSearch: setSearch,
    },
    grid: {
      label: SURL_SHEET.procedure,
      columns: TPL20_COLUMNS,
      sections: tpl20Sections(state),
      rows: tpl20Rows(state),
      status: status(state),
      viewer,
      height: 560,
      onAdopt: () => {
        intent("adopt");
        return Promise.resolve();
      },
      onOpenRow: () => {
        setDrawerOpen(true);
      },
      ...(run === undefined ? {} : { run }),
    },
    signOffs: tpl20SignOffs(state),
    onOpenSignOff: onOpenSignOff ?? (() => undefined),
    ...(state === "a"
      ? {
          presence: (
            <span
              data-presence-row={PRESENCE_ROW}
              className="flex items-center gap-[6px] text-dense text-ink-3"
            >
              <PersonAvatar name={P.simone.name} tint={2} />
              {COPY.presence(P.simone.name, PRESENCE_ROW)}
            </span>
          ),
        }
      : {}),
    ...(drawerOpen && exception !== undefined
      ? {
          drawer: {
            rowKey: exception.key,
            title: COPY.drawer.title(exception.key, exception.vendor),
            tab,
            onTab: setTab,
            onClose: () => {
              setDrawerOpen(false);
            },
            slots: { Agents: <AgentsTab viewer={viewer} onIntent={intent} /> },
          },
        }
      : {}),
  };
  const pending = run?.getSnapshot().pendingRowKeys?.size ?? 0;
  return (
    <RecordCockpit
      frame
      height={860}
      toolbar={specimenToolbar(firm, "Audits")}
      record={{
        title: SURL_SHEET.procedure,
        context: COPY.context,
        state: state === "e" ? COPY.state.signedOff : COPY.state.working,
        backLabel: COPY.backLabel,
        meta: TPL20_SCENARIOS[state].label,
      }}
      rail={
        <RecordRail
          title={COPY.rail.title}
          links={[{ id: "bh-fs-430", title: COPY.rail.procedure }]}
          selected="bh-fs-430"
        />
      }
      canvas={{
        title: COPY.rail.procedure,
        ...(state === "b"
          ? {
              controls: (
                <span data-run-line="" className="flex gap-[12px] text-dense text-ink-3">
                  <span>
                    {COPY.evidence(SURL_SHEET.status.rows - pending, SURL_SHEET.status.rows)}
                  </span>
                  <span data-screening="">{COPY.screening(SCREENED_VENDOR)}</span>
                </span>
              ),
            }
          : {}),
        children: <SheetLayout {...layout} />,
      }}
      dock={{
        view: "Agent",
        title: COPY.dock.title,
        live: dockOpen,
        children: (
          <p data-dock-run="" className="p-[10px] text-dense text-ink-2">
            {COPY.dock.run}
          </p>
        ),
      }}
      dockOpen={dockOpen}
    />
  );
}

export function Tpl20Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: Tpl20State = TPL20_STATES.find((s) => s === params.st) ?? "a";
  const [signOff, setSignOff] = useState<string | null>(null);
  const [intent, setIntent] = useState<string | null>(null);
  return (
    <div
      data-artboard={state}
      data-clock={params.clock ?? TPL20_SCENARIOS[state].clock}
      data-persona={params.as ?? TPL20_PERSONA}
      {...(signOff === null ? {} : { "data-opened-sign-off": signOff })}
      {...(intent === null ? {} : { "data-intent": intent })}
    >
      <Tpl20Board
        state={state}
        onIntent={setIntent}
        onOpenSignOff={(keys, level) => {
          setSignOff(`${keys.join(",")}:${level}`);
        }}
      />
    </div>
  );
}
