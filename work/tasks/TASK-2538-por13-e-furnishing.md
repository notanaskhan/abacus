---
id: TASK-2538
title: "POR-13 electronic-furnishing consent (DV-12) with the firm's disclosure as content"
spec: SPEC-502  # AC-5; T-02 §3.7, DV-12; docs/screens/POR-13.md
acceptance_criteria: [AC-5]
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T27
branch: s20e-por13-efurnishing
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Close T-02-T27's other open piece: before the first download a recipient sees the firm's
counsel-approved electronic-furnishing disclosure and consents or declines (DV-12).

## Plan (amber)
- Migration 0590 `k1_furnishing_disclosures` (insert-only); matrix `k1_disclosure.import`.
- `tax/k1_disclosures.py`: import, newest, consent check, download gate; portal read; routes.
- POR-13: the consent sheet before the first download; fixture handlers; tests.
- Tests: `test_t02t27_e_furnishing.py`; T-02-T26's consent test names a published version.

## Progress log
- `2026-11-01` — Built on `s20e-por13-efurnishing` (stacked on `s20e-por13-upload`).
  Integration 2 + portal 6 passed; POR-13 13 passed.
