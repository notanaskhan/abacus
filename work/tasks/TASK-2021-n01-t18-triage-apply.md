---
id: TASK-2021
title: N-01-T18 Triage apply
spec: SPEC-380
acceptance_criteria: [AC-25]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T18
branch: s15n-n01-t18
created: 2026-10-29
updated: 2026-10-29
---

## Objective
INB-02's bundle, the destinations picker with `register_intake_destination`, Apply in one unit
of work (file as a new item or version n+1 with supersede or keep both, request fulfilment,
ignore with a reason, hold) and bulk-file (DEC-1061).

Acceptance (backlog row): "Superseding never deletes, an agent or system context is refused at
all layers, Feld Intake goes from 2 to 1, and the PR merges by the Thu May 27, 2027 train for M8."

## Built
- `communications/triage_apply.py`; routes live in `intake_contract.py`; `api.py` exports the
  destination slot.
- `evidence/intake_filing.py` (`file_intake_object`), exported.
- Stub test live paths; OpenAPI and client regenerated. Stacked on N-01-T14.

## Tests
Build-only (Ayush, 2026-10-29): no tests written or run; at the end review.

## Progress log
- 2026-10-29: built (S15 group B, build-only). ruff, pyright, lint-imports, banned_patterns clean.
