import { type JSX, useEffect, useRef, useState } from "react";
import { Button, IconButton } from "../components/button";
import { SearchField } from "../components/inputs";
import { SegmentedGroup } from "../components/tabs";
import { Toast } from "../components/toast";
import { DataGrid } from "../data/data-grid";
import { FieldBlock } from "../data/fields";
import {
  IssueComposer,
  IssueDetail,
  IssueFooter,
  type IssueGroup,
  IssueQueue,
  type IssueState,
} from "../issues/issue-kit";
import { Pane } from "../layout/pane";
import { RecordHeader } from "../layout/record-header";
import { Tabsbar } from "../layout/tabsbar";
import { type QueuePreset, QueueDetailLayout } from "../templates/queue-detail";
import { createMatchStore } from "../tracing/match-store";
import type { CitationPayload, MatchId } from "../tracing/types";
import { SourceViewer } from "../viewer/source-viewer";
import guards from "../../scope-guards.gen.json";
import { FELD_DOCS, feldRegions, feldWorksheets } from "./feld-t3";
import { Artboard } from "./portal";
import { COPPERLEAF, FELD, FIRM, RIDGELINE, STAFF } from "./seed-figures";
import {
  CO_EXPLAIN,
  COPPERLEAF_GROUPS,
  COPPERLEAF_ISSUES,
  DIV3B_MATCH,
  FELD_GROUPS,
  FELD_ISSUES,
  REGISTER_COLUMNS,
  REGISTER_ROWS,
  T9_PEOPLE,
  type T9Issue,
  registerMatch,
  ridgelineGroups,
  ridgelineIssue,
} from "./t9-data";
import { FORM_PAGE_PNG } from "./viewer-pages";

// T9 QueueDetailLayout (F-05-T55; T9 handoff, Wave 0 Foundations #t9): the three presets on the
// C-17 Issue kit, states T9a to T9e. Every board is live: pick issues (↑ ↓ too), reassign them (the
// agent is one of the assignees), explain, resolve or mark not applicable, send fix instructions
// (the issue turns "Agent working…" and the agent fixes it), and hover a workbook cell or a linked
// entity to light its source. The viewer is Samuel Ito; the agent is never offered Resolve.

const VIEWER = { kind: "human", name: STAFF.samuel } as const;

const toolbar = (active: string) =>
  ({
    nav: guards.nav.map((label) => ({ label })),
    firm: FIRM,
    firmShort: "Brightwater",
    firmTitle: "Brightwater Hale LLP",
    active,
  }) as const;

const RETURN_TABS = [
  "Overview",
  { label: "Intake", count: 2 },
  { label: "Review", count: 37 },
  { label: "Issues", count: 4, bad: true },
  "Activity",
];
const CLOSE_TABS = [
  "Overview",
  "Intake",
  "Accounts",
  { label: "Review", count: 7, bad: true },
  "Deliverables",
];
const ENTITY_TABS = ["Agent", { label: "Issues", count: 9, bad: true }, "Workpaper", "Review"];

const VIEWER_MENU = [
  { label: "Download", onSelect: () => undefined },
  { label: "Open in Files", onSelect: () => undefined },
];

interface Board {
  id: string;
  badge: string;
  name: string;
  note: string;
  preset: QueuePreset;
  selected: string | null;
  states?: Readonly<Record<string, IssueState>>;
}

const BOARDS: readonly Board[] = [
  {
    id: "t9a",
    badge: "T9a",
    name: "Issues · individual",
    note: "Feld 1040: queue and detail cards in the well, beside the viewer and the worksheet",
    preset: "issues-individual",
    selected: "div3b",
  },
  {
    id: "t9b",
    badge: "T9b",
    name: "Close review",
    note: "Copperleaf August close: one 790 pane split 310 and 480, beside the register",
    preset: "close-review",
    selected: "dup",
  },
  {
    id: "t9c",
    badge: "T9c",
    name: "Issues · entity",
    note: "Ridgeline 1065: the 470 queue beside the 896 detail, with the instruction composer",
    preset: "issues-entity",
    selected: "rp",
  },
  {
    id: "t9d",
    badge: "T9d",
    name: "Empty detail",
    note: "Nothing selected, so the detail card shows its empty state on the shell colour",
    preset: "issues-individual",
    selected: null,
  },
  {
    id: "t9e",
    badge: "T9e",
    name: "Agent working",
    note: "Fix instructions went out and Accrued Agent is redoing the Colorado factor",
    preset: "issues-entity",
    selected: "co",
    states: { co: "working" },
  },
];

const FIX_MS = 2800;

/** The issue with the board's live state laid over it. */
function live(
  issue: T9Issue,
  state: IssueState | undefined,
  assignee: string | undefined,
  work: string | undefined,
): T9Issue {
  const s = state ?? issue.view.state;
  return {
    kind: issue.kind,
    view: {
      ...issue.view,
      state: s,
      ...(assignee === undefined ? {} : { assignee }),
      status:
        s === "working"
          ? "Agent working"
          : s === "resolved"
            ? "Resolved"
            : s === "na"
              ? "Not applicable"
              : issue.view.status,
      ...(s === "working"
        ? { working: { text: work ?? issue.view.explain ?? "Applying the fix", percent: 46 } }
        : {}),
    },
  };
}

