---
id: TASK-2519
title: N-02-T38 Evidence package hardening and retention
spec: SPEC-381  # N-02 §3.3, §3.13
acceptance_criteria: [AC-17]  # and N-02 §3.3, §3.13
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T38
branch: s20b-n02-t38
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Evidence package hardening and retention: legible reproduction (evidence page appended through
C11), nightly hash re-verification of records objects with an alarm, retention record types for
e-file authorizations (due date + 3 years, extended at the IRS received date), 7216 consents
(signature + 3 years) and letters (firm policy), extend_retention wired to T-01
acknowledgements, Download evidence bundling certificate and manifest.

Acceptance (backlog row): "A tampered records object fails the nightly check with an alarm, and
an 8879 package's retain-until only ever moves forward."

## Plan (red)
- `signatures/integrity.py`: purpose retention type (`consent_evidence` for §7216, else
  `signature_evidence`, never unlocked), the legible page (C11's renderer, isolated child, from
  stored evidence; a missing renderer records `envelope.legible_copy_failed` and never blocks),
  the nightly sweep (re-hash every named record; `envelope.integrity_failed` once; error log;
  `signatures_evidence_integrity_failures` counter for the alarm).
- `signatures/workflows.py` `EvidenceIntegrityWorkflow` + daily `PlatformSchedule`;
  `signatures/api.py` registers activity, workflow, schedule.
- `signatures/activities.py` `envelope_complete`: the purpose's retention; the page stored and
  listed in every signer's documents (so the manifest and Download evidence carry it).
- `tax/engine_files.py`: an accepted federal acknowledgement extends the 8879 to the IRS received
  date + 3 years through C7's `extend_retention` (forward only).
- `banned_patterns.MODULE_DEPENDENCIES`: signatures may import reporting (reporting never imports
  signatures).
- Download evidence already zips packages, documents (now the page) and the certificate with
  `manifest.sha256` (N-02-T13).
- Rollback: revert; no migration.

## Not done (open)
- The alarm rule on `signatures_evidence_integrity_failures` lives in Terraform (Q-03's
  monitoring module); the counter and the error log are what it watches.
- The drawer's "Evidence integrity check failed" line reads the `envelope.integrity_failed`
  event in the trail; a dedicated SIG-01 field waits for the frontend row.
- An e-file authorization's floor at completion is the firm's signature-evidence policy (at
  least 3 years from signing); "return due date + 3 years" is met by the extension at the
  received date, which is never earlier than the due date's for a timely return.

## Decisions
DEC-1567.

## Progress log
- `2026-10-31` — Built on `s20b-n02-t38` off main 7d4def8e5. test_n02t38 plus the N-02-T12,
  T13, T14 and T25 suites: 61 passed.
