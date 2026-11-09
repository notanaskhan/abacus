---
id: TASK-6509
title: "A-07-T32: code-only Accrued Agent capabilities on the v1 recording path (digest, readiness, bring-down, letter compose, archive readiness)"
spec: SPEC-644
acceptance_criteria: [F10]
risk_zone: red
status: in-review
branch: s33-a07-t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: A-07-T32
---

## Objective
Five capabilities, no model call, each with a code plan, ToolCards, AgentBlocks narration from
templates, verified citations, and drafts or suggestions only; registered for the P-09 dock.

## Plan (red)
1. `agents/code_runs.py` (PROTECTED): `CodeRun`, `CodeStep`, `check_plan` (no reserved verb),
   `record_code_run` (v1 deterministic run, a `tool` step per ToolCard, a `narration` step whose
   summary is validated AgentBlocks with its facts, the run closed; `agent_run.code_recorded`
   with `model_calls=0`). Dock labels in `agents/runs.py`.
2. `assurance/agent_capabilities.py`: `eqr_digest` ("I have not evaluated them"),
   `completion_readiness` (#4231), `record_bring_down` (#4240, as the EP via Agent, from the
   bring-down activity), `letter_compose` (rep letter compose, governance regenerate),
   `archive_readiness` (#4302); the bring-down also-required provider for A-07-T30.
3. Routes: `POST …/eqr/digest:build`, `POST …/completion/readiness:check` (new action
   `completion.check_readiness`), rep-letter compose, governance compose and binder-index now
   record their runs.
Rollback: revert; no migration.

## Progress log
- `2026-11-09` — Built; unit tests written, not run (end pass). Partial: no citations yet in the
  narrations (the facts are counts; the digest cards' own citations stay on the cards); the
  rep letter's `drafted_by_run_id` is not set (the run records the letter; the version insert is
  A-07-T24's); the 60 s debounce trigger for #4231 on `completion.item_changed` is not wired (the
  route runs it on demand); T40's conformance suite is a later row.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3109 | The code-run recording shape, the reserved verbs and the bring-down's initiator | no |
