---
id: SPEC-653
title: W-02 Workbench sessions (WB-01, WB-02, WB-03) and the workbench.assistant capability
status: draft
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-235, ADR-233, ADR-234, ADR-230, ADR-169, ADR-161, ADR-232, ADR-186, ADR-063, ADR-005, ADR-026, ADR-050, ADR-090, ADR-241]
related_specs: [SPEC-647, SPEC-652]
created: 2026-11-12
updated: 2026-11-12
epic: W-02
task: W-02-T01 (TASK-7601)
---

# SPEC-653 · Workbench sessions

> **Instructions for coding agents**
> - The design is `docs/plan/epics/W-02.md` §1 to §8; rows are `docs/plan/epics/W-02.tasks.csv`.
>   The acceptance criteria are the epic's §3, adopted verbatim as the spec of record under their
>   epic IDs (AC-L1 … AC-D3); this file lists them, settles the open questions and records what
>   the upstream epics shipped. Where the epic's text and this file differ, this file wins.
> - Contract: `docs/contracts/workbench-sessions.md` (W-02-T02), additive to C6 v2
>   (`docs/contracts/agent-runs.md` §9). Screen contracts: `docs/screens/WB-01.md`, `WB-02.md`,
>   `WB-03.md` (W-02-T08).
> - Chapter 05 §5.2.4 (sessions and chat), §5.2.5 (runs), §5.3.7 (orchestration on Temporal) and
>   §5.4.6 (authority, walls and need-to-know) are the sources; chapter 01 gives the dates.

## Scope
- Three P0 screens, 22 artboards: WB-01 a–g (7), WB-02 a–f (6), WB-03 a, a2, b, c, d, d2, e, f, g
  (9); plus the two DF-04 states, the `workbench.enabled` flag-off state and the loading and error
  view states on each screen. WB-01 h, i and WB-02 g, h (R2 saved prompts) are W-03's.
- Modules: `workbench` (amber: list, CRUD, visibility, context options and items, events, C15
  registration), `agents` (red: `workbench.assistant` spec, session workflow v2, plan fields, the
  per-item failure ledger, run-artifact preview, download and drill), `ai_gateway` (red: prompts
  only), and tool owners `tax`, `requests`, `workpapers`, `assurance` (amber), `identity` and
  `evidence` (red).
- Out of scope: W-02 §2.3 (saved prompts, Create Agent…, live schedules, WB-04 to WB-12, drafting
  tools, live Box and CCH connectors, real-data clearance, MCP).

## Decisions and ADRs (the acceptance check)
The epic names chapter 09's P-IDs and the plan's reserved numbers; the repository numbers differ.

| Epic ID | Repository ADR | Status on main | What W-02 relies on |
|---|---|---|---|
| P-23 (AG-04), "ADR-159" | ADR-235 Workbench sessions (amends ADR-063 and `build-plan.md` §10) | proposed | sessions are a conversation over typed tool plans; every write planned and approved |
| P-22 (AG-01), "ADR-157" | ADR-233 Agent capabilities and definitions | proposed | capability specs in code; one agent principal |
| P-46 (AG-02), "ADR-158" | ADR-234 Gateway conversations and tool use | proposed | `converse()` with tools; no token streaming |
| P-24 (AG-05), "ADR-160" | ADR-230 Structured agent output | accepted | closed `AgentBlocks`, numbers by reference |
| P-47 (AG-03), "ADR-147" | ADR-169 Canonical run states, durable run records | accepted | runs, steps, 14 states |
| P-35 (AG-08), "ADR-126" | ADR-161 Suggestions, proposals, approval grants, Undo | accepted | single-use grants, `not_before` +10 s, Undo |
| P-15 (AG-06), "ADR-156" | ADR-232 Real time via SSE | proposed | SSE, polling fallback, no WebSockets |
| P-49, "ADR-148" | ADR-186 Autonomy policy versions, Auto mode | accepted | Auto mode never applies to sessions |
| DEC-87, DEC-43, DEC-33, DEC-52 | decision log; C19 (`c19-consent-gate.md`) | decided | list membership, walls, scope kinds, §7216 |

ADR-232 to ADR-235 stay **proposed**: their acceptance is Ayush's (DEC-3016). W-02 builds on them as
proposed, as P-10 and T-04 did. ADR-235's amendment of ADR-063 and of `build-plan.md`'s Phase 5
placement is in ADR-235 itself ("Negative": amends `build-plan.md`), so no separate amendment is
needed before the stub.

