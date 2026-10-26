---
id: TASK-1335
title: EngagementExportWorkflow and the deterministic package builder (A-01-T19)
spec: SPEC-344
acceptance_criteria: [AC-9, AC-10, AC-11, AC-12, AC-13]
risk_zone: red
status: in-review
epic: A-01
plan_key: A-01-T19
branch: s10b-audit-trail-export
created: 2026-10-26
updated: 2026-10-26
---

## Objective
After the Undo window an export is built: the grant consumed, the selection snapshot at one
audit sequence, a deterministic ZIP (SPEC-344 §7), sealed in 64 MiB segments in the exports
store, and the row marked `ready` (or `failed`). Acceptance: "Northwind's export lists 24
requests and 12 files whose SHA-256 match their fingerprints, and two builds are
byte-identical."

## Plan
- **Workflow** `engagement_export` (`EngagementExportWorkflow`), id
  `engagement_export:<tenant>:<export_id>`, reuse rejected, work class `batch`, v1 (ADR-090:
  later changes behind `workflow.patched`). Started by the `engagement_export.requested`
  subscriber. Durable timer for the rest of the window (`wait_seconds` from the business clock),
  then activities: `engagement_export.consume_grant` (voided or refused → the run ends; a grant
  not yet due raises `GrantNotYetDue` and retries) → `engagement_export.snapshot` (`as_of_seq` =
  the tenant's newest audit sequence; the selected versions written to
  `engagement_export_contents`) → `engagement_export.package` (build, verify, seal, store;
  heartbeats) → `engagement_export.mark_ready`. Any failure → `engagement_export.mark_failed`
  (unlimited retries) with `integrity_mismatch`, `export_section_missing` or `build_error`.
- **Builder** (`evidence/export_builder.py`, pure): sorted entries, timestamps fixed at
  `generated_at` (the export's `not_before`, so a rebuild of the same export is byte-identical),
  `ZIP_DEFLATED` level 9, `create_system = 3`, 0644, no extra fields; `index.xlsx` rendered from
  the index CSV's rows with ADR-042's writer (`render._normalised`); `checksums.sha256` and
  `manifest.sha256` in `sha256sum` format; `manifest.json` canonical, validated by
  `EngagementExportManifest` before anything is written.
- **Selection** (`evidence/export_selection.py`): as the requester (`member_context`), the
  scope's binders' requests through `requests.api.source_documents` (`visible_items`), each
  request's live versions through `item_versions_with_decisions` (withdrawn and voided excluded);
  accepted only, plus needs-review with `include_unaccepted`. Paths
  `evidence/NN Category/NN Request/vN__file`: each segment NFC, separators and control or format
  characters replaced, `.`/`..` replaced, TIN forms masked (`kernel.tin_patterns.scrub_tins`,
  which uses `kernel.classification.mask`), trimmed to 180 characters, de-duplicated `~2`, `~3`;
  `archive_path_problem` must pass.
- **Sections:** evidence registers the four core sections it can read (`index`, `fulfilments`,
  `review_decisions`, `citations`; requests may not import evidence, so its rows come through
  evidence's own reads of `requests.api`); agents registers `screening`. Every cell is a literal
  string, formula leads neutralised with a leading apostrophe in CSV and `quotePrefix` in XLSX,
  TIN forms masked. A core section with no provider fails `export_section_missing`.
- **Audit trail:** `audit_trail/events.jsonl` through a slot evidence owns
  (`register_export_audit_trail`), because audit_trail may import only identity, engagements
  and platform; the composition root registers `audit_trail.api.events_for_work_item`. Each
  line: seq, effective_at, action, actor grammar (kind and ids), target type and id. No reader
  registered while the scope asks for the trail: `export_section_missing`.
- **Integrity:** every evidence file is read through `evidence.storage.get` (which verifies) and
  its SHA-256 compared again with the `evidence_versions` fingerprint; a mismatch fails
  `integrity_mismatch` and nothing is stored.
- **Store** (`evidence/export_storage.py`): `exports/<tenant>/<export_id>/segment-NNNN`, each
  64 MiB segment sealed with a fresh data key under the tenant key (`kernel.crypto.seal`, bound
  to export and segment), no Object Lock; bucket from the new `exports_bucket` setting (unset:
  fails closed).

## Files
- `backend/src/abacus/modules/evidence/{export_builder,export_selection,export_sections,
  export_storage,export_activities}.py` (new); `workflows.py`, `workflow_types.py` (append)
- `backend/src/abacus/modules/agents/export_screening.py` (new), `agents/api.py` (append)
- `backend/src/abacus/kernel/config.py` (`exports_bucket`)
- `backend/src/abacus_tools/workflows/record_engagement_export.py` (new)
- `backend/tests/workflows/test_engagement_export_replay.py`,
  `backend/tests/workflows/histories/engagement-export-v1-*.json` (recorded)
- `backend/tests/unit/evidence/test_export_builder.py` (AC-10, AC-11, AC-13 offline)
- `backend/tests/integration/test_a01t19_engagement_export_package.py` (AC-9, AC-10, AC-12,
  AC-13 against Postgres and S3)

## Rollback
Flag off. The workflow is v1; a stuck run is terminated and its export marked failed by an
operator. Segments live in a bucket with a lifecycle rule (Q-01), not locked.

## Progress log
- 2026-10-26: plan written; built after TASK-1334 in the s10b worktree.
