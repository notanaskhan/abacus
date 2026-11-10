---
id: SPEC-648
title: P-09 agent transparency v1 — run dock (SHL-13) and run trace (WB-09) on C6 v1.1 and AgentBlocks
status: approved
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-005, ADR-019, ADR-050, ADR-065, ADR-078, ADR-166, ADR-169, ADR-230]
related_specs: [SPEC-318, SPEC-647]
created: 2026-11-08
updated: 2026-11-08
---

> **Instructions for coding agents**
> - P-09's own SPEC (P-09-T01). The design is `docs/plan/epics/P-09.md` §3 to §5; task rows are
>   `docs/plan/epics/P-09.tasks.csv`. SPEC-318 (TASK-461) remains the v0/v1 run-trace spec.
> - Contract provided: C6 v1.1 (`docs/contracts/agent-runs.md` §10), co-provided with P-10 (C6 v2).
> - Read only: nothing in P-09 decides, approves or signs off (ADR-005). The dock's human actions
>   are intents on P-10's and P-04's routes (T14).

## 1. Summary
A read-only run dock and trace drawer, so a person can see and verify what an agent did. Sprint 31
lands the contract (T01), its consumer tests (T02), AgentBlocks v1 (T03), the gateway output-check
registry (T04), the E6 front-end core (T05) and the renderers (T06). TASK-5000 to 5008 built parts of
these early (DEC-336); S31 finishes them.

## 2. ADR check (main a801fff01, 2026-11-08; DEC-2801)
| P-ID | ADR on main | State | Note |
|---|---|---|---|
| P-24 agent blocks (plan alias ADR-160) | ADR-230 | accepted | `agents/blocks.py`, `packages/ui/src/agent` |
| P-46 gateway, `converse()` | ADR-234 | proposed | P-10-T19 builds `ai_gateway/converse.py` in S31 |
| DEC-87 content and metadata | DEC-87 | decided | `run_content.read` (TASK-5002) |

## 3. Acceptance criteria (S31)
- **AC-1 (T01):** `GET /v1/agent-runs/{id}`, `…/items`, `…/trace`, `…/trace/records-read` and
  `…/trace/writes` answer the v1.1 fields (§10 of the contract), every one optional, so v1's frozen
  snapshot still passes. `access` equals `projection`. A legacy item carries its `session_kind`.
- **AC-2 (T01):** `GET /v1/agent-runs/{id}/trace/steps/{step_id}` answers 404 when the caller may
  not read the run, 404 while `run_trace.enabled` is off, and 501 until P-09-T08.
- **AC-3 (T01):** `run_trace.export` has the `agent_run.read` principals, the agent denied, fresh
  MFA and not-offshore required; an export's manifest carries the caller's projection.
- **AC-4 (T01):** the E0 fixtures foot: #4118 reads 224 + 214 + 241 + 1,946 = 2,625 records over
  9:00:00 to 9:02:41 (161 s), with 79 citations, 0 writes done and 1 waiting; #4127 is running with
  materiality blocked on a partner decision; Aug 17 failed on "CCH Axcess Tax returned 401: token
  expired"; Copperleaf Run 2 shows 6 of 9 steps complete.
- **AC-5 (T02):** consumer tests prove every SHL-13 and WB-09 view model is satisfiable from the
  stub routes and the TypeScript fixtures.
- **AC-6 (T03):** AgentBlocks v1 validates a closed nine-part union, sanitises every string, refuses
  a free number (number provenance, ADR-166 rule 10), lints copy deterministically and exports its
  JSON Schema into `packages/api-client`.
- **AC-7 (T04):** `converse()` runs the output-check registry on a structured final turn: one repair,
  then Unsupported or escalated; `call()` and the live specialists are byte-for-byte unchanged.
- **AC-8 (T05):** the RunStore polls at 1.5 s only while the run is active and the tab visible,
  orders by `seq`, resyncs on `resync`, and stops on a terminal state; `?static=1` freezes the
  scripted source.
- **AC-9 (T06):** the renderers emit React nodes only, sanitise every string, format facts through
  `format.ts`, cite through C4's CiteMarker, render an unknown part as a neutral row, and L4 lints
  the new fields.

## 4. Out of scope (S31)
The read models behind the stub (T07, T08), the dock and drawer screens (T09, T10), exports in PDF
(T11), and the human-action intents (T14) are S32 to S34.
