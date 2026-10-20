---
id: TASK-098
title: Design foundation, step 4b — firm settings in the plan's settings frame (T12); a grouped section list on the left, the section on the right; headings at the plan's sizes; agent names in words on Budget
spec: SPEC-019
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-098-firm-settings
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Scope
**In**
- `AdminLayout.tsx`: "Firm settings" replaces the "Firm admin" heading and its tab row with a sticky section list in groups:
  - Firm: Setup, plus People and Walls for admins.
  - Methodology: Methodology, Knowledge documents.
  - AI and automation: Autonomy, Budget.
  - Security: Support access, for admins.
  - The emergency banner and the section sit on the right.
  - Sections are still by role; the API stays the authority.
- Headings on Methodology, its version page and Knowledge use the plan's sizes.
- Budget: agent capabilities read as work ("Evidence screening", "Entry assessment"); the id stays on hover.

## Definition of done
- [x] Web tests pass (353); the screens checked on the dev stack.
- [x] `make check-fast` passes.
