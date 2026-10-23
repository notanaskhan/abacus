---
id: TASK-991
title: Q-03 programme set-up, back-fill tracker, weekly quality report and the ac-test-author skill (Q-03-T001, T002, T003, T010)
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T001; Q-03-T002; Q-03-T003; Q-03-T010
branch: s6-q03-programme
created: 2026-10-23
updated: 2026-10-23
---

## Objective
- **T001:** "The S6 Friday review reads the reserve per founder and per workstream from the ledger, and no reserve row is a feature."
- **T002:** "Every one of the 55 rows has a status and an owner, and the 11 superseded rows name the replacing epic and the AC-suite task that closes them."
- **T003:** "The report runs on the Friday of week 2 and shows every metric area in chapter 10 section 10.14.2 without a commit, a build or a deploy."
- **T010:** "A fresh session following the skill writes a back-fill suite without opening any implementation file."

Q-03 has no SPEC; SPEC-000 AC-20 (`make check` passes) is the nearest binding criterion for tooling. The rows' acceptance strings above are what this task proves.

## Plan (red, because T003 is quality tooling)
- **T001:** a Q-03 section in `docs/product/capacity-ledger.md`: reserve per sprint kind (one builder column, the plan's split kept for reading the epic), per workstream, the order of spend (chapter 01 §1.8.6 rule 1), a refused-requests table, and the S6 rows.
- **T002:** `docs/quality/backfill.md`, the 55 with zone, area, spec, sprint, Q-03 row, status and suite; QD-3's 11 superseded with the replacing epic and closing task. `docs/quality/escaped-defects.md` as the log T009 writes to (F-01-T15's form is not built).
- **T003:** `backend/src/abacus_tools/quality/report.py` (standard library plus `kernel.clock`), its unit tests, and `.github/workflows/quality-report.yml` (Fridays, read-only token, summary and artifact).
- **T010:** `.claude/skills/ac-test-author/SKILL.md`.
- **Decision:** DEC-200.
- **Rollback:** revert the commit; nothing reads these files at runtime.

## What changed
- **Ledger.** S6 is 8.57 te of reserve, a normal sprint 9.38, Thanksgiving 8.44, holiday 5.63. Per workstream: the 13 rows of Q-03 §9.1, 625.75 te in all. Labels and burn-down issues are replaced by files (DEC-200).
- **Tracker.** 9 tranche 0, 35 scheduled, 11 superseded. PR B (TASK-992) moves the six S6 rows to `back-filled`; PR C (TASK-993) closes TASK-028 through P-01-T14.
- **Report.** Twelve areas (CI, Flow, Tests, Security, Contracts, Journeys, Design, Accessibility, Compute, AI, Ops, Cost). Computed today: main-green share (time-weighted, cancelled runs ignored, so batched merges whose runs are cancelled read "no data"), workflow p50/p90, PR size, open-to-merge latency and review count, escaped defects by zone and layer, refused reserve requests, back-fill burn-down, global and per-module coverage, mutation scores when `mutation.json` exists, `ac-test-author` suites, strict xfails, security and contract suite counts, journey and parity results, eval pass state, Actions minutes and real-model eval spend. The rest print "no data" with the source they wait for. A path inside the repository is refused, so the report can't be committed by accident.
- **Skill.** What to load and never open, where tests go, the header, names, the triage table, and what to record.

## Tests
- `tests/unit/quality/test_quality_report.py` (8): every area prints with no inputs; time-weighted green share ignoring cancelled runs; PR size, escaped defects and reserve refusals inside the window only; burn-down, coverage below 97%, author headers and strict xfails; parity, journeys, evals and spend; no write inside the repository; markdown and JSON written outside it; a malformed input is an error.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-200: files instead of labels and issues; xfails cite the PR that records them; the report reads files only | No issue queues in the solo edition; SKIP-001 needs `#<n>` | no |

## Gotchas and discoveries
- `.github/workflows/*` job-level `env` cannot use the `runner` context, so the workflow uses `$RUNNER_TEMP` in its scripts. Workflow-dispatch dates go through `env`, never interpolated into the script.
- Main's CI runs are cancelled by design when merges are batched, so main-green share needs finished runs to say anything; the report says "no data" rather than 100%.

## Progress log
- 2026-10-23: ledger, tracker, escaped-defect log, report with 8 unit tests, workflow, skill, DEC-200. `make check-fast` and the unit, acceptance, security and contract suites run before the PR.
