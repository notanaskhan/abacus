import { type JSX, useEffect, useRef, useState } from "react";
import { cn } from "../cn";
import { Amount } from "../components/amount";
import { Button, IconButton } from "../components/button";
import { Picker, SearchField, ValueRow } from "../components/inputs";
import { EmptyState } from "../components/states";
import { TallyPill } from "../components/status";
import { Segmented, SegmentedGroup, SheetTabs } from "../components/tabs";
import { Toast } from "../components/toast";
import { FieldBlock } from "../data/fields";
import { Icon } from "../icons";
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
import { useMatch } from "../tracing/match";
import { createMatchStore } from "../tracing/match-store";
import type { CitationPayload } from "../tracing/types";
import { SourceViewer } from "../viewer/source-viewer";
import guards from "../../scope-guards.gen.json";
import { Artboard } from "./portal";
import { COPPERLEAF, FELD, FIRM, RIDGELINE, STAFF } from "./seed-figures";
import { K1_FILE, K1_VIEW } from "./tpl03";
import {
  BANK_REC,
  FELD_ISSUES,
  K1_SUPPORT,
  K18_MATCH,
  REFUND_MATCH,
  type RecLine,
  TPL09_PEOPLE,
  type Tpl09Issue,
  closeGroups,
  closeIssue,
  feldGroups,
  feldSheet,
  ridgelineGroups,
  ridgelineIssue,
} from "./tpl09-data";

// TPL-09 (F-05-T57; TPL-09 handoff, Wave 0 Templates #tpl09): T9 in its three presets on the
// seed's own issue lists, TPL-09a to TPL-09g. The Feld 1040 issues for Kevin Osei (546 well, viewer
// 433, sheets 377), the Copperleaf August close review for Priya Raman (790 split beside the ••4410
// reconciliation, which shows `tie`, not Reconciled, while #2281 and the refund are open) and the
// Ridgeline 1065 issues for Samuel Ito (470 queue, 896 detail). Every board is live: pick issues,
// collapse bands, Explain, set fix instructions, resolve with a note, Accept or Reject the proposed
// value, and Reopen. The verbs are a person's; the agent can be the assignee and is never offered
// Resolve or Accept.

type Frame = "A" | "B" | "C";

const PRESET: Record<Frame, QueuePreset> = {
  A: "issues-individual",
  B: "close-review",
  C: "issues-entity",
};

/** The person each frame is seen as. */
const VIEWERS: Record<Frame, string> = { A: STAFF.kevin, B: STAFF.priya, C: STAFF.samuel };

interface Board {
  id: string;
  badge: string;
  name: string;
  note: string;
  frame: Frame;
  selected: string | null;
  working?: boolean;
  resolved?: Readonly<Record<string, IssueState>>;
  empty?: boolean;
}

// The canvas's META, word for word.
const BOARDS: readonly Board[] = [
  {
    id: "tpl-09a",
    badge: "TPL-09a",
    name: "Issues · individual",
    note: "Kevin Osei on the Feld 1040; box 18A is missing from the worksheet",
    frame: "A",
    selected: "k18",
  },
  {
    id: "tpl-09b",
    badge: "TPL-09b",
    name: "Close review",
    note: "Priya Raman on the Copperleaf August close; check #2281 is stale",
    frame: "B",
    selected: "ck",
  },
  {
    id: "tpl-09c",
    badge: "TPL-09c",
    name: "Issues · entity",
    note: "Samuel Ito on the Ridgeline 1065; M-2 is off 6,200",
    frame: "C",
    selected: "tei",
  },
  {
    id: "tpl-09d",
    badge: "TPL-09d",
    name: "Agent fixing",
    note: "Fix instructions sent: Accrued Agent adds 1,550 to line 2a",
    frame: "A",
    selected: "k18",
    working: true,
  },
  {
    id: "tpl-09e",
    badge: "TPL-09e",
    name: "Waiting on client",
    note: "The estimated payments issue asks the client",
    frame: "A",
    selected: "est",
  },
  {
    id: "tpl-09f",
    badge: "TPL-09f",
    name: "Resolved",
    note: "The M-2 issue is resolved; Reopen in the footer",
    frame: "C",
    selected: "tei",
    resolved: { tei: "resolved" },
  },
  {
    id: "tpl-09g",
    badge: "TPL-09g",
    name: "Empty queue",
    note: "No open issues on the close",
    frame: "B",
    selected: null,
    empty: true,
  },
];

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
const ENTITY_TABS = [
  "Agent",
  { label: "Issues", count: 11, bad: true },
  "Workpaper",
  "Review",
  "Intake",
  "Activity",
];
const closeTabs = (empty: boolean) => [
  "Overview",
  "Intake",
  "Accounts",
  empty ? "Review" : { label: "Review", count: 7, bad: true },
  "Deliverables",
];

