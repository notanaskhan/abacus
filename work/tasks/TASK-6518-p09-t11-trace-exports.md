---
id: TASK-6518
title: "P-09-T11 finish: trace exports with a signed manifest and the run record's hash"
spec: SPEC-648
acceptance_criteria: [AC-3]
risk_zone: red
status: in-review
branch: s33-p09-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-09-T11
---

## Objective
Two exports of the same trace version are byte-identical, the audit event names the person and the
sha256, and a stale MFA answers mfa_required. Finishes TASK-461/TASK-901's route.

## Plan (red)
1. `agents/runs.py` `export_trace`: the manifest adds `run_record_sha256` (the persisted record's
   hash, else the run's own fingerprint) and `exported_by`, and is signed with the export signer
   (`kernel.crypto.signing`; KMS in AWS, local in tests; unavailable → 503, never unsigned); the
   audit event `agent_run.trace_exported` names the person.
2. `runs_routes.py` `TraceExportOut`: `run_record_sha256`, `signature`, `signature_key_id`.
3. Fresh MFA is the matrix's `mfa_recent` on `run_trace.export` (TASK-901): 403 with
   `facts.reason = mfa_required` (DEC-547), the shell's step-up.
Rollback: revert.

## Progress log
- `2026-11-09` — Built; unit test written, not run (end pass). Partial: the PDF format through C11's
  `run_trace_export` kind (registered by no module yet; layout and template are P-11's) stays
  out; `format` accepts `json` only.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3118 | The signed manifest's fields; fail closed without a signer | no |
