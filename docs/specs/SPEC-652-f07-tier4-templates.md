---
id: SPEC-652
title: "F-07 tier 4: template props as contracts (addendum)"
status: approved
owner: ayushkbhatia
risk_zone: amber
created: 2026-11-12
updated: 2026-11-12
---

# SPEC-652 · F-07 tier 4: template props as contracts (addendum)

| Field | Value |
|---|---|
| Epic | F-07 (S38–S43) |
| Status | addendum (F-07-T01, Thu Nov 12, 2026; plan date Mon Apr 3, 2028) |
| Binds | F-07-T02 (T4 frame, SessionList, ChatHeader), F-07-T03 (ChatThread), F-07-T04 (TPL-04 fixtures), F-07-T05 (independent AC), and the T13, T14, T17 rows |
| Contracts | C6 v2 (sessions and run events), C2 (status words), C4 (citations) |

Templates take data through props and emit intents; they never fetch (F-07 §1). The props below are
the contract a consumer (W-02, T-06, T-08, W-03) binds to; changing a prop's name or meaning is a
contract change recorded in `packages/ui/src/tokens/DECISIONS.md`.

## AC-1. `WorkbenchLayout` (T4a–f)

```ts
type WorkbenchTab = "sessions" | "agents" | "connect";
interface WorkbenchLayoutProps {
  tab: WorkbenchTab;                 // the tabsbar's Segmented (60 h, −10 bottom margin)
  list: ReactNode;                   // 358 wide at x12 (320 in the T4f variant)
  chat: ReactNode;                   // flex (1008 at 1440 × 900), panes y106–848, 742 tall
  variant?: "chat" | "agent_detail"; // T4f: list 320 + detail
  viewState?: "ready" | "restricted" | "flag-off";
  onTab?: (tab: WorkbenchTab) => void;
}
```

## AC-2. `SessionList` and its rows (T4a–e, WB-01f, WB-01g)

```ts
interface SessionRow {
  id: string;
  title: string;
  owner: Actor;                      // formatActor: "Hannah Leclerc" or "Hannah Leclerc via Agent"
  last_at: string;                   // ISO; shown as "9:21 AM"
  state: WorkbenchSessionStatus;     // C2 workbench_session
  needs_answer: boolean;             // the 8 px amber dot, accessible name "Awaiting your answer"
  running: boolean;                  // the 12 px spinner
  locked: boolean;                   // restricted: selecting it shows no item or figure (INV-3)
}
interface SessionListProps {
  rows: readonly SessionRow[];
  selectedId?: string;
  query?: string;                    // filtered-empty with Clear search when nothing matches
  onSelect?: (id: string) => void;
  onQuery?: (q: string) => void;
}
```
Rows are 48 h; the meta line is produced only by `formatActor`; no line reads "Accrued Agent" as an
owner (INV-5).

## AC-3. `ChatHeader`

```ts
interface ChatHeaderProps {
  title: string;
  owner: Actor;
  live: boolean;                     // the 8 px olive LiveDot
  context?: readonly ContextRef[];   // the Paperclip ⌄ chip
  locked?: boolean;                  // actions disabled
  onOpenTrace?: () => void;          // Bug → WB-09 (the host's TraceDrawer)
  onRename?: () => void;             // Pencil
  onDelete?: () => void;             // Trash2
  onCreateAgent?: () => void;        // "Create Agent…" (WB-07, W-03)
}
```

## AC-4. `ChatThread` (F-07-T03)

The renderer registry is keyed by C6's `SessionItemOut.kind`. Consumer slots are registered by the
host; with none registered the neutral row renders and the raw payload never does.

| C6 kind | Renders |
|---|---|
| `user_message` | Bubble `me` |
| `agent_blocks` | `AgentBlocks` (p, table, kv, metric, file parts); 20 ms per word client-side reveal; `?static=1` or reduced motion shows the text at once |
| `question` | `QuestionCard` above the composer (F-07-T06, S39) |
| `answer` | Bubble `me` with the chosen option's title |
| `tool_card` | `ToolCardRow` (C2 `agent_run_step`); a failed step is `ChatErrorRow` with Retry and View run |
| `artifact` | `FileArtifactRow` (Open · Download · Save to Files intents) |
| `notice` | `NoticeRow`: the server's fixed words, no action |
| `plan` | the consumer's `plan` slot (W-02) |
| slot kinds `approval`, `decision_ref`, `run_card` | the consumer's slots (P-04's ApprovalCard and DecisionCard, P-09's RunCard) |

```ts
interface ChatThreadProps {
  items: readonly SessionItem[];     // from RunStore, oldest first
  locked?: boolean;                  // restricted: no item renders
  slots?: Partial<Record<"plan" | "approval" | "decision_ref" | "run_card", (item: SessionItem) => ReactNode>>;
  onRetryStep?: (stepId: string) => void;
  onOpenRun?: (runId: string) => void;
  onArtifact?: (id: string, intent: "open" | "download" | "save") => void;
  onSend?: (body: string) => void;   // Composer: Enter sends, Shift+Enter breaks a line
}
```
The kit never renders Approve, Reject, Decide, Sign off, Release or Send (INV-1).

## AC-5. `QuestionCard` (F-07-T06, S39)

`{question_id, steps:[{q, options:[{key, title, detail}], other, preselect}], skipText, skipDefault,
n, m}`; emits exactly one `onAnswer({question_id, step, key})` per choice, `{skipped: true}` only
on an explicit Skip (never on timeout, blur or navigation); Esc returns focus to the Composer.

## AC-6. T13, T14, T17 (S40–S43)

Recorded here for the consumer epics and refined by their rows: `CalendarLayout {view: "month" |
"week" | "list", month, today, chips:[{id, date, label, tier: RegistryCode<"filing_deadline">, rule}],
onFilter, onExpandDay}`; `GraphCanvasLayout {nodes:[{id, kind, label, x, y, external, masked_tin}],
edges:[{from, to, label, solid}], selectedId, view: "graph" | "list", onSelect, onMove}`;
`FormRendererLayout {pages:[{n, image_url}], selectedPage, schedules:[{key, label, diagnostics}],
traces, onGoTo}`. Dates, tiers, layouts' saved positions and form images are the server's.
