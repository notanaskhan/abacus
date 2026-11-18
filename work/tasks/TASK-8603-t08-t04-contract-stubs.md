---
id: TASK-8603
title: "T-08-T04: Contract stubs FD-1 filing deadlines, SS-1 season setup and TP-1 tax practice tools"
spec: SPEC-710
acceptance_criteria: [AC-36, AC-39]
risk_zone: amber
status: in-review
branch: t08-t04-contract-stubs
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-08-T04
---

## Objective
Spec section: docs/plan/epics/T-08.md §4.3, §8.1. Pydantic VMs with classification tags, 501 routes under one action each, docs/contracts files, regenerated api-client.

## Plan (amber)
1. engagements/season_contract.py (SS-1, 10 routes), practice/filing_deadlines_contract.py (FD-1, 4 routes; portal principals 403), tax/practice_tools_contract.py (TP-1, 27 routes); each route: client 404 (FD-1: 403), flag 404, human-only 403, then 501.
2. Routers mounted in each module ROUTERS; model names prefixed Season*, FilingDeadline*, TaxPractice* (generated-client uniqueness).
3. docs/contracts/{season-setup,filing-deadlines,tax-practice}.md; make generate; apps/web tsc clean.
4. Rollback: revert the PR; the flags stay off.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5603). Partial: seed-derived fixtures for the 33 artboards come with the T-08 scenario slice (T-08-T39, S55) and each screen task; fixture mode renders nothing for these screens until then. Gates and tests run once at the S50 end pass (build first, test last).
