---
id: TASK-2135
title: Q-03-T094 Contract and connector upkeep 2027 Q2 (the fakes register)
spec: docs/contracts/README.md
acceptance_criteria: [backlog row]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T094
branch: s16-q03-t093
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Consumer suites for AY-provided contracts (C2 half, C10, C12, C13, C18, C21) and nightly connector
suites against provider sandboxes; fakes marked unverified fixed.

Acceptance (backlog row): "No fake is reported unverified at the quarter's end."

## Progress log
- 2026-10-29: nothing marked a fake unverified, so the report read "not measured". Added
  `docs/quality/fakes.yaml` (six provider fakes, each with its suite and `verified_on`) and
  `abacus_tools.quality.fakes` (in `check-fast`: every listed path exists; `--strict` fails while
  any fake is unverified). The report row now counts them: 6 of 6 unverified, honestly — none has
  been checked against a provider sandbox. Human (Ayush): sandbox credentials from the vault, a
  nightly connector workflow, and `verified_on` dates. Consumer suites: C2 frozen with its suite;
  C13 stub with its suite; C21's stub and consumer tests are in the S16 K-02 stack (#670); C10,
  C12 and C18 are planned (S29+), so they have no suite yet.
