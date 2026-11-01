---
id: TASK-2513
title: P-11-T11 Reporting routes live (generated-document read, fields, compare, changes, regenerate; SAMPLE preview)
spec: SPEC-520  # AC-14, AC-17 to AC-19, AC-22, AC-23, AC-26; C11 v1
acceptance_criteria: [AC-14, AC-17, AC-18, AC-19, AC-22, AC-23, AC-26]
risk_zone: amber
status: done
epic: P-11
plan_key: P-11-T11
branch: s20b-p11-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Reporting routes live: generated-document read and versions, field-region manifest, compare to
standard or to another version (deterministic word diff), changes since snapshot, human-only
regenerate with Idempotency-Key; template list, version and SAMPLE preview; visible and walls on
the P-36 envelope.

Acceptance (backlog row): "A walled user gets 404 with no count, a client principal gets 403 on
every reporting route, and regenerate from an agent or worker context is refused."

## Plan (amber)
- **Gap found:** P-11-T08 sealed only the snapshot's hash, and DEC-1457 left the render workflow
  "for P-11-T11". The letter kind's provider answers only inside its consumer's call (DEC-1458),
  so the job cannot re-resolve values later. So: migration **0522**
  `generated_document_snapshots` (insert-only, `reporting_rows_immutable`, forced RLS) written
  with every version in the consumer's unit of work.
- `reporting/render_job.py`: the job on `generated_document.render_requested` (relay
  subscription): snapshot + template parts → `compose.py` → isolated PDF with field regions
  (`render/regions.py`, text-search fallback of P-11 §4.4) and DOCX when the kind asks →
  `evidence.api.store_generated` → `files.record_file` + `generated_document_fields`; refusal
  fails the job with its code, a `render_failed` event and audit.
- `reporting/reads.py` + `contract.py`: the six routes live (no 501); client 404, flag 404, the
  document under RLS 404, then the one action on the document's engagement or client; a wall is
  404; regenerate refuses any non-human context, runs under `idempotent`, 409 `document_locked`.
- `reporting/api.py` `regenerate(tx, …)`; methodology `TemplateParts` gains `template_id` and
  `sample_data` (additive).
- Registry, tenant-isolation list, C11 doc §5 (`render_failed`), C11 stub test (every route
  live), `make generate`.
- Rollback: the routes keep the flag (`reporting.generated_documents`); 0522 is expand-only.

## Decisions
DEC-1561 (as built; the client answer stays 404 per the frozen C11 order, not the row's 403).

## Progress log
- `2026-10-31` — Built on `s20b-p11-t11` off main 7d4def8e5. Targeted tests: C11 contracts,
  test_p11t11 (9), P-11-T08/T09, N-02-T32, unit reporting: 178 passed. Full gates at the S20b
  end review.