function withStates(
  groups: readonly IssueGroup[],
  states: Readonly<Record<string, IssueState>>,
): readonly IssueGroup[] {
  return groups.map((g) => ({
    ...g,
    items: g.items.map((i) => {
      const st = states[i.id];
      return st === undefined ? i : { ...i, state: st };
    }),
  }));
}

function T9({ board }: { board: Board }): JSX.Element {
  const [sel, setSel] = useState<string | null>(board.selected);
  const [states, setStates] = useState<Readonly<Record<string, IssueState>>>(board.states ?? {});
  const [assignees, setAssignees] = useState<Readonly<Record<string, string>>>({});
  const [work, setWork] = useState<Readonly<Record<string, string>>>(
    board.states?.co === "working" ? { co: CO_EXPLAIN } : {},
  );
  const [explain, setExplain] = useState<Readonly<Record<string, boolean>>>({});
  const [asked, setAsked] = useState<Readonly<Record<string, string>>>({});
  const [showResolved, setShowResolved] = useState(false);
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [store] = useState(() => createMatchStore<CitationPayload>());
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
    },
    [],
  );

  const set = (id: string, st: IssueState): void => {
    setStates((s) => ({ ...s, [id]: st }));
  };
  const source =
    board.preset === "issues-individual"
      ? FELD_ISSUES
      : board.preset === "close-review"
        ? COPPERLEAF_ISSUES
        : null;
  const base: T9Issue | null =
    sel === null ? null : source === null ? ridgelineIssue(sel) : (source[sel] ?? null);
  const issue =
    base === null || sel === null ? null : live(base, states[sel], assignees[sel], work[sel]);
  const short = (title: string): string => title.split(":")[0] ?? title;

  const fix = (text: string): void => {
    if (issue === null) return;
    const id = issue.view.id;
    set(id, "working");
    setWork((w) => ({ ...w, [id]: text }));
    setDraft("");
    timers.current.push(
      setTimeout(() => {
        set(id, "resolved");
        setToast(`Fixed by Accrued Agent · ${short(issue.view.title)}`);
      }, FIX_MS),
    );
  };

  const groups =
    board.preset === "issues-individual"
      ? withStates(FELD_GROUPS, states)
      : board.preset === "close-review"
        ? withStates(COPPERLEAF_GROUPS(showResolved), states)
        : ridgelineGroups(states);
  const variant =
    board.preset === "issues-individual"
      ? "tree"
      : board.preset === "close-review"
        ? "severity"
        : "radio";

  const footer =
    issue === null ? undefined : (
      <IssueFooter
        actor={VIEWER}
        kind={issue.kind}
        state={issue.view.state}
        explainOpen={explain[issue.view.id] === true}
        {...(asked[issue.view.id] === undefined ? {} : { asked: asked[issue.view.id] })}
        onSetFix={() => {
          fix(issue.view.explain ?? "Use the default fix");
        }}
        onExplain={() => {
          setExplain((e) => ({ ...e, [issue.view.id]: e[issue.view.id] !== true }));
        }}
        onResolve={() => {
          set(issue.view.id, "resolved");
          setToast(`Resolved · ${short(issue.view.title)}`);
        }}
        onNotApplicable={() => {
          set(issue.view.id, "na");
          setToast("Marked not applicable");
        }}
        onAsk={() => {
          setAsked((a) => ({ ...a, [issue.view.id]: "Request sent Sep 14" }));
          setToast("Request added to the client portal");
        }}
        onReopen={() => {
          set(issue.view.id, "open");
        }}
      />
    );

  const detail = (
    <IssueDetail
      issue={issue?.view ?? null}
      people={T9_PEOPLE}
      explainOpen={issue !== null && explain[issue.view.id] === true}
      titleBand={board.preset === "close-review" ? "shell" : "card"}
      onAssign={(name) => {
        if (sel === null) return;
        setAssignees((a) => ({ ...a, [sel]: name }));
        setToast(`Assigned to ${name}`);
      }}
      {...(issue === null ? { className: "min-h-full" } : {})}
    />
  );

  const composer =
    board.preset === "issues-entity" &&
    issue !== null &&
    issue.kind !== "review" &&
    issue.view.state === "open" ? (
      <IssueComposer value={draft} onChange={setDraft} onSend={fix} />
    ) : undefined;

  const evidence =
    board.preset === "issues-individual"
      ? [
          <Pane key="viewer" header={false} className="min-h-0 flex-1">
            <div data-queue-pane="viewer" className="flex min-h-0 flex-1 flex-col">
              <SourceViewer
                file={{
                  name: FELD_DOCS.c1099.name,
                  pages: [1, 2].map((n) => ({
                    n,
                    width_pt: 612,
                    height_pt: 792,
                    rotation: 0 as const,
                    src: FORM_PAGE_PNG,
                  })),
                  regions: feldRegions("c1099").map((r) => ({
                    match: r.match,
                    page: 1,
                    rects: [r.bbox],
                  })),
                }}
                menu={VIEWER_MENU}
              />
            </div>
          </Pane>,
          <Pane key="sheet" title="Worksheets" className="min-h-0 flex-1">
            <div
              data-queue-pane="sheet"
              className="flex min-h-0 flex-1 flex-col gap-[16px] overflow-auto pb-[12px]"
            >
              {feldWorksheets(true).map((b) => (
                <FieldBlock key={b.title} title={b.title} meta={b.meta} rows={b.rows} />
              ))}
            </div>
          </Pane>,
        ]
      : board.preset === "close-review"
        ? [
            <Pane
              key="register"
              title="Operating ••4410 · August Register"
              className="min-h-0 flex-1"
            >
              <div data-queue-pane="register" className="min-h-0 flex-1 overflow-auto">
                <DataGrid
                  label="Operating ••4410 · August Register"
                  grammar="ledger"
                  columns={REGISTER_COLUMNS}
                  rows={REGISTER_ROWS}
                  rowMatch={registerMatch}
                />
              </div>
            </Pane>,
          ]
        : [];

  const record =
    board.preset === "close-review" ? (
      <RecordHeader
        variant="close"
        title={COPPERLEAF}
        periods={["2026-06", "2026-07", "2026-08"]}
        tabs={CLOSE_TABS}
        activeTab="Review"
      />
    ) : board.preset === "issues-individual" ? (
      <RecordHeader
        title="2025 Form 1040"
        context={FELD}
        state="In review · Manager"
        sync="synced"
        syncDate="Sep 11"
      />
    ) : (
      <RecordHeader
        title="2025 Form 1065"
        context={RIDGELINE}
        state="In review · Partner"
        sync="synced"
        syncDate="Sep 11"
      />
    );

  const tabs =
    board.preset === "issues-individual" ? (
      <Tabsbar size="compact" label="Return" options={RETURN_TABS} active="Issues" />
    ) : board.preset === "issues-entity" ? (
      <div data-shell="tabsbar" className="flex h-(--tabs-h) flex-none items-center px-[12px]">
        <SegmentedGroup
          size="small"
          label="Partnership return"
          options={ENTITY_TABS}
          active="Issues"
        />
      </div>
    ) : undefined;

  const queue =
    board.preset === "issues-individual"
      ? {
          title: "Issues",
          left: (
            <>
              <SearchField
                label="Search issues"
                placeholder="Search"
                value={query}
                onChange={setQuery}
                className="w-[150px]"
              />
              <IconButton icon="list-filter" label="Filter issues" variant="white" />
            </>
          ),
          right: (
            <>
              <IconButton icon="download" label="Download issues" variant="white" />
              <Button variant="secondary" size="sm" icon="plus" opensDialog>
                Issue…
              </Button>
            </>
          ),
        }
      : board.preset === "close-review"
        ? {
            title: "Issues",
            right: (
              <button
                type="button"
                aria-pressed={showResolved}
                onClick={() => {
                  setShowResolved((s) => !s);
                }}
                className="text-body text-ink-3 hover:text-ink"
              >
                Show resolved
              </button>
            ),
          }
        : { title: "Issues" };

  const q = query.trim().toLowerCase();
  const shown =
    q === ""
      ? groups
      : groups
          .map((g) => ({ ...g, items: g.items.filter((i) => i.title.toLowerCase().includes(q)) }))
          .filter((g) => g.items.length > 0);

  return (
    <Artboard id={board.id} badge={board.badge} name={board.name} note={board.note}>
      <div className="relative">
        <QueueDetailLayout
          embedded
          height={860}
          store={store}
          preset={board.preset}
          toolbar={toolbar(board.preset === "close-review" ? "Closes" : "Tax Returns")}
          record={record}
          {...(tabs === undefined ? {} : { tabs })}
          queue={{
            ...queue,
            body: (
              <IssueQueue
                variant={variant}
                groups={shown}
                selected={sel}
                onSelect={(i) => {
                  setSel(i.id);
                }}
              />
            ),
          }}
          detail={{
            body: detail,
            ...(footer === undefined ? {} : { footer }),
            ...(composer === undefined ? {} : { composer }),
          }}
          evidence={evidence}
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

/** The match the T9a workbook cell lights: 1099-DIV box 1a and worksheet line 3b. */
export const T9A_CELL_MATCH: MatchId = DIV3B_MATCH;

/** One artboard on its own (the tests render a single board). */
export function T9Board({ id }: { id: string }): JSX.Element | null {
  const board = BOARDS.find((b) => b.id === id);
  return board === undefined ? null : <T9 board={board} />;
}

export function T9Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {BOARDS.map((b) => (
        <T9 key={b.id} board={b} />
      ))}
    </div>
  );
}
