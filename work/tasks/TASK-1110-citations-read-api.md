---
id: TASK-1110
title: Citations read API — GET /v1/citations/{id} display contract and GET /v1/citations (anchor stack, host section, source version, kind) on the P-36 envelope with visible() and used_in (P-03-T08)
spec: SPEC-322
acceptance_criteria: [AC-5, AC-12]
risk_zone: red
status: done
epic: P-03
plan_key: P-03-T08
branch: s7-p03-viewer
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"A walled or client principal gets 404 or 403, an unverified citation is never returned as verified, and no quote text is stored in the database" (P-03-T08; ADR-166; C4 §3.2).

## Plan (red zone)
- **Code (evidence, protected):**
  - `evidence/citations/display.py` (new): `citation_display(ctx, id)` and `citation_list(ctx, filters, cursor, limit)`. A client principal is refused (403, `role`) before any read. The single read loads the row by id under RLS, then `get_ref` + `authorise(citation.read)` on its engagement (a wall answers 404, a role 403); a row with no engagement answers 404 (firm-level anchors take visibility from their anchor provider, none registered before P-04). The list filters through `visible(ctx, "citation.read", Citation.engagement_id)` with keyset paging (`n` for an anchor stack, else `created_at`) and the P-36 envelope.
  - Display per row: `title`/`loc` from the kind's registered display function (a kind with none renders its kind name by code); `quote` re-read from the word layer inside the stored box and hash-checked against `quote_sha256` (`shown`; `changed` when no run of the box's words hashes to it, which also reports the row unverified with `quote_not_found`; `withheld` when the layer can't be read or the citation has no box), then rendered from the masked projection (`evidence/masking.py`, words inside a `pii_regions` box become their mask token); `state` computed from `citation_events` (`relinked` if relinked, else the latest of moved/broken, else `valid`); `moved` from the latest moved event; `created_by` "‹person› via Agent" / person / "Accrued"; `used_in` the number of distinct anchors, visible to the reader, citing the same `match_id`; `allowed_actions` `citation.relink` only on a moved citation the reader may relink.
  - `citations/registry.py`: a display function takes the reader's session (`AsyncSession`), not a unit of work (a read opens none).
  - `citations/matching.py`: `reread_span(words, box, sha256)` (pure).
  - `evidence/masking.py` (new): mask tokens per kind (P-03 §4.4) and `masked_text(words, regions)`.
  - `evidence/models.py`: `CitationEvent`, `PiiRegion` (read models over 0109's tables).
  - `trust_contract.py`: the two GET routes go live behind `evidence.citations_v2` (relink and create stay 501). `host_ref` is `<anchor_type>:<anchor_id>`; `section_id` matches `cited_from_locator.section_id`.
- **Registry and flags:** none new; the flag description says the reads are served.
- **Migrations:** none.
- **Tests (first):** `tests/integration/trust_kit/test_citation_reads.py` (AC-5 wall 404 and stack omission with no count, client principal 403, AC-12 unverified never verified, changed quote, re-read quote shown and masked, used_in, state from events, no quote column); `tests/unit/evidence/test_citation_matching.py` gains `reread_span` and masking cases.
- **Rollback:** revert the commit; the routes return to the 501 stub.

## Progress log
- 2026-10-24: plan written.
- 2026-10-24: built. `citations/display.py` serves both reads; tests written first (`test_citation_reads.py`, 11; `tests/unit/evidence/test_citation_display.py`, 8, shared with T09). A two-line quote's stored box also covers words that aren't the quote, so re-reading takes the run from the box's top edge to its bottom edge whose hash matches, not every word in the box. Committed together with T09 (they share `trust_contract.py` and `repository.py`).
- 2026-10-24: final checks on the branch: backend unit, contracts and security 26,387 passed (4 xfailed); integration (trust_kit, screening, access events, schema check, binder lifecycle, model foundation) 322 passed (2 xfailed); ruff, pyright, banned_patterns, validate_docs and error_codes clean; make check-fast green; apps/web vitest 1,488 tests, one SHL-01 timing test flaked under load and passes alone.
- 2026-10-24 (security review): (1) quotes and search failed open on pages no PII scan covers; one check (`evidence/projection.py`) now serves the manifest, search and the quote re-read: an unscanned page is never searched (409 `preview_outdated` with no scanned text page) and its quote is `withheld`. (2) a shown quote and a search now write an `evidence_content.read` access event first (never the query). (3) a title names a file only for a verified citation whose source is in its engagement (the display function takes the engagement). (4) search needs 3 characters and reads at most 50 pages and counts 1,000 hits a call. Six failing tests written first; existing tests that read quotes or search now seed a scan run. DEC-266 updated.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-265 | The display rules C4 §3.2 leaves open (host_ref grammar, quote_state rules, changed ⇒ unverified, used_in, labels, firm-level rows) | No (ADR-166, C4) |