const VIEWER_MENU = [
  { label: "Download", onSelect: () => undefined },
  { label: "Open in Files", onSelect: () => undefined },
];

const FIX_MS = 2400;
const DONE: readonly IssueState[] = ["resolved", "na"];

function issueOf(frame: Frame, id: string | null): Tpl09Issue | null {
  if (id === null) return null;
  if (frame === "A") return FELD_ISSUES[id] ?? null;
  return frame === "B" ? closeIssue(id) : ridgelineIssue(id);
}

/** The issue with the board's live state over it: status, the run row. */
function live(issue: Tpl09Issue, state: IssueState): Tpl09Issue {
  const status = state === "resolved" ? "Resolved" : state === "na" ? "Not applicable" : "Open";
  return {
    ...issue,
    view: {
      ...issue.view,
      state,
      status,
      ...(issue.view.facts === undefined
        ? {}
        : {
            facts: issue.view.facts.map((f) =>
              f.label === "Status" ? { ...f, value: status } : f,
            ),
          }),
      ...(state === "working"
        ? { working: { text: issue.run ?? "Working on this issue", percent: 46 } }
        : {}),
    },
  };
}

/** One line of the ••4410 reconciliation; the refund row lights with its statement chip. */
function RecRow({ line, stale }: { line: RecLine; stale: boolean }): JSX.Element {
  const { lit, bind } = useMatch(REFUND_MATCH, "row");
  const chipLit = line.chip !== undefined && lit;
  if (line.kind === "group") {
    return (
      <tr data-rec-row={line.id}>
        <th
          colSpan={3}
          scope="colgroup"
          className="h-[26px] px-[14px] text-left text-pill-sm font-normal text-ink-3 hairline-t"
        >
          {line.label}
        </th>
      </tr>
    );
  }
  const strong = line.kind === "total" || line.kind === "band";
  return (
    <tr
      data-rec-row={line.id}
      className={cn(
        "h-[30px] text-cell hairline-t transition-[background-color] duration-[360ms]",
        line.kind === "band" && "bg-band-hd",
        stale && "bg-sel-bg",
        chipLit && "bg-match-bg",
      )}
    >
      <th
        scope="row"
        className={cn(
          "text-left",
          line.kind === "check" ? "pl-[26px]" : "pl-[14px]",
          strong ? "font-medium" : "font-normal",
        )}
      >
        <span className="inline-flex items-center gap-[8px]">
          {line.flag === true && (
            <Icon name="flag" size={12} aria-label="Flagged" className="text-red" />
          )}
          {line.label}
        </span>
      </th>
      <td className="w-[110px] text-right">
        {line.chip !== undefined && (
          <span
            {...bind}
            data-rec-chip=""
            className={cn(
              "inline-flex h-[20px] items-center rounded-pill px-[8px] text-pill-sm",
              "transition-[background-color,color] duration-[360ms]",
              chipLit ? "bg-match-bg-2 text-match-ink" : "bg-nested text-ink-3",
            )}
          >
            {line.chip}
          </span>
        )}
        {line.tie === true && (
          <span data-rec-tally="">
            <TallyPill code="tie" />
          </span>
        )}
      </td>
      <td className={cn("pr-[14px] text-right", strong && "font-medium")}>
        <Amount value={line.amount ?? ""} style="money" zero="explicit" />
      </td>
    </tr>
  );
}

