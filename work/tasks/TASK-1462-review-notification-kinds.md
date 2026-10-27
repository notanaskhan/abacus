---
id: TASK-1462
title: The seven review-grammar notification kinds (P-04-T26)
spec: SPEC-360
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
epic: P-04
plan_key: P-04-T26
branch: s12-review
created: 2026-10-27
updated: 2026-10-27
---

## Objective
`decision_assigned`, `sign_off_requested`, `sign_off_stale`, `proposal_routed`,
`review_note_raised`, `issue_assigned` and `import_pending_approval` in
`notifications/catalogue.py`, in the Approvals category with read-time facts; undotted codes
that pass the widened kind CHECK (0090); email template keys only. Acceptance: "Each kind fans
out once per recipient with walls re-checked, and no template text is committed."

## Plan
- Register the four missing kinds (`sign_off_requested`, `proposal_routed`, `issue_assigned`,
  `import_pending_approval`) as `approval`; map their events (`sign_off.requested`,
  `proposal.routed`, `issue.assigned`, `checkpoint.import_pending`) in `CATALOGUE` with
  in-app sentences; the producers of the last three events land with their services
  (P-04-T30, T32, T48), and fan-out is ready for them.
- Read-time facts and pending: a subject-state slot in `notifications/kinds.py`
  (`register_subject_state(subject_type, resolver)`, exported from `notifications.api`); the
  seven kinds resolve facts and pending through the subject's owner (review registers
  `decision_card`, `sign_off`, `reviewable_note`; agents registers `proposal`). Fail closed: no
  owner, no facts and never pending.
- A person's route is not the agent's: `proposal_routed` rows read as the person when the event
  names one (DEC-605).
- Tests: the catalogue unit test lists the new events; an integration test fans each kind out
  once per recipient and drops a walled one.
- **Rollback**: revert.

## Progress log
- 2026-10-27: planned.
