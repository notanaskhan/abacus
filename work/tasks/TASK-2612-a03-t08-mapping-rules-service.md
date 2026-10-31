---
id: TASK-2612
title: A-03-T08 mapping rules and service (C9 v2 live)
spec: SPEC-580
acceptance_criteria: [AC-1, AC-2, AC-4]
risk_zone: red
status: in-review
epic: A-03
plan_key: A-03-T08
branch: s21-a03-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"Granite Peak's 128 accounts are mapped by rule or left Needs review with no suggested row,
confirm returns 409 unmapped_accounts while any remains, and a successful confirm writes exactly
one L1 sign-off and mapping_set.confirmed." (A-03 §3 F6; ADR-341.)

## Scope
**Already on main** (TASK-345, 5009, 5010): compute-on-read mapping (edits insert-only, newest
wins), prior-year match by normalised code, tallies, `unmapped_accounts`, the L1 sign-off with
`mapping_set.confirmed`, staleness and `mapping_set.went_stale`, `register_reviewable`.
**In**: `ledger/compute/mapping.py` (the rules moved into the pure compute package with
confidence in words, tallies and grouping subtotals with `off` against a source summary line;
`ledger.mapping` re-exports for its callers); ledger reads `mapping_set_by_id`, `account_edits`,
`mapped_trial_balance` (`ledger.api`); `assurance/mapping_live.py` behind the C9 v2 routes (list,
run, read with filter and `group_by=fs_line`, run progress, one account's edit with
`seen_version`, confirm with `seen_hash`, mapped trial balance); the gate authorises on the set's
own engagement; error codes `stale_version`, `content_changed`, `mapping_run_in_progress`.
**Out (DEC-1661)**: `TbMappingWorkflow` (ADR-341 §5 computes on read, so the run is ready at
once; the route answers ready); the predecessor-file prior source (no table holds parsed prior
keys; `prior_source` reads `prior_engagement`); `group_by=fs_line` on A-02's trial balance route
(the mapping set's own `group_by` and the mapped trial balance serve AUD-31 and A-04); the
Planning › Trial Balance & Mapping rail section (A-03-T11 with AUD-31's live swap); source summary
lines for `off` (the TB of record carries none today: subtotals compute, `off` stays null).

## Plan
1. [x] Move the pure rules; add tallies and subtotals. 2. [x] Ledger reads. 3. [x] Live service
and routes. 4. [x] Tests: compute unit (128 accounts) and HTTP (run, 409 rerun, rows and tallies,
409 unmapped, edit and 409 stale, 409 content_changed, confirm with one L1 and the event, mapped
TB per FS line with the view's hash, a stranger refused). Rollback: revert (no migration).

## Progress log
- `2026-10-31` — Compute 7 passed; HTTP 4 passed first run; ledger unit suite 172 still green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1661 | C9 v2 mapping live on the compute-on-read design; deferrals named | No |
