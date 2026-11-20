---
id: TASK-8855
title: "Q-03-T359: x100 November 2028 load content"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-q03t359
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-03-T359
---

## Objective
The Q-03-T376 x100 content: W1 posting (C-02-T43), October CAS month-end, TY2028 season tools.

## Done
- scenarios/november_2028.yaml with W1 dry run + post (Idempotency-Key replayed once), posting log, Oct 2028 closes, package and tax hand-off, seasons/manifests/cohorts, filing deadlines, C12 hand-off
- Runner: json_body placeholders (JSON for whole-string vars) and Step.replays (same key)
- Path pattern allows ':' custom methods
- Test: every step is an API operation; writes are dry run + one replayed post

## Progress log
- `2026-11-20` — 2026-11-20: built; 43 loadtest unit tests pass. Run is Q-03-T376 on the perf stack (human). DEC-5852.
