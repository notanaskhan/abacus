---
id: TASK-6627
title: "P-11-T38: document services runbook part 2, evidence and reporting READMEs, temporal skill, evidence-storage reference"
spec: SPEC-000  # row (P-11-T38)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: s34-p11-t38
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-11-T38
---

## Objective
A staging drill runs the backfill and the kill switch from the runbook alone, and the yearly
refresh procedure names its owner and golden corpus.

## Plan (red, docs only)
1. `docs/runbooks/RB-43-document-services.md` §9–§14 (the row's `document-services.md`):
   Textract outage, refusal spikes by gate reason, the cost cap and the kill switch, the backfill
   as an ECS one-off task never from a laptop, the yearly form-map refresh (owner ayushkbhatia,
   due Dec 1; golden corpus and map tests named), the staging drill.
2. `evidence/README.md` OCR section; `reporting/README.md` operations; the temporal-workflow skill's
   operator-started workflows; `evidence-storage.md` "What OCR adds".
No code. Rollback: revert.

## Progress log
- 2026-11-10: written.
- Partial: the staging drill (§14) needs staging; the rehearsal log stays empty until it runs.
