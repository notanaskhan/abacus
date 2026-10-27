---
id: TASK-1405
title: Reconcile the Sprint 10 rows' status in backlog.csv
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: green
status: in-review
epic: F-01
plan_key: S10
branch: s10-leftovers
created: 2026-10-27
updated: 2026-10-27
---

## Objective
All 59 sprint-10 rows in `docs/plan/backlog.csv` said `todo` (P-04-T18 `partial`). Set each from
what is on main, with one line of evidence per row in `docs/plan/status/status-verified.csv`.

## Result
- **done (43):** A-01-T18, T19, T21, T31; A-02-T10..T14; F-05-T61; G-01-T16; G-02-T08..T12;
  I-01-T01..T03; K-01-T01, T02; P-03-T19, T21; P-04-T18..T20; P-06-T26, T27; P-07-T41..T46;
  Q-03-T038..T040; R-01-T18..T22; Q-02-T43 (this branch).
- **partial (6):** F-05-T60 (no board locked), P-03-T20 (handoff copy, DEC-460), Q-03-T043,
  T044, T046 (perf stack), P-08-T28 (staging rollout is human).
- **todo (10):** F-09-T94..T99 (programme, vendor, counsel), Q-02-T44 (paid Bedrock runs),
  Q-03-T041, T042 (pen test #1), Q-03-T045 (four clean sprints and the founders).

Each PR was checked on `origin/main` (`git log --grep "(#NNN)"`): #429, #430, #431, #432, #433,
#434, #436, #437, #438, #439, #444, #450, #463, #464, #468, #469, #470, #472. The P-04-T18 row
already in `status-verified.csv` (the TASK-100 fieldwork sign-offs) is replaced by #429's.

## Progress log
- 2026-10-27: reconciled on s10-leftovers. The file keeps its CRLF endings; only the `status`
  field of the 59 rows changed.
- 2026-10-27: targeted tests and gates clean; held in the s10-leftovers PR.