## Settled questions (DEC-4601)
- **Q1 list membership.** "All" = sessions I own or initiated, plus sessions whose owner shares a
  team or an office with me, plus sessions on work items whose team I am on; walled rows are
  omitted with no count; non-walled rows I can't open are listed with metadata and lock on open
  (chapter 05 §5.4.6). "Mine" = owned or initiated by me. "Via Agent" = origin is not `manual`.
- **Q2 aggregate tax counts.** Counts and stage matrices by status, office and stage, with names
  only by entity reference resolved at render time, are outside the §7216 AI-disclosure consent.
  Per-return content stays `tri` and outside the assistant. Counsel's confirmation is a real-firm
  gate (no live firm, DEC-1391); until it lands `tax.season_counts` stays on synthetic tenants,
  which is where W-02 runs (`client_data: none`).
- **Q3 ApprovalCard Edit….** File name and target folder (folders the approver can write), as a
  new proposal version; never the workbook's content.
- **Q6 retention of session-only artifacts.** Same record type as run artifacts: the longer of 7
  years and the engagement's retention; firm-level sessions use the firm-records floor.
- **Q7 stage groups.** Gather · Prepare · Review · Deliver live in the status registry as context
  labels over return statuses (W-02-T04), never firm content.

## Inventory of what upstream shipped (2026-11-12, main 09639107a)
- **P-10:** sessions core (`workbench/sessions.py`, `session_queue.py`, `session_workflow.py`,
  `session_activities.py`; tables 0682), the snapshot with `locked`, message post with the side
  queue, the `session:<id>` topic (TASK-7325), the badge stream behind `realtime.sse`
  (`/v1/me/agent-events`), run commands, the capability endpoint (`runs_v2_contract.py`,
  `capability_availability.py`), the `files.*` tools (`files.build_workbook`, `files.propose_save`,
  `files.save_approved`), eval infrastructure and the runtime scenario. **No P-10 cut item is
  absorbed**: the badge stream and the side queue both shipped.
- **F-07:** the T4 kit `packages/ui/src/agent/chat` (`SessionList`, `ChatHeader`, `ChatThread`,
  `QuestionCard`, `ContextPicker`, `EmptySession`, `AgentDetail`); TPL-04 locked at Tier B
  (F-07-T09, DEC-4511).
- **P-09:** `AgentBlocks`, the RunCard and the E6 run store; WB-09 trace.
- **P-04:** `packages/ui/src/gates/approval-card.tsx`, proposals, grants, Undo.
- **N-01 (finding):** Files folders are per work item (`folder:<work item>:<kind>`) or per client
  (`permanent:<client>[:<kind>]`); there is **no firm-level folder**, so "Files › Firm reports ›
  TY2025 season" has no home yet. Per W-02 §11 R5, W-02-T23 either adds a firm-level folder kind
  through N-01's API or ships "Attach it to this session only" alone; the T02 fixtures carry the
  designed copy either way.
