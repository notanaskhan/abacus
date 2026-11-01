---
id: TASK-2222
title: F-06-T11 TPL-19 frames 5 and 6 (v1 capture) and the TPL-19 lock
spec: SPEC-000  # F-06-T11 row and the TPL-19 handoff; no SPEC defines the specimen
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: done
epic: F-06
plan_key: F-06-T11
branch: s17-f06-t11
created: 2026-10-30
updated: 2026-11-01
---

## Objective
TPL-19 frames 5 and 6 for v1 capture (DEC-45): the upload action sheet with native camera input,
ReviewAssignSheet with page previews and the Add to request picker, UploadRing to receipt; frames
3, 4, 8 and permission-off marked deferred (DEC-97); TPL-19 parity lock.

Acceptance (backlog row): "Frame 6 moves the title pill from 2 to do to 1 to do with the green-ink
receipt, deferred frames render a Deferred (DEC-97) placeholder, and TPL-19 is parity-locked."

## Plan (amber)
- `packages/ui/src/requests/capture.tsx` (new): `UploadActionSheet` (native `capture="environment"`
  camera input and file input), `ReviewAssignSheet` (page previews 150 × 194, stitched file line,
  Retake / Add a page, native-select request picker with "Something else", 48 Upload),
  `DeferredFrame`.
- `RequestMobile` (additive): `onUpload` intercepts Upload… and the DropZone card; `progress` draws
  the UploadRing on a card; `openOnly.keep` keeps a just-answered card for its receipt; "Matched to
  this request" under a matched receipt.
- `PortalLayout` mobile (additive): `overlay`.
- `specimens/tpl19.tsx`: frames 3, 4, 5, 6 (ring and receipt), 8, permission off; frame 2 runs the
  capture path live.
- Lock: Tier D `apps/web/e2e/visual/tier-d-tpl19.spec.ts` (no handoff PNG exists for TPL-19).
- Tests: `packages/ui/src/templates/tpl19.test.tsx` (frames 3–8, the flow).
- Rollback: revert; additive props only.

## Progress log
- 2026-10-30: built in S17 Lane 2 off main; tests run in the end review.
- 2026-11-01: merged to main in #794 (59be914f7).
