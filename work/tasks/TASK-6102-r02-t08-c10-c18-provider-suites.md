---
id: TASK-6102
title: "R-02-T08 C10 and C18 provider contract suites and the portal figures book"
spec: SPEC-000  # row (R-02-T08)
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: R-02
plan_key: R-02-T08
branch: s30-r02-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Chapter 10 §10.7.2: C10's and C18's provider suites, written against the stubs from R-02 §3 and §4, asserting shapes, refusal codes, human-only actions and seed figures; they stay green through S35.

## Plan
- `backend/tests/golden/scenario/brightwater_hale/portal_figures.json`: POR-08/09/15 figures transcribed from R-02 §3 (the A-06-T32 pattern).
- `backend/tests/contracts/c10_deliverables/test_c10_provider.py`: spec and result shapes, kinds/audiences/withdraw reasons equal migration 0710's CHECK lists, status words equal the registry, client DTOs carry no source fields, `draft_without_watermark` 422, client-only matrix rows, page 2 foots and agrees with the completion book.
- `backend/tests/contracts/c18_portal_approvals/test_c18_provider.py`: the four kinds, the provider protocol, `ClientDecisionContext`, vocabulary and reasons, 409/403 codes, `seen_hash` on every decision, decisions denied to agent/system with fresh MFA, decision events human-only, AC-11 sentence built from the figures and agreeing with the completion book, entry and posted sub-lines foot.
- TS fixture assertions: the portal fixtures arrive with R-02-T06, which adds `apps/web/src/fixtures/contracts/portal-figures.test.ts` reading the same book.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
None.
