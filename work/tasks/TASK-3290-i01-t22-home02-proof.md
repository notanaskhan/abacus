---
id: TASK-3290
title: I-01-T22 HOME-02 proof and the flip runbook
spec: SPEC-000  # I-01-T22 row; docs/screens/HOME-02.md
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: I-01
plan_key: I-01-T22
branch: s27-i01-t22
created: 2026-11-05
updated: 2026-11-05
---

## Objective
Tier C lock for a, c, d, e, f, g in fixture mode; Tier D for 790 = 310 + 480 and the 576 evidence
pane; axe and keyboard; j23 steps 2 and 4 full stack and j13 steps 2-3 in fixture mode (tax hosts
fixme); per-firm `home.approvals` flips in the Tue Nov 2 and Nov 9, 2027 windows with a written
rollback.

Acceptance (backlog row): "HOME-02 is parity-locked, axe clean and walkable for the audit half on
staging, and both founders approve the flip runbook."

## Progress log
- 2026-11-05: Locking the screen showed a–g well off the handoff (a 5.62, e 5.22, d 3.93, g 3.81),
  so the screen was fixed, not masked (DEC-2263). Now a 2.90, c 1.75, d 1.99, e 2.37, f 0.19, g 0.99
  against the 3% Tier C limit, with the limit unchanged. Masks: Decide on a (DV-1), the queue and segmented on g
  (DV-6). Tier C is report-only in `parity.spec.ts`, so the numbers are recorded in the contract.
- Tier D: 4 pass (`tier-d-home.spec.ts`). Axe and Tab walk on a–g and J/K on the queue: 8 pass
  (`e2e/home/home-02.spec.ts`). j13 2-3 passes on the fixture project.
- Written: RB-48, with rollback and verification.

## Open (not met here)
- **Walkable for the audit half on staging**: not walked. No staging run from this laptop.
- **j23 steps 2 and 4 full stack**: not run. j23 2 stays `test.fixme` (A-09); j23 4 passes on
  fixtures only.
- **Both founders approve the flip runbook**: human, open.
- The T9 `h-full` change is checked by Tier D t9a–c; the T9 and TPL-09 pixel rows are re-measured in
  Q-03-T186.
