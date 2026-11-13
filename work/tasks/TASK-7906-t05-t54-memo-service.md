---
id: TASK-7906
title: T-05-T54 Preparer memo service
plan_key: T-05-T54
spec: SPEC-651
acceptance_criteria: [AC-F9]  # approving the M-2 fix turns the memo Stale with the moved figure; regenerate keeps a person's section
risk_zone: amber
status: in-review
branch: t05-t54-memo-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The memo's facts and sources from code, the draft run, a person's section edit, L1 adopt and L2
approve (never the preparer), staleness on cited figures with a went_stale event, affected-only
regenerate, and the opportunities list.

## Plan (amber)
- Files: `tax/memo_service.py` (new: facts, sources, workflow, edit, sign, staleness,
  opportunities, reviewable), `tax/workbook_contract.py` (memo GET, draft, section, adopt, new
  approve, opportunities), `tax/api.py` (register; workflows), staleness hooks in
  `tax/entity_sections.py`, `tax/workbook_fix.py`, `tax/cell_edit.py`; SIGNOFF-001 allowlist.
- No migration (0830's tables). Tests: `backend/tests/unit/tax/test_t05t54_memo_service.py`.
- Rollback: revert the PR (memo versions and events are insert-only rows that stay).

## Partial
- Stored segments cite sources by position; the read gives section bodies without C4 citation ids
  (TXP-01's CiteMarkers read them with T-05-T59).
- No §752 liabilities or depreciation facts yet: their sheets' layouts have no reader (the
  drafter marks those sections "Unsupported" rather than inventing figures).
- `allowed_actions` on the memo read is empty until TXP-01 (T-05-T59) defines its buttons.

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4909 | code's facts, fingerprint staleness, affected-only regenerate, draft workflow | no |
| DEC-4910 | L1/L2 as P-04 sign-offs on the memo; preparer never approves; opportunities | no |
- 2026-11-13 (end pass): MemoDraftWorkflow's imports passed through (the sandbox refused the
  kernel's random at import); `memo-draft-v1-{drafted,failed}.json` recorded and replaying.
