---
id: TASK-6508
title: "A-07-T31: archive service and checklist — open on report.released, nine live items, binder index A–H, Request lock…"
spec: SPEC-644
acceptance_criteria: [AC-1]  # the row's acceptance (F7)
risk_zone: red
status: in-review
branch: s33-a07-t31
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: A-07-T31
---

## Objective
On Thu Oct 22, 2026 Northwind reads Archive in 47 days, 8 of 9 with one named open item, and a
binder index of 26 workpapers and 24 source documents.

## Plan (red)
1. `evidence/archive.py` (new, PROTECTED): `open_archive` (one v2 row per work item, Assembling,
   retention = max(P-14 `audit_documentation` policy, release + 5 years)), `record_binder_index`
   (insert-only versions, code-built), `latest_binder_index`, `source_document_count`;
   `audit_documentation` joins `RECORD_TYPES` (years are content).
2. `assurance/archive_gate.py`: nine items computed live (sign-offs, notes, stale versions, the
   binder index current, final report and deliverables, every governance letter sent or
   acknowledged, team independence, ended run logs, EBP's EFAST2 filing or not applicable);
   `binder_sections` (AUD-02 rail rows by band, EBP test papers under C; F evidence items with
   superseded versions; G run logs; H confirmations); `request_lock` (9 of 9, emits
   `archive.lock_requested`); `report.released` → `open_archive`.
3. `agents/run_logs.py`: `run_log_count`.
4. Routes: `GET …/archive`, `POST …/archive/binder-index`, `POST …/archive/request-lock` live behind
   `audits.archive`.
Rollback: revert; no migration (0669 has the tables).

## Progress log
- `2026-11-09` — Built; unit tests written, not run (end pass). Partial: the 26/24 Northwind golden
  needs the A-07-T41 completion scenario (S34) to seed the file; ArchiveReadinessWorkflow's
  fingerprint re-verification and #4302 narration come with A-07-T32; seal and additions T37/T42.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3108 | The binder's section mapping, the nine items' rules and the retention floor | no |
