---
id: TASK-1045
title: POR-03 Documents part 1 in fixture mode on T7 and the C-16 Request kit (R-01-T06)
spec: SPEC-323
acceptance_criteria: [AC-6]
risk_zone: green
status: done
epic: R-01
plan_key: R-01-T06
branch: s7-r01-portal-requests
created: 2026-10-24
updated: 2026-10-24
---

Plan of record: docs/screens/POR-03.md; R-01 §3.1, §3.3, §3.4.

## Objective
"Scenario tests for a, c, e, f, g and h pass with axe clean and no firm status word, agent name
or bell in the DOM." Rail with the binder picker (the closed 2024 binder read-only), the DropZone
and Uploading band, category ticks; RequestRow states a, c, e, f, g and h; the Requested filter;
Ignore with three reasons and a note; Mark as Done tonal and olive with the banner and Undo;
Withdraw with the DF-15 line.

## What changed
- `screens/POR-03/{index.tsx, copy.ts, scenarios.ts, POR-03.test.tsx}`: T7 split over C5
  portal-pbc; the rail is composed from the kit's parts with a picker over every binder the person
  can see; the documents pane is the kit's `RequestDocuments` over `useRequestBinder`.
- `domain/portal/documents.ts` (exported through `domain/portal`): `useBinders`, `useBinder`,
  `binderView` (projection → kit rows in client words: receipts, the Suggested line, firm-provided
  and connection rows, Ignored with its day, Returned with the firm's note and name, server ticks
  as `doneCats`), and `useBinderActions` (Ignore and Undo, Mark as Done and Undo, Withdraw of the
  person's own unaccepted file, per-request upload with an upload intent, and a drop in one batch
  with `X-Drop-Batch` and an `Idempotency-Key` per file). `domain/portal/messages.ts` gains
  `DOCUMENT_WORDS`.
- C-16 kit (`packages/ui/src/requests`): opt-ins `withdraw` (DF-15: "Withdraw this file?
  Brightwater Hale’s team won’t use it. It’s kept securely for 30 days, then erased."),
  `suggested` on a row (DEC-58 a) and `readOnly`. Defaults unchanged, so the TPL-07 specimen and
  its tests are untouched; three kit tests cover the opt-ins.
- Gallery: `POR-03` registered (`/components/screens/POR-03?st=a|c|e|f|g|h`). Manifest stays
  planned until R-01-T10 mounts `/documents` and wires POR-02's link (link-contract rule 1).
- Fixtures: the closed 2024 binder (empty until R-01-T11).
- `e2e/screens/POR-03.spec.ts`: the six artboards at 1440 × 900 with axe (zero serious or
  critical), the white-label rule and the firm-word ban.

## Progress log
- 2026-10-24: built and tested. `vitest run src/screens/POR-03` (14 passed), kit tests (31),
  `vitest run src/routes src/screens src/fixtures src/gallery` (557; one SHL-01 timing flake under
  load passes alone), tsc, eslint, prettier; Playwright `e2e/screens/POR-03.spec.ts` 6 passed.
