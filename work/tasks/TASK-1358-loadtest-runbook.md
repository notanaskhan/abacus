---
id: TASK-1358
title: Load-test runbook and the loadtest skill (Q-03-T046)
spec: SPEC-000  # no Q-03 SPEC: chapter 10 section 10.11 and the Q-03-T046 row
acceptance_criteria: [AC-1]  # Q-03-T046: AY runs a x1 profile on the perf stack from the runbook alone
risk_zone: green
status: in-review
epic: Q-03
plan_key: Q-03-T046
branch: s10c-ops
created: 2026-10-27
updated: 2026-10-27
---

## Objective
`docs/ops/loadtests/README.md` and `.claude/skills/loadtest/SKILL.md`: create the perf stack, seed a
profile, run, read percentiles and OTel, record results only, destroy the stack, never against a
database a hosted build is using.

## Plan
- Runbook: what exists today; a laptop rehearsal that works now (x1, `smoke`, `journeys`,
  `pbc_import_burst`); the perf-stack create, seed, run, read, record and destroy steps, each
  naming what it waits on; a failure table.
- Skill: the never-list, how to add a profile (personas, targets, vars, bodies, tests), run, read,
  record. Written only; no load test run against anything hosted.

## Not done
- The acceptance (AY runs x1 on the perf stack from the runbook) waits on Q-03-T036
  (`infra/envs/perf`, its create and destroy workflow, an ops route for the fleet loader) and
  Q-03-T043 (a harness target inside the perf stack). The runbook marks those steps.

## Progress log
- 2026-10-27: written. No load test run (session rule).
