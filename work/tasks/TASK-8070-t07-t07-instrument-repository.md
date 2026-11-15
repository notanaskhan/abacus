---
id: TASK-8070
title: "T-07-T07 part: the instrument tables' repository"
spec: SPEC-656
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t07-t07-instrument-repository
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T07
---

## Objective
The part of T-07-T07 that S45's T12 service unblocked. The 28 statements the instrument service ran
inline now live in `tax/instruments/repository.py` (ADR-012: routes, service, repository).

## Built
- `tax/instruments/repository.py` holds the 28 statements as public names. They cover trust
  profiles, governing instruments, segmentations, clauses, interpretations, determinations and
  their versions, the reviewable reads and the L3 lock.
- `service.py` reads and writes only through `repo.*`, inside its own tenant session or unit of
  work. Its behaviour is unchanged; no statement changed.

## Partial
The fiduciary computation (T16) and estate (T22, T23) tables get their repositories with those
services.

## Progress log
- `2026-11-15` — Moved. Lint, pyright, banned_patterns and import-linter are clean; the T-07 unit
  suites run at the end pass.
