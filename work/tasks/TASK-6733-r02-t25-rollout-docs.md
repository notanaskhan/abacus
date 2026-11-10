---
id: TASK-6733
title: "R-02-T25: rollout and docs: RB-71 portal rollout, RB-01 flag section, C10 and C18 v1 frozen, screen deviations, portal skill note"
spec: SPEC-646
acceptance_criteria: [AC-31, AC-33]
risk_zone: green
status: in-review
branch: s35-r02-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: R-02-T25
---

## Objective
All three flags are on for the canary after both founders approve, and both contract docs read v1 frozen.

## Plan
- `docs/runbooks/RB-71-portal-r02-rollout.md` (new) and its index row. It covers:
  - the email-template import checklist (`notification.approval_requested`, `notification.governance_letter_sent`, "Deliverable ready"; database content per environment);
  - the pre-flip journeys;
  - the canary flip in the Tue Feb 29, 2028 slot, then the real-firm flips on Tue Mar 7 and Tue Mar 21 (`make flag` with the other founder's approval);
  - rollback and what stays;
  - the Thu Apr 13 flag-renewal ticket.
- `docs/runbooks/RB-01-*.md`: a section on flag flips and their rollback, pointing to RB-71.
- `docs/contracts/deliverables.md` (C10) and `docs/contracts/portal-approvals.md` (C18): v1 frozen 2026-11-10, with the register rows in `docs/contracts/README.md`.
- `docs/screens/POR-08`, `POR-09`, `POR-15.md`: S35 deviations (no AUD-20 row yet, j22 8 and j05 P unwalked, POR-09 g/h/i, comment notifications, author-only questions).
- `.claude/skills/portal-screen/SKILL.md`: the client-comment anchor note.

## Partials (flagged)
- **The canary flip:** an operation for the Feb 29, 2028 slot (both founders), not a code change. The runbook is ready.
- **Capacity ledger:** the solo edition keeps none (`docs/plan/AMENDMENT-solo.md`), so nothing is updated.

## Progress log
- 2026-11-10: written; validate_docs at the end pass.
