---
id: TASK-7318
title: "S37 end pass: gates, tests, security review, fixes, restack"
spec: SPEC-000  # sprint record
acceptance_criteria: [AC-1]  # gates green, targeted suites run, one review round, PRs restacked
risk_zone: green
status: in-review
branch: s37-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
---

## Objective
One end pass over the S37 PRs (#1709 to #1732): gates, targeted tests, one security review of the
red diffs, one fix round, at most one re-review, then restack on main and merge one commit per PR.

## Gates and fixes
- `validate_docs`: task files' acceptance ids now name the specs' section ids (`AC-<n>`, as the
  validator reads them).
- `banned_patterns`: OWN-001 (capability availability read `engagements`; now
  `engagements.api.engagement_metadata` and agents' own `engagement_agents`), BOUND-002 (tax may
  not import workbench: TAX-08 sessions are `POST/GET /v1/workbench/sessions` with `subject_ref`,
  and tax registers its resolver in `agents.api.register_session_subject`), SQL-001 (K-1 queries
  are whole constants), DISPATCH-001 (the session's child run starts through
  `kernel.dispatch` in the `workbench.session.start_child` activity, not `start_child_workflow`),
  BOUND-001 (the recorder imports `workbench.api`), TENANT-001 (a test literal), TYPE-001 reasons.
- `error_codes --write`: `capability_unavailable`, `session_locked`, `reason_required`,
  `stale_version`, `level_not_permitted`.
- pyright clean over every changed file; import-linter 8 contracts kept.
- OpenAPI and the client regenerated on the restacked tree; the workbench subject model is
  `SessionSubjectRefIn` (organisations owns `SubjectRefIn`).
- Migration 0820 re-chained onto main's 0814 (S35 follow-ups, #1714); head 0821.

## Security review (inline, red diffs)
- **Fixed:** DEC-87 lock in sessions would have locked an owner (or teammate) who reads the
  session's engagement but holds no firm-level `client.read`: the engagement's own client now
  counts as opened through the engagement; any other client in `client_scope` still needs
  `client.read`, and a wall on any client omits the session.
- **Accepted (low):** a turn's run is opened before the person's item; a failed item insert leaves
  one queued run with no session item (no model call, no write).
- **Accepted (low):** a session message body is stored as written (Restricted, never logged); the
  session items table has no sealed column (P-10-T04's schema).
- **Fixed (functional, DEC-4317):** a write-proposing turn's child run carried its steps with no
  arguments, and a propose step declared `proposal.create` with a person as approver, which no
  person holds, so `validate_plan` would refuse it. Plan steps now carry the model's arguments
  validated against each tool's input model (refused before any child run otherwise); only an
  approved_write step names an approver. The existing executor runs the approved steps through C17.

## Progress log
- `2026-11-12` — Gates and review done; tests run once the shared test lock is free.
