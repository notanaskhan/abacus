---
id: TASK-331
title: "P-04 / AUD-17: review notes on any reviewable, trial balance sign-offs, the sign-off matrix and G5"
spec: SPEC-313
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7]
risk_zone: red
status: done
branch: task-325-review-notes
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan keys
P-04-T18, P-04-T21 (partial; DEC-134 makes these the tables C3 extends). Recorded in docs/plan/status/status-verified.csv (TASK-901).

## Plan
- **Migration 0076:** `reviewable_notes` and `reviewable_note_events`. Rollback is the downgrade.
- **Review:**
  - `slots.py` (`register_reviewable`, `reviewables_of`, `REQUIRED_LEVELS`);
  - `notes.py`;
  - `matrix.py` (`matrix_for`, `review_gate`, registered as G5);
  - `routes.py`;
  - `record_sign_off` refuses L2 and above while notes are open.
- **Workpapers:** `workpaper_reviewables`, registered.
- **Ledger:** `review_digests`.
- **Assurance:** `tb_reviewables` (registered), `sign_off_tb`, `tb_levels`, the five sign-off routes, and `sign_offs` on the view.
- **Identity api:** exports `PARTNER_ROLES` (AUTHZ-001).
- **Web:** `ReviewableNotes.tsx` and `ReviewMatrix.tsx`; the Workpaper and TrialBalance panels; the `/sign-offs` route and tab.

## Progress log
- Renumbered from TASK-325 after merge (PR #198), because the other stream took TASK-325 to TASK-330 in parallel. Migration 0076's docstring keeps the old number, since it's already on main.
- A mistake to make into a check: writing the new notes component to `src/screens/ReviewNotes.tsx` replaced fieldwork's file of the same name. `tsc` caught it, and the original was restored from git. New screen files should check the path is free before writing.

- A test that had failed since TASK-315 (`test_ac20_importing_the_engagements_api_registers_the_lookup`): reloading the engagements api re-registered G1–G3 and the slot refused. It is fixed here: re-registering the same provider (same module and name) is a no-op. The reviewable slot follows the same rule.

## Definition of done
- [x] `tests/unit/review` (5), the workpapers tests and the pinned gate tests pass.
- [x] A local DB smoke test passes: the trial balance is listed as a reviewable; G5 is unmet with `unsigned:…:L1/L2`; a note and a response are written; a bodyless response is refused by CHECK.
- [x] spec313review, spec309, spec308 and spec041 pass.
- [x] check-fast passes.
- [x] review, workpapers, ledger, api, identity, quality, engagements and contracts (10,139) pass.
