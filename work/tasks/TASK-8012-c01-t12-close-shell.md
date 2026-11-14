---
id: TASK-8012
title: "C-01-T12: close shell — /closes subtree, RecordHeader close variant, manifest, handlers"
spec: SPEC-655
acceptance_criteria: []
risk_zone: green
status: in-review
branch: c01-t12-close-shell
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T12
---

## Objective
close shell — /closes subtree, RecordHeader close variant, manifest, handlers.

## Plan
1. [x] Lazy `/closes` route subtree with tab-slug validation in beforeLoad (overview, intake, accounts, review, deliverables).
2. [x] RecordHeader variant `close` (period stepper, close tabs with Review count).
3. [x] Screen-manifest entries for CLS-01…06, 09, 10 and planned targets CLS-07/08/11/12/13, INB-04, HOME-03, SHL-21.
4. [x] Fixture handlers typed against the T04/T05 stubs; copy registries.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).
- `2026-11-14` — Built: `routes/firm/closes.tsx` (lazy routes `/closes/$closeId` overview, `/intake`, `/accounts`, `/accounts/$accountRef`, `/review`, `/flux`, a `$tab` catch whose beforeLoad lands any other slug on Overview, and `/close-plans/$clientId`), registered under the Closes area; `screens/CLS-02` close shell (RecordHeader variant `close` with the period stepper, Overview · Intake · Accounts · Review n · Deliverables, Deliverables disabled until C-02, flag-off state inside the frame); manifest paths for CLS-02 to CLS-06, CLS-09, CLS-10 (still `planned`); fixture handlers and the Copperleaf August record seed (handoff figures); scenarios `shell` and `off`; `CLS-02.test.tsx` (not run).
- **Fix carried here.** Seven C-01 model names collided with existing OpenAPI schema names (`PersonRefOut`, `DraftIn`, `RegisterOut`, `WorkpaperOut`, `ReconciliationOut`, `RegionOut`, `StatementLineOut`), which made FastAPI module-qualify both and broke existing web imports. Renamed at their source (T04, T05: `ClosePersonOut`, `PlanDraftIn`, `CloseRegisterOut`, `CloseWorkpaperOut`, `CloseReconciliationOut`, `StatementRegionOut`, `CloseStatementLineOut`), the stack restacked and the client regenerated in T07. Lesson: diff `components.schemas` against main after `make generate`.
- **Partials.** `/closes` stays the area landing until CLS-01 (T33). Tier D geometry (record bar 42, tabs 50) runs in the parity suite at the end pass. The `closes` module is not yet in the web `MODULES` list (no screen gates on the entitlement yet).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