- Not yet built (W-02's own rows): the six tools, the capability spec and prompt, the list and
  CRUD routes, context options and items, the drill, run-artifact preview and download.

## Endpoints (W-02 §4.3, all `AbacusRouter`, one action each, P-36 list envelope)
| Method · path | Action | Row |
|---|---|---|
| `GET /v1/workbench/sessions?filter=all\|mine\|via_agent\|running\|needs_answer&q=&cursor=` | `session.read` | stub T02, live T09 |
| `POST /v1/workbench/sessions` (blank, `firm_wide`) | `session.create` | T02, T09 |
| `PATCH /v1/workbench/sessions/{id}` `{title}` (`If-Match`) | `session.manage` | T02, T09 |
| `DELETE /v1/workbench/sessions/{id}` (soft) | `session.manage` | T02, T09 |
| `GET /v1/workbench/context-options?tab=client_record\|documents\|workpapers&q=` | `session.create` | T02, T10 |
| `POST /v1/workbench/sessions/{id}/context` `{items[]}` | `session.manage` | T02, T10 |
| `DELETE /v1/workbench/sessions/{id}/context/{item_id}` | `session.manage` | T02, T10 |
| `POST /v1/workbench/sessions/{id}/drill` `{artifact_id, group_key}` | `session.manage` | T03, T20 |
| `GET /v1/run-artifacts/{id}/preview?sheet=` | `agent_run.read` | T03, T20 |
| `GET /v1/run-artifacts/{id}/download` | `export.create` | T03, T20 |

The existing `GET /v1/workbench/sessions?subject_ref=` (TAX-08 History, DEC-4316) and
`POST /v1/workbench/sessions` with a `subject_ref` keep their shapes: the list route answers the
subject list when `subject_ref` is given and the filtered list otherwise; the create body accepts
either a `subject_ref` or nothing (a blank firm-wide session).

## Tools (C17), capability, flags, migrations
- Tools: `tax.season_counts` (compute, aggregate only), `binders.read`, `workpapers.read_section`,
  `assurance.read_materiality` (amber); `identity.list_offices`, `files.list_folders` (red).
- Capability `workbench.assistant` v1 per W-02 §6: loop, medium tier, `client_data: none`, never
  `tri`, propose only `files.propose_save`, limits as listed; eval suite frozen in S40 (W-02-T07).
- Flags (W-02-T03): `workbench.enabled`, `workbench.plans`; boolean, default false, owner
  notanaskhan, `expires: 2028-07-31` under ADR-089. In the repository's calendar the P-10 flags
  expire 2027-05-07 (DEC-137); the W-02 flags take the epic's 2028-07-31, before the Sep 1, 2028
  window, and the flag-expiry lint holds them.
- Migrations: `workbench_sessions_v2` (W-02-T06, 0850+), `agent_step_failed_items` (W-02-T19).
- Workflows: `WorkbenchSessionWorkflow` `workflow.patched("w02-session-v2")` (T15) and
  `AgentRunWorkflow` `workflow.patched("w02-failed-items")` (T19), with replay histories.
- Outbox: `workbench_session.created`, `.renamed`, `.deleted`, `.context_changed`. Audit events:
  the same plus `workbench_session.context_added`, `.context_removed`, `run_artifact.downloaded`.

## Acceptance criteria (the epic's §3, verbatim there)
- **List (3.1):** AC-L1 eight rows in order, amber dot, "via Agent"; AC-L2 Running 3 → Running 4;
  AC-L3 title-only search, "No sessions match 'K-3'."; AC-L4 rename (`title_source` manual) and
  soft delete with the dialog copy; AC-L5 owner-only manage (403 otherwise); AC-L6 first-message
  title (56 characters).
- **Visibility (3.2):** AC-V1 locked thread with metadata only; AC-V2 walled rows absent from rows,
  counts and search; AC-V3 membership per Q1; AC-V4 portal 403 and no workbench import.
- **Context (3.3):** AC-C1 blank session copy; AC-C2 suggested prompt fills the composer, sends
  nothing; AC-C3 picker lists only openable records; AC-C4 code-computed summary lines and one
  `context_added` per item; AC-C5 removal narrows later turns.
- **Answers (3.4):** AC-A1 grounded $48,600 answer, sums by code; AC-A2 no severity or decision;
  AC-A3 "Nothing was written." by code; AC-A4 unverified shows "Unsupported"; AC-A5 citation opens
  SHL-08; AC-A6 discovery facts (224 · 79 · 145 · 214 · 241 · 3 offices).
- **Questions (3.5):** AC-Q1 to AC-Q4.
- **Plans (3.6):** AC-P1 plan card, no bulk read before approval; AC-P2 owner-only approve; AC-P3
  edit re-validates; AC-P4 cancel line; AC-P5 `workbench.plans` off gives a notice.
- **Gathering (3.7):** AC-G1 to AC-G5 (the per-item failure ledger, Retry those 3).
- **Results (3.8):** AC-R1 to AC-R5 (preview from the stored artifact, audited download, drill
  without a model call).
- **Save to Files (3.9):** AC-W1 to AC-W7.
- **Run log (3.10):** AC-U1 to AC-U3. **Gated (3.11):** AC-D1 to AC-D3.
- **Invariants (3.12):** INV-1 to INV-5 with the tests the epic names.

## S40 rows
T01 (this), T02 contract stub, T03 protected bundle, T04 status and glossary rows, T05 consumer
contract tests, T06 migration, T07 eval suite, T08 frontend skeleton. T09 onward are S41 to S45.
