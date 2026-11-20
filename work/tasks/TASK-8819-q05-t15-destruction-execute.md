---
id: TASK-8819
title: "Q-05-T15: Approvals and execution (DestructionExecuteWorkflow, certificate, 410)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-q05t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-05-T15
---

## Objective
Felix Andersen's typed DESTROY 2026-Q3 destroys 1,204 documents (1,201 with 3 excluded in the fil02e variant), reads answer 410 citing DC-2026-Q3, and a re-render of the certificate is byte-identical.

## Done
- evidence/destruction_execute.py: approve (firm_admin + security_admin, distinct people and roles, fresh MFA, second types the phrase; Approved + workflow start), cancel, execute (DB and S3 hold re-check, observed retain-until, shared-object check, version delete primary and replica under the destruction role, registered derived-store purge, tombstone under destruction_tombstone, shrink-only exclusions, kill switch destruction_execute), certify (canonical JSON certificate in the COMPLIANCE records bucket, 7 years), register_derived_store slot, DestructionExecuteWorkflow (batch class)
- storage.delete_version + default destruction client (STS AssumeRole with the batch tag in AWS; configured client in synthetic envs; refused elsewhere); kernel destruction_s3_client; settings evidence_replica_bucket, destruction_role_arn
- DomainGone (410 destroyed) and evidence reads of a destroyed version answer it citing the certificate
- routes approvals, cancel, certificate; reviewed audit actions
- unit tests

## Progress log
- `2026-11-20` — Plan (red): approvals, workflow, storage, certificate, 410; rollback revert (no migration: 0964 has the tables). Deviation (DEC-5824): the certificate is canonical JSON in the records bucket, not a C11 PDF. Replay history and the DB walk at the end pass.