function Tpl09({ board }: { board: Board }): JSX.Element {
  const { frame } = board;
  const empty = board.empty === true;
  const [sel, setSel] = useState<string | null>(board.selected);
  const [states, setStates] = useState<Readonly<Record<string, IssueState>>>(() => ({
    ...(board.resolved ?? {}),
    ...(board.working === true && board.selected !== null ? { [board.selected]: "working" } : {}),
  }));
  const [assignees, setAssignees] = useState<Readonly<Record<string, string>>>({});
  const [explain, setExplain] = useState<Readonly<Record<string, boolean>>>({});
  const [asked, setAsked] = useState<Readonly<Record<string, boolean>>>({});
  const [ghost, setGhost] = useState<"proposed" | "accepted" | "rejected">("proposed");
  const [noting, setNoting] = useState(false);
  const [note, setNote] = useState("");
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
  const base = empty ? null : issueOf(frame, sel);
  const state: IssueState = sel === null ? "open" : (states[sel] ?? "open");
  const issue = base === null ? null : live(base, state);
  const view =
    issue === null || sel === null
      ? null
      : { ...issue.view, assignee: assignees[sel] ?? issue.view.assignee };
  const done = DONE.includes(state);

  const fix = (): void => {
    if (sel === null) return;
    const id = sel;
    set(id, "working");
    setDraft("");
    timers.current.push(
      setTimeout(() => {
        set(id, "resolved");
        if (frame === "A" && id === "k18") setGhost("accepted");
      }, FIX_MS),
    );
  };
  const resolve = (): void => {
    if (sel === null || note.trim() === "") return;
    set(sel, "resolved");
    setNoting(false);
    setNote("");
  };
  const pick = (id: string): void => {
    setSel(id);
    setNoting(false);
  };

  const groups: readonly IssueGroup[] = empty
    ? []
    : frame === "A"
      ? feldGroups(states)
      : frame === "B"
        ? closeGroups(states, showResolved)
        : ridgelineGroups(states);
  const q = query.trim().toLowerCase();
  const shown =
    q === ""
      ? groups
      : groups
          .map((g) => ({ ...g, items: g.items.filter((i) => i.title.toLowerCase().includes(q)) }))
          .filter((g) => g.items.length > 0);

  const person = { kind: "human", name: VIEWERS[frame] } as const;

  const noteForm = (
    <div data-issue-note="" className="flex flex-col gap-[8px]">
      <div className="rounded-nested bg-card shadow-e1">
        <ValueRow
          kind="paragraph"
          label="Resolution note"
          value={note}
          onChange={setNote}
          placeholder="Add a resolution note"
          rows={2}
        />
      </div>
      <span className="flex gap-[8px]">
        <Button
          variant="secondary"
          size="footer"
          className="flex-1"
          onClick={() => {
            setNoting(false);
          }}
        >
          Cancel
        </Button>
        <Button
          variant="primary"
          size="footer"
          icon="check"
          data-human-only=""
          disabled={note.trim() === ""}
          className="flex-1"
          onClick={resolve}
        >
          Resolve
        </Button>
      </span>
    </div>
  );

  const footer =
    issue === null || sel === null ? undefined : noting ? (
      noteForm
    ) : frame === "C" && !done ? undefined : (
      <IssueFooter
        actor={person}
        kind={issue.kind}
        state={state}
        explainOpen={explain[sel] === true}
        {...(asked[sel] === true ? { asked: "Request sent" } : {})}
        onSetFix={fix}
        onExplain={() => {
          setExplain((e) => ({ ...e, [sel]: e[sel] !== true }));
        }}
        onResolve={() => {
          setNoting(true);
          setNote("");
        }}
        onNotApplicable={() => {
          set(sel, "na");
        }}
        onAsk={() => {
          setAsked((a) => ({ ...a, [sel]: true }));
          setToast("Request sent to the Feld portal · estimated payment confirmations");
        }}
        onReopen={() => {
          set(sel, "open");
        }}
      />
    );

  const detailBody =
    view === null ? (
      empty ? (
        <div data-issue-detail="blank" className="min-h-full bg-shell" />
      ) : (
        <IssueDetail issue={null} className="min-h-full" />
      )
    ) : (
      <IssueDetail
        issue={view}
        people={TPL09_PEOPLE}
        explainOpen={explain[view.id] === true}
        titleBand={frame === "B" ? "shell" : "card"}
        onAssign={(name) => {
          setAssignees((a) => ({ ...a, [view.id]: name }));
          setToast(`Assigned to ${name}`);
        }}
      />
    );

  const composer =
    frame === "C" && issue !== null && state === "open" && !noting ? (
      <IssueComposer value={draft} onChange={setDraft} onSend={fix} />
    ) : undefined;
  const headerResolve =
    frame === "C" && issue !== null && !done && !noting ? (
      <Button
        variant="primary"
        size="sm"
        data-human-only=""
        onClick={() => {
          setNoting(true);
          setNote("");
        }}
      >
        Resolve
      </Button>
    ) : undefined;

  const evidence =
    frame === "A"
      ? [
          <Pane key="viewer" header={false} className="min-h-0 flex-1">
            <div data-queue-pane="viewer" className="flex min-h-0 flex-1 flex-col">
              <SourceViewer file={K1_VIEW} menu={VIEWER_MENU} />
              <section
                data-k1-support=""
                aria-label="Schedule K-1 (Form 1065) — Supporting Schedules"
                className="flex-none p-[10px]"
              >
                <h3 className="bg-espresso px-[10px] py-[7px] text-meta font-medium text-on-dark">
                  Schedule K-1 (Form 1065) — Supporting Schedules
                </h3>
                <dl className="bg-card px-[10px] pt-[6px] pb-[8px] shadow-e1">
                  {K1_SUPPORT.map(([k, v]) => (
                    <div key={k} className="flex gap-[10px] py-[2px] text-meta">
                      <dt className="w-[84px] flex-none text-ink-3">{k}</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            </div>
          </Pane>,
          <Pane
            key="sheet"
            left={
              <SheetTabs
                label="Workpaper view"
                options={[
                  { label: "Worksheets", icon: "panels-top-left" },
                  { label: "Leadsheets", icon: "layers" },
                ]}
                active="Worksheets"
              />
            }
            className="min-h-0 flex-1"
          >
            <div
              data-queue-pane="sheet"
              className="flex min-h-0 flex-1 flex-col gap-[16px] overflow-auto pb-[12px]"
            >
              <div className="flex items-center gap-[8px] px-[12px] pt-[4px]">
                <SearchField label="Search worksheets" placeholder="Search" className="flex-1" />
                <Picker
                  label="Worksheet"
                  options={[{ value: "ridgeline", label: "RIDGELINE PROPERTY …" }]}
                  defaultValue="ridgeline"
                  className="w-[150px]"
                />
                <Button variant="secondary" size="sm" icon="pencil">
                  Edit
                </Button>
              </div>
              {feldSheet(ghost).map((b) => (
                <FieldBlock
                  key={b.title}
                  title={b.title}
                  rows={b.rows}
                  onAccept={() => {
                    setGhost("accepted");
                    setToast("Checkpoint created · 1,550 added to Form 1040 line 2a");
                  }}
                  onReject={() => {
                    setGhost("rejected");
                    setToast("Proposed value rejected");
                  }}
                />
              ))}
            </div>
          </Pane>,
        ]
      : frame === "B"
        ? [
            <Pane
              key="register"
              title="Operating Checking (Front Range Bank) ••4410"
              className="min-h-0 flex-1"
            >
              <div data-queue-pane="register" className="min-h-0 flex-1 overflow-auto">
                <div className="flex h-[44px] items-center px-[12px]">
                  <Segmented
                    size="small"
                    label="Account view"
                    options={["Detail", "Reconciliation"]}
                    active="Reconciliation"
                  />
                </div>
                <table data-bank-rec="" className="w-full border-collapse tabular-nums">
                  <caption className="sr-only">
                    Operating Checking (Front Range Bank) ••4410 reconciliation
                  </caption>
                  <tbody>
                    {BANK_REC.map((line) => (
                      <RecRow
                        key={line.id}
                        line={line}
                        stale={line.flag === true && sel === "ck" && !empty}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </Pane>,
          ]
        : [];

  const record =
    frame === "B" ? (
      <RecordHeader
        variant="close"
        title={COPPERLEAF}
        periods={["2026-06", "2026-07", "2026-08"]}
        tabs={closeTabs(empty)}
        activeTab="Review"
      />
    ) : frame === "A" ? (
      <RecordHeader
        title="2025 Form 1040"
        context={FELD}
        state="In review · Manager"
        sync="synced"
        syncDate="Sep 10"
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
    frame === "A" ? (
      <Tabsbar size="compact" label="Return" options={RETURN_TABS} active="Issues" />
    ) : frame === "C" ? (
      <div data-shell="tabsbar" className="flex h-(--tabs-h) flex-none items-center px-[12px]">
        <SegmentedGroup
          size="small"
          label="Partnership return"
          options={ENTITY_TABS}
          active="Issues"
        />
      </div>
    ) : undefined;

  const queueHead =
    frame === "A"
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
      : frame === "B"
        ? {
            title: "Issues",
            right: (
              <button
                type="button"
                aria-pressed={showResolved}
                onClick={() => {
                  setShowResolved((s) => !s);
                }}
                className={cn(
                  "text-body hover:text-ink",
                  showResolved ? "text-ink" : "text-ink-3",
                )}
              >
                Show resolved
              </button>
            ),
          }
        : { title: "Issues" };

  const queueBody = empty ? (
    <EmptyState title="No open issues." icon="check" className="min-h-full">
      Issues raised by the agent or reviewers appear here.
    </EmptyState>
  ) : (
    <>
      {frame === "A" && (
        <header
          data-queue-head=""
          className="flex items-center gap-[8px] px-[12px] pt-[12px] pb-[10px] hairline-b"
        >
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="text-tab font-medium">Open Issues</span>
            <span className="text-meta text-ink-3">Instructions Required</span>
          </span>
          <Button variant="secondary" size="sm" icon="plus" opensDialog>
            Instructions…
          </Button>
        </header>
      )}
      <IssueQueue
        variant={frame === "A" ? "tree" : frame === "B" ? "severity" : "radio"}
        groups={shown}
        selected={sel}
        onSelect={(i) => {
          pick(i.id);
        }}
      />
    </>
  );

  return (
    <Artboard id={board.id} badge={board.badge} name={board.name} note={board.note}>
      <div className="relative" data-tpl09-frame={frame}>
        <QueueDetailLayout
          embedded
          height={860}
          store={store}
          preset={PRESET[frame]}
          toolbar={toolbar(frame === "B" ? "Closes" : "Tax Returns")}
          record={record}
          {...(tabs === undefined ? {} : { tabs })}
          queue={{ ...queueHead, body: queueBody }}
          detail={{
            body: detailBody,
            ...(headerResolve === undefined ? {} : { right: headerResolve }),
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

/** The match the K-1 box 18A chip, page region and worksheet line 2a share (TPL-09a). */
export const TPL09A_MATCH = K18_MATCH;
export { K1_FILE as TPL09_K1_FILE };

/** One artboard on its own (the tests render a single board). */
export function Tpl09Board({ id }: { id: string }): JSX.Element | null {
  const board = BOARDS.find((b) => b.id === id);
  return board === undefined ? null : <Tpl09 board={board} />;
}

export function Tpl09Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {BOARDS.map((b) => (
        <Tpl09 key={b.id} board={b} />
      ))}
    </div>
  );
}
