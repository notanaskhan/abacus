---
id: TASK-332
title: "A-07 first slice (record mode): EQR, going concern, report and rep letter records, release and sealed archive (G6-G9)"
spec: SPEC-314
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9]
risk_zone: red
status: done
branch: task-326-completion
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- **Migration 0077:** `eqr_concurrences`, `completion_records`, `releases` and `archives`. Rollback is the downgrade.
- **Engagements:**
  - the `register_judgment_source` / `judgments_of` slot (fail closed; re-registering the same source is a no-op);
  - `set_assurance_phase`;
  - `lock_engagement`.
- **Identity:** `EQR_ROLES` and `engagement_eqrs` (AUTHZ-001).
- **Fieldwork:** `judgments` (materiality, significant risks, the SUM), registered.
- **Assurance:**
  - `completion.py` (gates G6–G9, the digest, the Merkle seal, acts);
  - models and repository;
  - `completion_routes.py`;
  - G6–G9 registered;
  - matrix actions.
- **Review api:** exports `open_note_counts` and `reviewables_of`.
- **Web:** `CompletionRelease.tsx`, plus the `/completion` route and tab.

## Notes
- Renumbered from TASK-326, because the other stream took TASK-325 to TASK-330 in parallel. TASK-331 is the renumbered review-notes task.
- The other stream renamed Button variants (TASK-329: `outline` became `secondary`, `default` became `primary`) just before TASK-331 merged, so `main` failed `tsc` on `ReviewableNotes.tsx` and `TrialBalance.tsx`. This task maps the old names in every file this stream wrote.
- `test_preregistration`'s unregistered gate moves from G7 to G4.

## Definition of done
- [x] `tests/unit/assurance` (7), the pinned gate tests, review and preregistration pass.
- [x] A local DB smoke test passes: judgments read from dev data, G5–G9 facts, and CHECKs refusing an agent concurrence, an involved EQR, a report without a document, and a bad going-concern choice.
- [x] spec314, spec313, spec309, spec308, spec312 and spec029checks (43) pass.
- [x] check-fast passes.
