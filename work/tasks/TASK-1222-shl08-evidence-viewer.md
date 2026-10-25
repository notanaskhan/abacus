---
id: TASK-1222
title: SHL-08 EvidenceViewer on its two hosts — O2 drawer ?ov=viewer and T2 dock ?dock=viewer (P-03-T14)
spec: SPEC-322
acceptance_criteria: [AC-13, AC-14, AC-15, AC-16, AC-17, AC-18, AC-19]
risk_zone: green
status: done
epic: P-03
plan_key: P-03-T14
branch: s8b-evidence-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"The lit figure row and page region share one match, the region scrolls to 30% from the top, and no
raw file, pdf.js or toolbar Download ever appears." States a (drawer), b (dock pane with trial
balance re-target), e (loading), f (source 2 of 3), h (auto-highlight outlines); the linked-figure
card, stacked edges, Also cited, page and zoom controls, Download only in the ⋯ menu.

## Plan
- **L3 container** `apps/web/src/screens/SHL-08/`: `useViewerManifest.ts` (manifest polled every
  3 s while `processing`, regions, page blobs), `EvidenceViewer.tsx` (stack stepping, the opened
  region's linked-figure tag, auto-highlight preference, ⋯ menu, Also cited), `LinkedFigures.tsx`,
  `ViewerDrawer.tsx` (O2, 480, no scrim), `ViewerPane.tsx` (dock body for `dockHost(…, { viewer })`),
  `copy.ts`, `index.ts`; artboards a–f, h rebuilt on the two hosts.
- **L2 shell** `packages/ui/src/viewer/source-viewer.tsx`: `header`, `skeletons`, `outlineCited`,
  `scrollToLit` (`LIT_AT`, `litScrollTop`), `stack` edges, `aboveWell`, `afterPages`; a page whose
  image is still loading is drawn blank with its regions. `ViewerRegion.cited`.
- **Routing:** `?ov=viewer:<v>[:<match>[:<type>:<id>:<ref>[:<figure>]]]` registered in
  `routes/firm/viewer.tsx` (lazy chunk, behind `evidence.viewer_v1`); `sourceViewerArgs` and
  `sourceViewerTarget` in `app-core/overlays.ts`; `useOpenSourceViewer()` in `overlay-host.tsx`.
- **Fixtures:** the K-1 stack titles carry the "Also cited" copy; a States figure row; SHL-08e answers
  `processing` (DEC-350).
- **No** migrations, flags, registry or endpoint changes. **Rollback:** revert the commit.

## Scope
**Out**
- c (masked PII, logged reveal and `MaskedValue`) and d (unlock panel): P-03-T16, T19, T20. The
  viewer renders masks as their tokens and never unmasks; offshore readers get the masked projection.
- g (Annotate) is K-03's; the Annotate capsule is not drawn.
- The server search capsule (AC3.9) keeps the shell's local label find until P-03-T09's search is
  bound; AC3.8 (spreadsheet table) waits for a table-kind fixture.
- Switching the legacy `ItemDetail` and review-queue hosts from `EvidencePreview` (behind
  `evidence.viewer_v1`) and mounting `ViewerPane` in AUD-06's dock (A-02).

## Progress log
- 2026-10-25: built. 18 new viewer tests (`EvidenceViewer.test.tsx`), 6 new shell tests, the SHL-08
  scenario and artboard tests green. The scenario test for e now asserts the processing manifest
  (AC3.4) instead of a manifest that never answers (DEC-350); the figures test gains the States row.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-349 | `?ov=viewer` carries the opening anchor and figure name so the card and stack survive a reload; figure rows read in page order | No |
| DEC-350 | SHL-08e's fixture answers `status=processing` (AC3.4) so the file name and "Processing…" can show | No |
