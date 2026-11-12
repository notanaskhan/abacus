---
id: TASK-7403
title: "P-10-T57: Independent AC tests (ADR-078) for the sessions core, run records and capability endpoint (T43, T44, T45) and the T08 matrix rows"
spec: SPEC-647
acceptance_criteria: [AC-S2, AC-S3, AC-S4, AC-RR2, AC-RR3, AC-RR4]
risk_zone: red
status: in-review
branch: s38-p10-t57
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T57
---

## Objective
Tests pass and fail if a locked viewer receives a figure, a pruned run loses its tool calls, or the
capability endpoint calls a model.

## Plan (red, tests only)
Written from SPEC-647 §3.7 and §3.9, `docs/contracts/agent-runs.md` §9 and DEC-4301 to DEC-4303.
- `tests/integration/agent_tests/test_p10t57_independent.py`:
  - Sessions: the side queue (a message while a question is open is a message, signalled
    `user_message`; the answer is `answer`), an answer must name an open question, one child run
    per write turn (two turns, two children, each idempotent), a locked viewer's body carries no
    figure or marker, a locked session takes no message (409 `session_locked`), a walled viewer
    reads 404 with nothing about the session.
  - Run records: the prune removes only rows past 30 days and the trace and export keep every
    tool call; the export and its manifest are byte-identical across the prune; moved rows freeze
    a new version; `agent_run_records` is a retention type; frozen traces refuse UPDATE and
    DELETE.
  - Capabilities: a provider that fails on any model call, no usage row and no `model.called`
    event, with and without an engagement; the first reason wins in DEC-4303's order.
- `tests/unit/agents/test_p10t57_matrix_rows.py`: T08's human-only actions are denied to agent,
  system and support; portal roles hold no `agent_run.*` or `session.*` action.

## Partial
- "Byte-identical PDF": the PDF export waits on C11's `run_trace_v1` template (TASK-7302 partial);
  the tests pin the JSON body, its hash and the manifest.

## Progress log
- `2026-11-12` — Written (S38). The matrix rows pass (6); the integration file runs at the end pass.
