---
id: TASK-430
title: C-16 Request kit portal variant; T7a to T7g, T7-M, TPL-07a to TPL-07f and TPL-07-M (F-05-T36)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T36
branch: f05-t36-request-kit
created: 2026-10-23
updated: 2026-10-23
---

## Objective

"TPL-07a shows exactly two open requests, the drop target uses the 2px espresso ring, Mark as Done
turns olive in 260 ms, and no red marks a missing item." (F-05-T36)

## Scope

**In** (`packages/ui/src/requests/`, exported from the package root)

- `types.ts`: the C-16 rules ported from `reference/request-rows-types.ts` (`satisfied`, `keep`,
  `categoryState`, `doneButton`, `naText`, `rowView`, `route`, `applyUpload`), the nine categories,
  the filters and the three Ignore reasons. The firm's name is always a parameter.
- `parts.tsx`: RequestSection, RequestRow (client side: uploaded, accepted, requested, needs
  follow-up with the inline reply, not applicable with Undo, firm-provided, returned), CategoryRail
  (`listbox`, ↑ ↓ Home End), DropZone and DropRing (the arc hidden at 0), the Uploading band and
  UploadRow (64 × 3 bar), MarkAsDone (tonal, then olive over 260 ms, never `disabled`), DoneBanner,
  RequestEmpty, DragStack, and the simple menu the Show, Binder, Ignore and Remove menus share.
- `binder.tsx`: `useRequestBinder` (filter, category, drop target, Mark as Done, the client's own
  edits) with `RequestRail`, `RequestDocuments` (the well, drop handling, unsorted section, empty
  states) and `RequestMobile` (TPL-07-M's 390 column). Intents go out through callbacks.
- Specimens: `c-16-request-rows`, `t7-client-portal` (T7a to T7g, T7-M) and `tpl-07` (TPL-07a to
  TPL-07f, TPL-07-M), every name, file and date from the canvases (`t7data`, `TP7`).
- Parity: Tier B (unlocked, report-only) entries for the 15 artboards, pinned with
  `crop_handoff --pin`; the two 390 frames carry recorded deviations.

**Out**

- The kit's toasts, the menu flip and the under-760 header collapse (DECISIONS.md).
- The firm-side binder (BND-01, P-06) and the fly animation.
- Real uploads and routing on the server: POR-03 (P-08) binds `onFiles` to upload intents.

## Plan

Green zone. No migration, registry, flag or dependency. Rollback is a revert.

Tests (`requests/request-kit.test.tsx`, 28):

- exactly two open requests → "TPL-07a shows exactly two open requests, matching Intake 2".
- 2px espresso ring → "the drop target uses the 2px espresso ring on the nested fill (TPL-07b)".
- olive in 260 ms → "Mark as Done is tonal while requests are open and olive over 260 ms".
- no red on a missing item → "no red marks a missing item".
- The other artboards (TPL-07c to 07-M, T7a to T7g), the rules, and the behaviour (Ignore with a
  reason and note, Undo, Remove, Reply with ⌘↵, the blocked Mark as Done, filter and category,
  the rail's keys, a live drop).

## Definition of done

- [x] `vitest run src/requests/request-kit.test.tsx`: 28 passed.
- [x] ui tsc, eslint, prettier; apps/web gallery and specimen-figures tests.
- [x] Parity (`playwright --project=visual parity.spec.ts`): 15 entries run, report-only.
- [x] `e2e/a11y.spec.ts` over the gallery.

## Progress log

- `2026-10-23` Built and checked as above. The parity captures come out 2 device px taller than
  the crops (the artboards sit at a fractional y on the long gallery page), so the report shows a
  size note, not a diff %. The single-artboard route `/components/specimens/:tpl?st=` (F-05 I1)
  fixes that; F-05-T49 locks these frames.

## Decisions made during this task

Recorded in `packages/ui/src/tokens/DECISIONS.md`, "C-16 Request kit, portal variant (F-05-T36)".
