# Tier 4 kickoff: E6 and C6 inventory (F-07-T01)

Scan of `main` at the S38 kickoff (5953d3e72, Thu Nov 12, 2026; plan date Mon Apr 3, 2028) for what
the T4 Workbench chat kit consumes from P-09 (S31–S34) and P-10 (S29–S38). "Present" names the
file; "Missing" is built by F-07 inside the named row and logged against its owner epic.

## E6: run and session components

| Piece | Owner | Where | Status | F-07 action |
|---|---|---|---|---|
| `RunStore` | P-09 | `apps/web/src/domain/agents/runSource.ts` | present | consumed by `ChatThread` (F-07-T03) through a prop, never imported by the kit |
| `ScriptedRunSource` | P-09 | `apps/web/src/domain/agents/runSource.ts` | present | TPL-04 fixtures script it (F-07-T04) |
| `PollingRunSource` | P-09 | `apps/web/src/domain/agents/runSource.ts` | present | none |
| `SseRunSource` | P-10 | `apps/web/src/domain/agents/sseRunSource.ts` | present | none (W-02 binds it) |
| `AgentBlocks`, `AgentProse` | P-09 | `packages/ui/src/agent/blocks.tsx` | present | every agent string in the thread renders through them (F-07-T03) |
| `AgentCard` | P-09 | `packages/ui/src/agent/agent-card.tsx` | present | T4f agent detail header reuses it |
| `AgentText` | F-05 | `packages/ui/src/agent-text.tsx` | present | reused unchanged |
| `formatActor` | F-05 | `packages/ui/src/attribution/actor.ts` | present | every SessionList meta line (F-07-T02) |
| `TraceDrawer` (WB-09) | P-09 | `apps/web/src/domain/agents/TraceDrawer.tsx` | present (app layer) | the header's Bug emits `onOpenTrace`; the host opens the drawer |
| `ToolCard` | P-09 | — | **missing** in `packages/ui` (the AUD-02 dock draws its rows in `domain/agents/RunPane.tsx`) | F-07-T03 adds a presentational `ToolCardRow` (agent_run_step words) and logs the gap against P-09 |
| `RunCard`, `ProgressCard` | P-09 | — | **missing** in `packages/ui` (`ReturnProgressCard` is T-05's) | F-07-T03 renders `run_card` items through a consumer slot; no kit card |
| `ApprovalCard` (SHL-10) | P-04 | `packages/ui/src/gates/approval-card.tsx` | present | rendered only through the `approval` slot |
| `DecisionCard` (SHL-11) | P-04 | `packages/ui/src/gates/decision-card.tsx` | present | rendered only through the `decision_ref` slot |
| `EmptyState`, view states | F-05 | `packages/ui/src/components/states.tsx` | present | `restricted`, `flag-off`, filtered-empty |
| `Segmented` | F-05 | `packages/ui/src/components/tabs.tsx` | present | the tabsbar's Sessions · Agents · Connect |

## C6 v2: the session contract the kit renders

| Contract item | Source | Kit mapping |
|---|---|---|
| `SessionItemOut.kind` ∈ `user_message`, `agent_blocks`, `plan`, `question`, `answer`, `tool_card`, `artifact`, `notice` | `workbench/sessions_contract.py`; migration 0682 | the `ChatThread` renderer registry keys (F-07-T03); `plan` renders the consumer slot |
| `SessionSnapshotOut.locked`, `allowed_actions` | P-10-T43 (DEC-4301) | `locked: true` draws the `restricted` view state with no items (AC A1, INV-3) |
| `RunEventOut` (`item.appended`, `question.opened`, `locked`, `resync`, …) | `docs/contracts/agent-runs.md` §9 | the store's events; the kit re-renders from the store, never from the event |
| `POST …/messages {body, answers_seq?}` | P-10-T43 | `Composer` and `QuestionCard` emit `onSend` and `onAnswer`; the host posts |
| Status words `workbench_session`, `agent_run_step`, `agent_question` | C2 (`status-vocabulary.yaml`) | present: session dots, tool card states and the question chip read them |

## Status words (C2)

Present: `workbench_session` (live, running, awaiting_answer, ready_for_review, complete, failed),
`agent_run_step`, `agent_question`, `k1_package` (Draft K-1 · pre-release, Released {date}).
F-07-T25 (DEC-4507) added the `filing_deadline` object to C2 (overdue "Past due", due_7, due_30,
later, done, postponed "Postponed → {date}", extended "Extended to {date}"; all derived) and
removed the kit-local draft type; nothing tier 4 needs is missing from C2 now.

## Decisions confirmed at the S38 Contract Monday

DEC-04, DEC-11, DEC-14, DEC-15, DEC-16, DEC-23, DEC-30, DEC-32, DEC-40, DEC-41, DEC-43, DEC-44,
DEC-49, DEC-52, DEC-62, DEC-76, DEC-78, DF-02 and DF-10 are recorded as decided in
`docs/product/decision-log.md`; ADR P-03, P-12, P-15, P-18, P-19, P-23, P-24, P-46, P-47 and P-62 are
recorded in `docs/adr/`. Conflicts between the handoff and C6 are in
`packages/ui/src/tokens/DECISIONS.md` (Tier-4 kickoff).
