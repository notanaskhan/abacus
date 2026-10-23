---
id: TASK-949
title: BND-02 Binder builder & tracker, states a–f in fixture mode on T2 (P-06-T12)
spec: SPEC-319
acceptance_criteria: [AC-12, AC-13, AC-14]
risk_zone: green
status: done
epic: P-06
plan_key: P-06-T12
branch: TASK-949-bnd02-binder-builder
created: 2026-10-23
updated: 2026-10-23
---

## Objective
BND-02 at `/binders/$binderId` (behind `binders.engine`) on the T2 RecordCockpit with the Request
dock: the rail (overview card, key values, the nine categories with olive ticks and "n open"),
the publish bar, request rows with the Eye toggle and the ··· menu (Edit, Waive, Return to client,
Delete), "Preview as client", the Requests and Activity tabs, and the 5-second live poll for
"Uploading n files…" and "Waiting n". Acceptance (P-06-T12): "Six scenarios render, Eye off shows
the internal-only helper, and polling stops while the tab is hidden."

## What changed
- **Screen** `apps/web/src/screens/BND-02/`: `index.tsx` (`BND02`, controlled by the route's
  `?request=` and `?tab=`; `BinderPage` for the gallery), `copy.ts`, `scenarios.ts`,
  `BND-02.test.tsx` (21 tests).
- **Domain** `apps/web/src/domain/requests/binder.ts` (record, rows, live poll gated on page
  visibility, client preview, activity, engagement context, uploads and the sender, row and
  binder writes with Idempotency-Keys) and `BinderParts.tsx` (`CategoryList`, `BinderRequestRow`).
- **Fixtures** `fixtures/seed/binder-detail.ts` (Feld a/b/c/f and Thornbury d/e from the canvas's
  `BN` data), `fixtures/scenarios/BND-02.ts` (C5 shapes; writes change the scenario's own copy).
- **Route** `routes/firm/binders.tsx`: `/binders/$binderId` with search validation; BND-01's row ›
  opens it and "‹ All Binders" returns. Manifest BND-02 path set, status `planned` (G-11).
- **UI kit** `RecordCockpit`: `header` and `tabs` slots, a dock `title`, and a bare frame without
  a toolbar for screens inside the workspace shell; `RecordHeader` settings `stateTone`.
- **Gallery** `/components/screens/BND-02?st=a…f`; **E2E** `e2e/screens/BND-02.spec.ts` (axe).
- **Docs** `docs/screens/BND-02.md` (code, parity, gaps G-1 to G-11), DEC-150.

## Tests mapped to ACs
- AC-12 (Ignore keeps `requested`, return to client clears it, waive needs a reason) →
  `BND-02e ignored`, `Return to client… asks for a note and sends it`.
- AC-13 (Delete only for never-sent Drafts) → `Delete is offered only for a never-sent Draft`.
- AC-14 (the live poll feeds "Uploading n files…" and "Waiting n") → `BND-02a default`,
  `polling stops while the tab is hidden and resumes when it shows`,
  `a Draft or complete binder is not polled`.
- Task acceptance: six artboard tests, `BND-02f visibility off: Eye off shows the internal-only
  helper`, the polling test; spec.md checklist → `BND-02 acceptance: …` tests.

## Progress log
- `2026-10-23 15:00` — Built on fixtures. apps/web typecheck (no new errors outside the known
  api-client set), eslint, vitest 116 files / 1160 tests; packages/ui templates and layout tests;
  Playwright `e2e/screens/BND-02.spec.ts` 6/6 with axe 0 serious or critical. Bundle budget: the
  firm initial was already over on main (251.0 of 250.0 KB) before this task; the new generated
  client functions this screen uses add about 5 KB to the shared sdk chunk.
- First run of axe found `nested-interactive` (a row that was a button holding the Eye and ···
  buttons); the row's title is now the selecting button.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Missing contract facts are gaps, not inventions (G-1 to G-10) | AGENTS.md frontend rule 5 | no |
| Cockpit draws bare inside the workspace shell | The app's Layout already draws the toolbar | no |
| No `to.*()` in production screens yet | The manifest names put "Brightwater" in the dist (dist scan) | no |
| Live poll only while Published and visible | DEC-23 polling; acceptance | no |

## Handoff
- **Current state:** done.
- **Exact next step:** P-06-T13 (SHL-14) enables "+ Request" and Edit; P-06-T16 the follow-up
  sheet and the live swap; P-06-T22 g and the R2 rows; P-06-T11 the read-model fields G-1 to G-4.
