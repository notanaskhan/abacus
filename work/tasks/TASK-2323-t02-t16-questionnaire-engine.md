---
id: TASK-2323
title: T-02-T16 questionnaire engine
spec: SPEC-502
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T16
branch: s18-t02-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Questionnaires in requests: migration 0467; template import (CSV/XLSX/JSON, isolated parse, dry-run
diff, human publish); organizer instantiation with prior-year values by code; team questions and
inquiries; firm reads; TRI on organizer answers.

## Plan
- `requests/questionnaire_templates.py` (pure), `requests/questionnaires.py` (service), firm routes
  live in `questionnaires_contract.py`, registry, schema_check, contract doc, DEC-1369.
- Tests: unit parser (5), contract stubs (33), integration acceptance (end review).

## Progress log
- `2026-10-30` — built (DEC-1369). `[skip ci]`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** T-02-T22 portal questionnaire routes (stacked on this).
