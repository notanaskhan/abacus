---
id: TASK-1111
title: Viewer endpoints — GET /v1/evidence-versions/{v}/viewer manifest, /pages/{n} (masked rendition only), /regions?match_ids= and /search?q= over the word layer; legacy preview routes share the page source (P-03-T09)
spec: SPEC-322
acceptance_criteria: [AC-16, AC-21, AC-22, AC-24]
risk_zone: red
status: done
epic: P-03
plan_key: P-03-T09
branch: s7-p03-viewer
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The manifest carries geometry only, search returns rects only and never logs the query, and client-scope versions resolve through visible()" (P-03-T09; C4 §3.3, §3.4).

## Plan (red zone)
- **Code (evidence, protected):** `evidence/viewer.py` (new):
  - `_visible_version(ctx, version_id)`: a client principal is refused (403, INV-4); the version is read through `visible(ctx, "evidence.read", EvidenceVersion.engagement_id)` (invisible or walled: 404, no count) and then authorised on its request item with client facts (`uploads._authorised_any_version`).
  - `manifest`: geometry from `evidence_pages` (word layer) and the preview's page sizes, never text; `pii_masks` from `pii_regions` as mask tokens; `pii_scan` is `done` only for a page a `pii_scan_runs` row lists as scanned, else `not_scannable` (fail closed).
  - **Interim rule (masking not built, T13/T15):** only a preview with `mask_version` set is a masked rendition. None exists before T15, so the manifest of a rendered version reads `status=processing`, `reason=preview_outdated`, and `/pages/{n}` answers 409 `preview_outdated` (AC-24). No C4 route ever serves an unmasked PNG. The legacy upload, version and inbox page routes keep serving their existing previews until T15 switches them (they go through the same `page_png` source with `masked_only=False`); recorded as DEC-266.
  - `page_png`: the PNG with `no-store`, `nosniff`, `default-src 'none'`, after an `evidence_content.read` access event (Q-02-T20; the content is not served if logging fails).
  - `regions`: from verified citations into this version (`visible(evidence.read)` on the citation's engagement), the box parsed from the stored locator; at most 200; sheet cells as `{sheet, cell}`.
  - `search`: the masked word layer, whole words, contiguous; page rects (one per line of a hit), at most 200, `total`, `truncated`; the query is never logged or stored.
  - `models.py`: `UploadPreview.mask_version`, `derivation_id`; `PiiScanRun`.
  - `trust_contract.py`: the four viewer routes go live behind `evidence.viewer_v1`.
- **Errors:** `PreviewOutdated` (409 `preview_outdated`) registered with `error_codes --write`.
- **Tests (first):** `tests/integration/trust_kit/test_viewer.py` (manifest geometry only, processing and preview_outdated, password-protected and unreadable, 409 page, wall 404, client 403, regions from citations, search rects only with the query absent from logs, access event on a page read); unit tests for the search spans.
- **Rollback:** revert the commit; the routes return to the 501 stub.

## Progress log
- 2026-10-24: plan written.
- 2026-10-24: built. `viewer.py` serves the four routes; tests written first (`test_viewer.py`, 7). `UploadPreview` now maps 0109's `derivation_id` and `mask_version`; `PiiRegion` maps no `value_sealed`. Committed with T08.
- 2026-10-24: final checks on the branch: backend unit, contracts and security 26,387 passed (4 xfailed); integration (trust_kit, screening, access events, schema check, binder lifecycle, model foundation) 322 passed (2 xfailed); ruff, pyright, banned_patterns, validate_docs and error_codes clean; make check-fast green; apps/web vitest 1,488 tests, one SHL-01 timing test flaked under load and passes alone.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-266 | The interim rule before masking (T13, T15), and the manifest's status mapping | No (ADR-110, SPEC-322) |
