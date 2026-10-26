---
id: TASK-1254
title: Masked renditions and masked agent material (P-03-T15)
spec: SPEC-322
acceptance_criteria: [AC-24, AC-25, AC-30, AC-40]
risk_zone: red
status: in-review
epic: P-03
plan_key: P-03-T15
branch: s9a-pii-masking
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"No served page has unmasked pixels inside a detected region, no agent input contains an
unmasked TIN pattern, and agent quotes of masked text still verify."

## Plan (red zone)
- **Burn (`evidence/previews.py`):** `render_masked(content, media_type, masks, sizes)` renders
  as `render` does, then on each page paints every detected box (page points scaled by the
  image over the word layer's page size, padded 2 px, rounded outward) opaque in the page's
  background colour (the most common colour of the image's border), on an RGB image with no
  alpha. It runs in the isolated child (`render_masked_isolated`, `kernel.isolation`); the
  unmasked bitmap never leaves the child. Pillow and pypdfium2 only (allowlisted).
- **Step (`evidence/masked_previews.py`):** `masked_preview_upload` is the activity
  `upload.masked_preview`. Idempotent on (source, `MASKED_RENDERER_VERSION` "v2",
  `MASK_VERSION` "m1"). Writes one `upload_previews` row with `mask_version` set, plus its page
  PNGs, in one system unit of work, audited `upload.masked_previewed`. It skips a withdrawn
  version (DEC-298) and an active-content PDF (DEC-296). Fail closed: a PDF rendition with pages
  but no PII scan run by `DETECTOR_VERSION` is never stored (`unscanned`). An image, a table or a
  `none` result is stored with no boxes; its pages read `not_scannable`.
- **Workflow:** `UploadProcessing` v7 `workflow.patched("masked_preview")` after `pii_scan`. It
  never fails the run. New runs skip the unmasked `upload.preview`: the v3 step becomes
  `patched("previews") and not patched("masked_preview")`, so v1 to v6 replay unchanged.
  `TrustLayerBackfill` v2 `patched("masks")`: batches come from `trust_layer.pending_masks`
  (sources with an extraction and no masked rendition), and each runs `upload.words`, then
  `upload.pii_scan`, then `upload.masked_preview`, all idempotent. Histories:
  `upload-processing-v7-masked-preview.json`, `-v7-masked-preview-failed.json` and
  `trust-layer-backfill-v2-masks.json`.
- **Serving:** the viewer and the legacy page routes (`…/uploads/{v}/preview/pages/{n}`,
  `…/evidence-versions/{v}/preview/pages/{n}`, `…/inbox/{f}/preview/pages/{n}`) serve only a
  masked rendition. They answer 409 `preview_outdated` while only a pre-masking preview exists.
  Legacy preview JSON comes from the masked row when there is one: `page_lines` hold masked words
  and are kept only for scanned pages, and sheets carry mask tokens. On the viewer an offshore
  reader is refused a `not_scannable` page (AC-30).
- **Agent material:** `review_material` and `match_material` always build from the masked
  projection (the offshore-only `masked` switch is removed). A PDF needs its scan, else there is
  no material (fail closed). Sheets go cell by cell through `pii.masked_rows`: label-anchored
  cells (a label to the left in the row, or the nearest labelled header above), valid unlabelled
  TINs and ABA routing numbers become tokens. `kernel.tin_patterns.scrub_tins` runs as a backstop
  on every page text and cell.
- **Verifier:** `verify_document_text` reads a scanned page's masked words through `projection`,
  so a quote copied from masked text verifies and a quote of the clear value does not.
  `verify_sheet_cell` reads masked sheets. Pages that no scan covers verify as before (DEC-369).
- **Tests first:** `tests/unit/evidence/test_masked_render.py` (pixel inspection: every pixel
  inside each padded region is one opaque colour, and the unmasked render differs there);
  `tests/unit/evidence/test_sheet_masking.py`;
  `tests/integration/trust_kit/test_masked_renditions.py` (AC-24, AC-25, AC-30, AC-40, backfill);
  replay tests.
- **Rollback:** revert. The patch markers stay as no-op branches if reverted after deploy
  (ADR-090). No migration (0109 already has `mask_version`).

## Progress log
- 2026-10-26: plan written.
- 2026-10-26: built as planned, with these additions:
  - Agent material now waits for the scan. So `check_upload` emits `upload_checks.recorded`
    only when material can be built, and the first scan of a document with page text
    re-announces it: `upload_checks.recorded`, or `inbox_file.extracted` for a firm file. It does
    so only in a live v7 run, never in the backfill.
  - The citation display and the moved detector re-read quotes on masked words first.
  - The TASK-1207 control in `test_offshore_agent_material.py` asserted clear text onshore.
    AC-25 supersedes it, and the test now asserts masked onshore too (stronger).
  - Three backfill-suite helpers (`preview_upload` in `test_client_uploads_and_processing.py`,
    `test_p06t18_detached_keys.py` and `test_offshore_evidence_reads.py`) now run the v7
    rendition steps, because their page routes serve masked renditions only. Assertions are
    unchanged.
  - `test_r01t09_v6_sorts_a_drop_last...` slices `ALL[:7]` (v1 to v5) rather than `ALL[:-1]`,
    which keeps its meaning now that v7 histories exist.
- Tests: 5 pixel unit, 8 integration (`test_masked_renditions.py`) and 30 replay tests.
  Targeted regression: trust_kit, c04 contract, replay and evidence unit, 484 passed. Agents,
  evidence, tools, contracts and workflows unit, 5,393 passed. Affected backfill and agent
  integration files, all passed. Security plus api/identity unit, 18,190 passed; the only failure
  was the OpenAPI snapshot before `make generate`, which then passed.
- Histories recorded with the repo recorders on throwaway containers:
  `upload-processing-v7-masked-preview{,-failed}.json`, `trust-layer-backfill-v2-done.json`.
- Not run: Playwright, and the full suite (shared machine).
- 2026-10-26 (security review fix round, all recorded in DEC-369):
  - **H1:** the word layer `w2` is in render space (`pdf_layout.RenderSpace`). It is read from
    an unrotated copy; detection runs upright (`pii.detect_on_page`, detector `d2`).
    Projection, viewer and masker read `d2` only.
  - **H2:** annotations are flattened before both extraction and render, and the render skips
    annotations. A page is not_scannable when its words can't be reconciled with PDFium's text,
    when it has sideways or mirrored text, when images cover 25% or more, or when it draws 40 or
    more Bézier segments.
  - **L2:** a page past the word cap is not_scannable.
  - **M1:** no sheets for portal drops or offshore initiators.
  - **L1:** the explicit flag `UploadInput.announce`.
  - Legacy `page_lines` are masked by text and dropped on rotated pages.
  - The reviewer's two scripts, run unchanged, still print their old numbers, because each
    bypasses the word layer: `geom.py` feeds raw pdfplumber boxes, and `annot2.py` passes no
    masks. Through the pipeline (layer, then detector, then masked render), every geometry case
    leaves 0 dark pixels and the FreeText widget leaves 0. `annot2.py` now shows the SSN in the
    word layer.
  - Tests: `test_pdf_layout.py` (19), 3 new and 1 parametrised integration tests in
    `test_masked_renditions.py`, and the Retry-After route test.
  - `test_words.py::test_p03t05_words_past_the_page_cap_are_left_out` now asserts the stricter
    L2 rule, as the review asked. The fake page in the hostile-size test gained a PDFium twin.
  - Regression runs: unit, workflows and contracts 5,250; trust kit 99; hostile files 29;
    affected backfill 94; agent and top-level 32. All pass.
  - **Deploy note:** runs in flight at deploy replay their old path, and uploads made before
    the deploy have no masked rendition or `w2`/`d2` layer. Their pages answer 409
    `preview_outdated`, and agents get no material, until `trust_layer_backfill` v2 has run for
    each tenant: `python -m abacus_tools.trust_layer_backfill`, as an ECS one-off on staging and
    production after the deploy. P-03-T26's RB-31 runbook should carry this step.
- 2026-10-26 (security review round 2, recorded in DEC-369):
  - **N1:** image content (0.25% of the page or more, and legible-number sized) marks the page
    unscanned for its images. Its text stays masked; offshore readers are refused the page.
  - **N2:** `detect` joins comb, split and wrapped digit runs; the kernel scrub reads
    single-separated nine-digit runs.
  - **L4:** page lines are matched on punctuation-free tokens; a page with an unmatched region
    word has no lines.
  - **L5:** the masked renderer is `v3`, and only the current renderer version is served.
  - Regression check: the sideways-text and curve rules are tuned (see DEC-369), and all
    synthetic PDFs stay scannable.
  - r2 variants through the pipeline:
    - comb, split-on-one-line, spaced and wrapped TINs each leave exactly the label-only
      baseline of dark pixels;
    - agent material for each carries `•••-••-6789` and no TIN;
    - images at 0.5%, 1.2%, 8% and 20% are all flagged.
  - Tests:
    - `test_pdf_layout.py`: 28;
    - `test_tin_spaced.py`: 9;
    - `test_masked_renditions.py`: N1 at 8% and 20% (onshore served, offshore refused, agent
      text only), L4 and L5.
  - Existing tests changed:
    - the H2 "mostly an image" test is replaced by N1's (stricter flag);
    - `test_viewer` seeds the current renderer version;
    - the stored-rendition assertion uses the version constants.
- 2026-10-26 (security review round 3, recorded in DEC-369): every rule is now the broader one.
  - **R1:** an image of 20 by 4 pt or more marks the page `unread`, with no area floor.
  - **R2:** 9 or more glyph-sized vector objects, straight or curved, anywhere on the page mark
    it `unread`.
  - **R3:** any sideways digit marks the page `unread`; sideways words are left out of the layer.
  - **R4:** digit pieces take more separator kinds, and masks spread by 0.6 of their height.
  - **R5:** fragments after a label are masked, carried over a page break.
  - Outlined and sideways content now marks the page `unread` instead of dropping its words, so
    onshore text masking is kept.
  - r3 variants through the pipeline (`scratchpad/r3fix/run.py`):
    - every upright separator variant is at or below the label-only baseline;
    - every sideways, outlined (pitch 8, 11 and 12) and image-strip variant (down to 60 x 5.5 pt)
      is refused to offshore readers;
    - both EIN splits and both pages of the page-break case are at or below baseline.
  - Tests:
    - `test_pdf_layout.py` (R1 to R5 regressions, updated semantics);
    - `test_masked_renditions.py::test_review_r5_...` (page break through the real scan);
    - `test_pii_detector.py` is unchanged and passes.
  - Existing tests changed to the new semantics:
    - outlined text, sideways digits and the vector logo now assert `unread` with the words kept;
    - the N2 pixel checks are `<=` the label-only baseline, because masks spread over neighbours.
- 2026-10-26 (Ayush, in chat: "Offshore readers get the masked-text-only view (no page
  images) until OCR (P-11) lands"; recorded in DEC-369):
  - **Pages:** the C4 page route refuses every offshore read (403 before any read). The legacy
    page and preview routes, the download, the statement preview and the setup files already
    refused offshore readers.
  - **Text view:** the manifest carries `view: text`, and a new `GET …/text` serves the masked
    projection per page, with `unread` flags and masked sheet cells. Contract first:
    `ViewerTextOut` plus the C4 doc, then `make generate` and the regenerated security-test
    route list.
  - **SPA:** SHL-08 and the cockpit dock render `app-core/masked-text.tsx`. Fixtures: the
    `textOnly(state)` scenario builder and a W-2 text seed.
  - **Tests:**
    - backend: `test_masked_renditions.py` covers 9 variants (r3 layouts plus a clean upright
      page): offshore 403 on the page, masked text with no TIN spaced, joined or reversed;
      onshore keeps images; workbook text masked;
    - route level (`test_offshore_evidence_reads.py`): `viewer_page` added to the refused
      routes, plus the text and manifest view;
    - frontend: the text view renders with no `img` or region; the fixture contract
      validates `…/text`;
    - C4 contract: the new route and the classifications.
  - **Deploy note:** offshore readers see text only from deploy on, independent of the backfill.
    A version not yet backfilled answers 409 `preview_outdated` on its text view.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-369 | Masking rules the plan leaves open (fill colour, fail-closed cases, sheets, verifier on unscanned pages, legacy routes) | No |
