---
id: TASK-2018
title: N-01-T12 AttachmentTriage workflow
spec: SPEC-380
acceptance_criteria: [AC-25]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T12
branch: s15n-n01-t12
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Intake attachments go through extraction, the word layer, the PII scan and masked previews
(evidence's upload steps, kind `intake`), then New to Waiting when matched (DEC-1058).

Acceptance (backlog row): "A 1095-C intake object gets masked page previews and the committed
replay history passes."

## Plan (red)
- Migration 0370 (expand-only): `inbox_attachment_id` on five derived tables; optional
  `engagement_id` on extractions and previews; one-subject CHECKs; indexes.
- evidence: `intake_sources.py` (resolver slot, `source_of`, `target_type`); repository subject
  predicates take `inbox_attachment_id`; the four step activities handle `intake`; models.
- communications: `triage_workflow.py` (`AttachmentTriage`), `triage.py` (resolver, start on
  `inbox_attachment.received`, `attachment_triaged`); registered in `api.py`.
- `abacus_tools/workflows/record_attachment_triage.py` (histories at the end review).
- Rollback: revert the branch; 0370's downgrade refuses while intake rows exist.

## Tests
Build-only (Ayush, 2026-10-29): no tests written or run in this pass; the acceptance test, the
replay test and recorded histories land at the end review.

## Progress log
- 2026-10-29: built (S15 group B, build-only). ruff, pyright, lint-imports, banned_patterns clean.
