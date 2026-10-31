---
id: TASK-2616
title: P-11-T16 full-stack E2E render-letter.fullstack.spec.ts
spec: SPEC-520
acceptance_criteria: [AC-6, AC-17, AC-18]
risk_zone: green
status: in-review
epic: P-11
plan_key: P-11-T16
branch: s21-p11-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"The spec passes nightly on staging with axe clean on the viewer, INV-1 to INV-5 asserted and the
draft's render_hash stable across two runs." (P-11 §1, AC3.4.)

## Scope
**In**: `apps/web/e2e/documents/render-letter.fullstack.spec.ts` on the harness projects (fixme
in fixture: no renderer). Priya Raman reads the seeded Copperleaf draft (composer, then C11's
generated document): its PDF `render_hash` is the same on two reads and, when
`ABACUS_E2E_COPPERLEAF_RENDER_HASH` carries the previous night's value, the same across runs;
SHL-08 opens the draft PDF (axe and INV-1 to INV-5 after each step; no Approve, Send or Sign); a
fee change in Draft (`PUT …/letter/composer`, If-Match) renders version 2 with a new hash.
**Gap (DEC-1664)**: the row's "change the fee to see Out of date" needs a fee change on the
engagement to reach the letter as a C11 source event; `engagement_letter` registers no source
event (reporting/engagement_letters.py), and ENG-04's live swap is N-02-T37. That step is a
named `test.fixme` with its owners; the composer path proves version 2 meanwhile. Hosted runs need
the seed's synthetic engagement id in `ABACUS_E2E_COPPERLEAF_ENGAGEMENT` (skips without it).

## Progress log
- 2026-10-31: built; runs nightly on full stack and staging (not on pull requests).
