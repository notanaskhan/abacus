---
id: TASK-108
title: "Live walk-through of TASK-100 to TASK-107 on the dev stack; one fix: a selected procedure's label in the rail and section header"
spec: SPEC-040
acceptance_criteria: [AC-11]
risk_zone: green
status: done
branch: task-108-walk-fixes
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Walk-through (2026-10-20, Playwright, Dana / Sam / Casey)
All 13 steps passed:
1. Home queue (Dana, 27 items: approvals first).
2. Requests status counts and quick view.
3. Follow-ups draft-now. Nothing was overdue on this engagement, so the empty state showed.
4. Fieldwork steps; Dana raised a review note.
5. Sam's queue showed "Respond to 1 review note".
6. Sam responded.
7. Sam raised a finding from the exception row.
8. Dana cleared the note.
9. Dana recorded a −12,500 factual misstatement; the summary read "Below performance materiality".
10. Casey said a request doesn't apply ("Already sent another way").
11. The firm saw the badge.
12. Casey undid it.
13. Firm settings.

Failed calls: only four expected 403s for staff on firm-admin reads (onboarding, templates, ledger-import formats and status).

## Fix
- `procedureState`: the procedures list's copy has the status but not the selection, so a selected procedure read "Set up" in the rail and the section header. It now reads "Selected" from the status.
