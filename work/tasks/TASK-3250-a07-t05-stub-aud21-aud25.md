---
id: TASK-3250
title: A-07-T05 contract stub part 2 (AUD-21 to AUD-25 letters, report, release, filings, archive)
spec: SPEC-644
acceptance_criteria: [AC-5]
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T05
branch: s27-a07-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Every AUD-21 to AUD-25 operation is in the generated client returning 501, and the contract doc
lists report.release, archive.lock and archive_addition.approve as human-only with fresh MFA."

## Plan (red)
- `assurance/release_contract.py`: classified models and 37 routes under
  `/v1/audits/{work_item_id}` (representation letter, governance communications and recipients,
  report and versions, diff and reason codes, release, filings, archive, manifest, additions,
  verify); same gate as T04, then 501.
- Matrix (`assurance.yaml`): 21 new actions; final verbs deny agent, system and clients; the new
  approvals (`rep_letter.approve`, `governance_comm.approve_send`, `archive_addition.approve`)
  carry `mfa_recent` and join `fresh-mfa-actions.yaml`; `archived_exempt` declared in comments
  for A-07-T14's codegen.
- Contract doc: the operations table, human-only actions with their audit events and refusals.
- `make regenerate`; schema set diffed: five names clashed (`ArchiveOut`, `ReleaseOut`,
  `ReasonCodeOut`, `RepresentationOut`, `SignerOut`) and two more on the first rename, so the
  models are `AuditArchiveStateOut`, `AuditReleaseOut`, `ReportReasonCodeOut`,
  `LetterRepresentationOut`, `RepLetterSignerOut`; none removed or renamed in the end.
- Tests: `tests/unit/assurance/test_a07t05_stub.py`.
- Rollback: revert and regenerate.

## Progress log
- 2026-11-04: built. Tests at the S27 end review.

## Decisions made during this task
DEC-2231.
