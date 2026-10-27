---
id: TASK-1614
title: POR-16 live swap in the portal (A-02-T28)
spec: SPEC-333
acceptance_criteria: [AC-36, AC-42]
risk_zone: green
status: in-review
epic: A-02
plan_key: A-02-T28
branch: s13-a02-t28
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Tess Moreno reaches POR-16 in the portal, connects or reconnects through the OAuth round trip and lands back on Connections.

## Plan
- Portal route `/connections` (`?entity=`), its own chunk; manifest POR-16 `live`.
- POR-16 props `onBack` (Home until POR-12), `onStepUp` (a `mfa_required` refusal signs in again and returns), `onExportInstead` (Documents, the TB request's guided steps).
- `legacy/ConnectCallback.tsx`: forwards QuickBooks Online's `realmId` inside the code (`withRealm`, DEC-709); an entity completion returns to `/connections?entity=`.
- `CompleteOut` gains `client_entity_id` and `reconnected` (additive); `make generate`.
- Retiring the portal ConnectionPanel entry: no portal surface renders it any more (the client engagement page redirects to Home since P-08-T28); the firm Overview keeps its read-only panel (`canConnect={false}`), which is not a portal entry.
- Tests `src/screens/POR-16/POR16.live.test.tsx`; the SPEC-020 legacy suite runs unchanged in the batch pass.
- Rollback: revert; the route disappears, the legacy callback still completes.

## Progress log
- 2026-10-27: built; tsc and eslint clean on the touched files. Staging walk is the batch pass's.
