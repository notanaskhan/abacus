---
id: TASK-8436
title: "A-08-T24: rest: the fieldwork fan-out runs at most 8 in flight"
spec: SPEC-657
acceptance_criteria: [AC-9]
risk_zone: amber
status: in-review
branch: s48r-fan-out-cap
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T24
---

## Objective
A-08 §5 asks for per item fan-out with at most 8 section drafter runs in parallel; T24 started every run at once. Every run is now recorded first, then one SectionDraftFanOutWorkflow starts them as child workflows, 8 at a time.

## Plan (amber)
1. agents.section_draft: split start into _record (checks, DF-04, cap, insert, audit) and dispatch; add start_many (record all, then one fan-out workflow for the new runs).
2. agents.workflows.SectionDraftFanOutWorkflow: child SectionDraftWorkflow per run under its old id, asyncio.Semaphore(8), ABANDON on parent close, a failed child never stops the rest.
3. fieldwork_runs._fan_out calls agents.api.start_section_drafts.
4. Unit tests: DF-04 before any dispatch; 12 sections record 12 runs and start one fan-out with max_parallel 8; a replay starts nothing. Replay history at the end pass.

## Progress log
- `2026-11-17` — Built (S48 rest, DEC-5425). Attribution, idempotency keys (key:section) and DF-04 behave as before; the child workflow ids are the old SectionDraftWorkflow ids, so the run pane reads the same runs. Gates and tests run once at the S48 end pass (build first, test last).
