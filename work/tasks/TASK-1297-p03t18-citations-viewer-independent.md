---
id: TASK-1297
title: Independent AC tests (ADR-078) for citations v2, the viewer, masked renditions and the logged reveal
spec: SPEC-322
acceptance_criteria: [AC-1, AC-2, AC-4, AC-5, AC-10, AC-16, AC-21, AC-22, AC-23, AC-24, AC-25, AC-26, AC-27, AC-28, AC-29, AC-30, AC-36, AC-37]
risk_zone: red
status: in-review
epic: P-03
plan_key: P-03-T18
branch: s9c-viewer-tests-docs
test_author: ayushkbhatia
test_session: 2026-10-26, branch s9c-viewer-tests-docs (S9 wave C), a session separate from the P-03 implementation sessions
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Prove, from SPEC-322, the C4 contract (`docs/contracts/c04-citations-viewer.md`), the evidence
matrix rows and DEC-369 / DEC-370 only, that every C4 read and the relink action keep INV-1
(human-only actions), INV-2 (citations resolve to a verified source) and INV-3 (walls and other
firms read as not found, with no count). Cover the PII-era behaviour now on main: masked
renditions for onshore readers, the offshore masked-text view and its refusals, and the logged
reveal.

## Plan
- **One file:** `backend/tests/integration/backfill/test_p03t18_citations_viewer_independent.py`,
  black-box over `create_app()` on the migrated testcontainer Postgres and the compose S3 image,
  using the back-fill `Seeder` / `Net` helpers. Uploads go through the client upload route; the
  rendition steps run through the processing activities a v7 run calls (words, PII scan, masked
  preview). Citations are written through `evidence.api.record_citations` as a person (the public
  writer), or seeded as the superuser when the row needs an agent run. The moved detector is
  driven by delivering the outbox `evidence_version.created` event to `evidence.api.on_version_created`.
- **Cast:** Samuel (onshore staff), Remy (offshore manager), Lena (staff, walled from the
  Ashford client), Rhea (reviewer: reads citations, may not reveal), Cora (`client_service`),
  the client's admin, and an outsider from a second firm.
- **Expectations** are literals typed from SPEC-322 §5, C4 §2 to §7 and DEC-369 / DEC-370; no
  module constant or scenario value is imported to decide an expectation.
- **No migrations, no generated sources, no matrix or flag edits.**
- **Defects:** fix if small and inside `evidence` (ED row + this test); otherwise a strict xfail
  citing TASK-1297 (DEC-399) and an open ED row.
- **Rollback:** delete the test file; nothing else changes.

## Spec drift followed (later decisions over the spec's words)
- AC-27 says "a TIN kind"; DEC-370 makes `mfa_recent` apply to every kind. The tests follow DEC-370.
- AC-28 / C4 §6 list `facts.reason: offshore | role`; DEC-370 answers the plain
  `{"detail": "forbidden"}` for every refusal but `mfa_required`. The tests follow DEC-370.
- C4 §3.3 `view` and §3.4 `TextOut` (DEC-369): an offshore reader gets `view: text`, the masked
  text projection, and a 403 on every page image. The tests follow DEC-369.

## Not covered here (and why)
- AC-31 to AC-35 (unlock): P-03-T19 is not this row's dependency; P-03-T21 covers the reveal
  matrix again with the unlock.
- Word-layer replay of workflow histories (v1 to v7) is the workflow replay suite's
  (`backend/tests/workflows/`); this suite proves activity-level idempotence instead (a second
  run of words, scan and masked preview writes no second row).
- The agent-context and outside-a-request layers of AC-37: an agent context is built only from a
  proven run (SYS-001), which the HTTP boundary cannot make. The suite proves the matrix layer
  (a client and a reviewer are refused) and the database CHECK; `serving_request()` stays with the
  implementer's tests.

## Results (per AC; all pass, no xfail)
- AC-1: `test_ac1_a_verified_document_citation_stores_a_hash_and_never_the_quote`, `test_ac1_an_agent_citation_reads_as_the_person_via_agent`.
- AC-2: `test_ac2_an_unsupported_claim_is_stored_unverified_with_its_reason` (page_not_found, quote_not_found, bbox_mismatch). `value_mismatch` needs a sheet source and is left to P-03-T21's corpus.
- AC-3: `test_ac3_a_quote_without_a_bbox_is_verified_on_the_page_text`.
- AC-4: `test_ac4_the_database_rejects_any_change_to_citation_rows_for_every_role` (UPDATE, DELETE, TRUNCATE × citations, citation_events; superuser by trigger, app role by grant).
- AC-5: `test_ac5_lena_walled_from_ashford_gets_not_found_and_no_count`, `test_ac5_a_client_principal_is_refused_every_citation_route`, `test_ac5_client_service_never_reads_citations`, `test_ac5_the_reviewer_reads_citations`.
- AC-6, AC-7 (server half): `test_ac6_the_display_carries_the_contract_fields_and_no_stored_hash`, `test_ac6_a_quote_is_reread_from_the_masked_layer`, `test_ac7_the_anchor_stack_lists_the_citations_in_order`.
- AC-10: `test_ac10_a_superseded_source_reads_moved_and_offers_relink`. Broken (a withdrawn source) is not covered here.
- AC-13, AC-16, AC-21, AC-22: manifest, regions by match id, processing, search (rects only, masked layer, query not in the product's logs), Lena on every viewer route, another firm on citation, viewer, page, text and reveal.
- AC-23 to AC-30: sealed SSN region, opaque burned regions on the served PNG (pixel check), no unmasked rendition stored, legacy preview JSON masked, 409 `preview_outdated` for a pre-masking preview, offshore text view and 403 on images, `not_scannable` page refused offshore with `unread` text, the reveal (201, `no-store`, `Pragma`, row, audit, access event, no outbox), EIN format, MFA step-up, refusals for offshore, reviewer, client and client_service, a region of another version, database refusal of machine and anonymous reveals, the 21st reveal throttled and audited.
- AC-36, AC-37: relink onto the successor, `not_moved`, `relink_unverified`, role refusals and the wall first, the database CHECK on `relinked` by a system actor.
- AC-41: every route family absent with its flag off.
- Activity-level replay: a second run of words, scan and masked preview writes no row.
- Defects found: none. Two assertions of mine were over-strict and were corrected without
  weakening the promise: the page's `Cache-Control` is `private, no-store` (the contract's
  `no-store` is a directive of it), and the search-logging check now reads the product's loggers
  only (the test's own HTTP client logs its request line).
- `docs/quality/backfill.md` is the Q-03 back-fill ledger of old TASKs; P-03-T18 is an epic row,
  so it has no line there.

## Progress log
- 2026-10-26: plan written; suite written from the spec and the contract.
- 2026-10-26: one targeted run: 50 tests, 48 passed and 2 failed on my over-strict assertions
  (above); after the fix the two and the 7 tests touched by the lint fixes pass. Gates: ruff
  format/check, pyright (0 errors), lint-imports (5 kept), banned_patterns, error_codes,
  validate_docs, scope_guards, fresh_mfa, secrets_scan clean. ED-087 not used.
