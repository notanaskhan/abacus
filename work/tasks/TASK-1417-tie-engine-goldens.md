---
id: TASK-1417
title: Tie engine goldens, issue link, stale on tie change, trial_balance field owner (A-02-T17)
spec: SPEC-333
acceptance_criteria: [AC-10, AC-11, AC-12, AC-13]
risk_zone: amber
status: in-progress
epic: A-02
plan_key: A-02-T17
branch: s11-integrations
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Goldens give tie for 288,500 + 96,200 - 57,450 - 14,850 = 312,400 and off 1,560.00 for the
BrokerWindow variant, and an uncited expected value is refused citation_required."

SPEC-310 built the engine (`workpapers/ties.py`), define and edit with citations, and results on
read. Left: goldens, the issue link (0193 columns), `tie_out_check.changed` reaching P-04's stale
consumer, the field owner. The reviewable is registered by assurance since SPEC-313.

## Plan
- Goldens `backend/tests/golden/workpapers/ties.yaml` and `tests/unit/workpapers/test_a02t17_tie_goldens.py`.
- `workpapers/tie_out.py: link_issue` (check's version as `seen_version`, the issue on the same
  engagement via `review.api.issue_engagement`, set once; audited `tie_out_check.issue_linked`);
  the C9 route `POST …/checks/{check}/issue-link` goes live; checks show `issue_id`.
- `TieOutCheckChanged` outbox event (define, edit, link) with `trial_balance_id`; review's stale
  sources gain it; the trial balance's signed digest (assurance) now includes the tie
  definitions (`workpapers.api.tie_digest`), so a tie changed after a sign-off makes it stale.
- `register_field_owner(FieldOwner("trial_balance", …))` in workpapers for the `wp_ref` and
  `area_override` field keys (`<key>:<account_code>`), read from the ledger's annotations.
- Tests: goldens (unit), `tests/integration/test_a02t17_tie_service.py`.
- Rollback: revert; no migration.

## Progress log
- 2026-10-27: plan written.
- 2026-10-27: built as planned; the golden reads Northwind from `tests/golden/ledger/tb_layers.yaml`. The C9 issue-link route moved from the stub to `assurance/tb_read_model.py`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-513 | Ties join the trial balance's signed hash; issue link set once; field owner keys | No |
