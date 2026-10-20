---
id: TASK-110
title: "F-01-T05 · Make main green: fix stale assertions against their spec ACs and measure coverage against fail_under 95"
spec: SPEC-045
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: red
status: in-progress
epic: F-01
plan_key: F-01-T05
branch: task-110-green-main-coverage
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
A full stage-2 run is green on main, every changed assertion is traced to a spec AC with AY's approval, and coverage is recorded with a dated ADR-116 exception if below 95.

Solo reading: the AY approval and ADR-116 are void; trace each changed assertion to its spec AC in a comment, and record any exception in `docs/product/decision-log.md` or an ADR.

## Scope
**In**
- Fix stale assertions at `test_engagements.py:897`, `agent_tests/test_board_reads_api.py:230`, `test_schema_check_db.py:1083` and any others a full run exposes
- Measure combined coverage; close the gap or record the exception

**Out**
- Lowering `fail_under`
- Skipping, deleting or loosening any test
- Ruleset and approvals

## Already built (verify, fill gaps only)
Evidence from `docs/plan/status/status-verified.csv` (status `partial`): Green main + 73% recorded (work/tasks/TASK-077); no dated ADR-116 exception in docs/adr; backend/pyproject.toml:136 still fail_under=95

Gap to close:
- Decide the 73% versus 95 gap: close with tests if at most 2 builder-days, else write the dated exception ratcheting to 95 by 2026-12-01.
- Re-run one full stage-2 on `main` and confirm green; confirm no assertion is loosened.

## Context to load
- Spec: `docs/specs/SPEC-045-repo-ci-dev-environment.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process); `docs/plan/status/status-verified.csv` row for this key
- Epic: `docs/plan/epics/F-01.md` section 3 (F4, first two stories), section 9 (row F-01-T05), section 10, section 11 (R3)
- Epic tasks CSV: `docs/plan/epics/F-01.tasks.csv` row F-01-T05
- Existing record: `work/tasks/TASK-077*` (green main and 73%)
- Coverage floor: `backend/pyproject.toml` line 136

## Plan
Steps:
1. [ ] Write the plan here (red zone), listing each failing assertion and its SPEC AC (SPEC-025 Setup-first flow; AC-20 update-column contract).
2. [ ] Run the full suite; list every failure.
3. [ ] Fix each assertion to match its spec AC, citing the AC in a comment; never skip, delete or loosen.
4. [ ] Measure combined coverage; either add tests (at most 2 builder-days) or write the dated exception.
5. [ ] Run one full stage 2 on `main`; record the run link.

Files to create or change:
- `backend/tests/unit/.../test_engagements.py`, `agent_tests/test_board_reads_api.py`, `test_schema_check_db.py` (assertions only)
- `docs/product/decision-log.md` or a new ADR (only if the exception is needed)

Tests to write (mapped to ACs):
- AC-1 -> each changed assertion carries its spec AC comment; diff review shows no skip, delete or loosening
- AC-2 -> one full stage-2 run green
- AC-3 -> recorded coverage figure and, if below 95, the dated exception; `fail_under = 95` unchanged

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one listed below
- [ ] Module README and relevant docs updated
- [ ] Decisions below recorded; ADR raised where needed

Commands:
```
make check-fast
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| | | | |

## Progress log
Append-only. Newest at the bottom.

- (none yet)
- 2026-10-20 (SU-15): main's stage 2 was red on two counts. (1) test_schema_check_db expected no update columns for `procedures`, though schema_check declares parameters, status and failure_code (SPEC-037, TASK-083); the contract line is added. (2) test_screening.py inherited a drained or blocked provider_capacity bucket from earlier tests in its shard (27 failures in shard 3/5); it now empties the bucket before and after each test, like its siblings. Shard 3/5: 27 failed before, 579 passed after. Coverage floor work (DEC-10) still open.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | |

## Gotchas and discoveries
- `fail_under` stays 95 in `backend/pyproject.toml`; only an exception record may excuse the gap.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
