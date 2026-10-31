---
id: TASK-2617
title: P-11-T17 document-services runbook part 1, reporting README, skill section, flag owner and expiry
spec: SPEC-520
acceptance_criteria: [AC-4, AC-30]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T17
branch: s21-p11-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"A staging drill republishes a prior template version and re-renders without a deploy, and the
flag carries an owner and an expiry outside the Sep 1 to Oct 20 window." (P-11 §10.)

## Scope
**In**: `docs/runbooks/RB-43-document-services.md` part 1 (failed renders by code, the kill switch,
engine upgrade and golden re-baseline with both founders' approval, regenerate, template rollback
by republishing a prior version, the staging drill), its row in `docs/runbooks/README.md`, the
reporting README's operations and live-file notes, and `.claude/skills/backend-module` "Adding a
document kind". The flag `reporting.generated_documents` already carries owner ayushkbhatia and
expiry 2027-04-21 (override DEC-137), outside the window; the runbook records that its renewal must
also land outside it (RB-26).
**Findings recorded (DEC-1665)**: the row's path `document-services.md` takes the next runbook
number (RB-43); regenerate keeps a document's template version, so after a republish a draft is
re-drawn by its consumer (ENG-04's Draft save with the republished version), and new renders use the
republished version at once. **Human**: the staging drill itself (rehearse by Fri Aug 20, 2027) and
its rehearsal-log row.

## Progress log
- 2026-10-31: written; the drill is a staging task after the batch deploy.
