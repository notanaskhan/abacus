---
id: TASK-6515
title: "P-10-T25: the loop harness — limits, questions and plans as fields, escalation, provenance before emission, active_ms"
spec: SPEC-647
acceptance_criteria: [AC-H1, AC-H2, AC-H3, AC-H5]
risk_zone: red
status: in-review
branch: s33-p10-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-10-T25
---

## Objective
A trajectory repeating an identical call stops with max_repeat, an uncited number is marked
Unsupported and never emitted as fact, and active_ms excludes waits.

## Plan (red)
1. `agents/harness.py` (new, PROTECTED): `run_step` over `HarnessPorts` (`turn`, `tool`), so each
   turn and each tool call runs as its own activity in AgentRunWorkflow; `Limits` from the
   spec's `LimitsV2`; identical calls keyed by tool and canonical arguments; escalation →
   `needs_input`; `question`/`plan` output fields handed back; `settle_blocks` validates each
   AgentBlocks part against the run's facts and verified citations and replaces a failing part
   with "Unsupported" plus its reason; `active_ms` counts turn and tool time minus the ports'
   reported waits.
2. Unit tests on a scripted FakeModel trajectory (`tests/unit/agents/test_p10t25_harness.py`).
Rollback: revert; nothing calls it yet (AgentRunWorkflow wires the gateway and C17 ports).

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). Built on ADR-234 as proposed (DEC-3016:
  acceptance is Ayush's). Partial: the gateway/C17 port adapters inside AgentRunWorkflow land with
  the run workflow row; AC-H4 containment is the conformance suite's.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3115 | The harness's limit order, repeat rule and Unsupported rendering | no (ADR-234) |
