---
id: TASK-1507
title: I-01-T08 C13 and home-count registrations for the wedge
spec: SPEC-308
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: I-01
branch: s12b-i01t08
created: 2026-10-27
updated: 2026-10-27
---

## Objective
SPEC-004's review queue as `evidence_review` gates; shadow suppression confirmed; home counts `agent_runs_running`, `audits`, `binders` (DEC-647).

## Plan (red)
- No migration. `assurance/review_gates.py` (the source; assurance may read requests, evidence and review), `evidence.api.review_assignees`, `requests` system reader `awaiting_review` and `awaiting_review_count`, `review/gates.py` subscribes to `evidence.uploaded` and `review.assigned`.
- Home counts in `agents`, `assurance`, `requests` (`home_counts.py`), registered at each api's import.
- Test: `tests/integration/backfill/test_i01t08_registrations.py`.
- Rollback: revert; the projection rebuilds without the source.

## Open
- Follow-up drafts awaiting send, portal invites to resend and `portal_invites_pending` wait for their state (DEC-647).
- P-04-T17's suites seed uploads; with the new source an upload is also an `evidence_review` gate, so their counts may move in the batch pass.

## Progress log
- 2026-10-27: built; lint, pyright, import contracts clean; app and worker import. Tests run in the S12 batch pass.
