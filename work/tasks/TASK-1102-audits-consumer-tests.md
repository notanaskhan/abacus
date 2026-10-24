---
id: TASK-1102
title: Consumer contract tests for the audits stub and the C5 v1.1 additive fields (A-01-T03)
spec: SPEC-330
acceptance_criteria: [AC-8]
risk_zone: amber
status: done
epic: A-01
plan_key: A-01-T03
branch: s7-a01-audit-wedge
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The suite runs in N's CI and asserts tile footing, counts minus the active tile, no hidden-count field and registry status codes."

## Plan (amber zone)
- **pytest:** `backend/tests/contracts/audits/test_audits_consumers.py` (schema and matrix only: no hidden-count or amount field reachable from any audits response, P-36 envelope and caption, every status field equals the registry's stored codes, the tile filter's codes, no single audit, EBP plan kinds, tag classification, rail row link and grammar, C5 v1.1 fields additive and optional, Source Documents totals and `counted` bands).
- **TS:** `apps/web/src/fixtures/seed/audits-index.ts` (AUD-01's 27 rows from the E0 engagements with the spec's index facts; `auditIndexPage` with counts minus the active tile; Northwind's Source Documents aggregate) and `apps/web/src/fixtures/contracts/audits.contract.test.ts` (typed with the generated client, validated against OpenAPI at run time: a 27 = 7 + 9 + 6 + 2 + 3, caption 14/6/4/3, segments 6/14/7, b 2 of 27 with unchanged tiles, c Sep 18/21/25/28, e empty, Bayside 13 days, Fairhaven no PBC, walled totals 25, Source Documents 24 = 11 + 1 + 12 with 3/5 · 4/6 · 3/7 · 1/4 · 0/1 · 0/1, g 9 overdue on Sep 21).
- **No code change** beyond a model comment; DEC-263.
- **Rollback:** revert the commit.

## Progress log
- 2026-10-24: `tests/contracts/audits` 68 passed; `vitest run src/fixtures` 20 files, 286 passed; `tsc` clean. The generated enums exclude derived codes (`processing`, `overdue`), so the suite compares with stored codes, and the overview's "Processing" pill is drawn from the audit bar's run time. Found the report-due boundary contradiction (DEC-263).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-263 | Report-due boundary, archived rows under Released, fixture tags, owed-by kinds | No |
