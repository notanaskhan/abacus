# CLS-08 · Close package · Copperleaf August 2026

| Field | Value |
|---|---|
| Route and params | `/closes/$closeId/package` (C-02 §5.1); artboards `/components/screens/CLS-08?st=…` |
| Template and host frame | T6 WorkbookLayout (paper) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-08 Close - Deliverables - Copperleaf August 2026 statements/` |
| Epic and tasks | C-02 · SPEC-700, SPEC-701; screen contracts and scenarios C-02-T15 (TASK-8624); screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | live (C-02-T23 a to c; C-02-T37 d to g) |

Parity tier target: C (C-02 §5.5). Copy keys live in `apps/web/src/screens/CLS-08/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Draft ready to release | ``fixtures/scenarios/CLS-08.ts` state` | Priya Raman | Mon Sep 14, 4:10 PM | planned | AY |
| a2 | Release · confirm | ``fixtures/scenarios/CLS-08.ts` state` | Priya Raman | Mon 14 Sep 2026, 4:10 PM | planned | AY |
| b | Drafting | ``fixtures/scenarios/CLS-08.ts` state` | Priya Raman | Mon 14 Sep 2026, 4:10 PM | planned | AY |
| c | Blocked · 9:24 AM | ``fixtures/scenarios/CLS-08.ts` state` | Priya Raman | Mon 14 Sep 2026, 4:10 PM | planned | AY |
| d | Released | ``fixtures/scenarios/CLS-08.ts` state` | Priya Raman | Mon 14 Sep 2026, 4:25 PM | live | AY |
| e | Approved by client | ``fixtures/scenarios/CLS-08.ts` state` | Priya Raman | Mon 14 Sep 2026, 8:42 AM | live | AY |
| f | SSARS 27 route · illustrative December 2026 close | ``fixtures/scenarios/CLS-08.ts` state` | Priya Raman | Mon 14 Sep 2026, 4:10 PM | live | AY |
| g | “No” answer | ``fixtures/scenarios/CLS-08.ts` state` | Priya Raman | Mon 14 Sep 2026, 4:10 PM | live | AY |

## States d to g (C-02-T37, DEC-5925)

- d: `status = released`; the green-tint "Released Sep 14" pill with "Released by Priya Raman · 4:25 PM · Portal › Deliverables · approval requested from Tess Moreno and Ben Ashby" (`released_by`, `approval_requested_from`, read now); the watermark is gone and Edit and Regenerate are off.
- e: `status = approved_by_client`; the green "Approved by client" pill with "Approved by Tess Moreno · Sep 15, 8:42 AM (POR-08) · released by Priya Raman · Sep 14, 4:25 PM"; "Lock close" opens a confirm and posts `POST /v1/closes/{id}/lock` (`close.lock`, fresh MFA; 409 `client_approval_required` before approval); a locked close shows "Locked" and "Reopen close…", a dialog whose Reopen stays off until a reason is written (`POST …/reopen`, `close.reopen`).
- f: the CAS by-product route: no legend and no report on the pages or in the basis.
- g: the standalone route: "Legend or report — Per the engagement letter" and "Engagement letter — Open letter" (ENG-04, a planned link).
- R2: "Open in statements studio" / "View in studio" and the Release band's "Studio version — v1 · synced with this package" are planned links (FSP-01, A-10): drawn disabled with their hint in dev, fixture and gallery builds; a production build drops them, so no live scenario shows them (`CLS-08.live.test.tsx`).

## Deviations
- The lock and reopen confirms' words are C-02-T37's (DEC-5925); the handoff names only the action. The studio button sits on the status row beside the pill, not inside the paper header, until FSP-01 is built.
- Personas and clocks per state are in the scenario file (CLS-07 c, c2, d are Priya Raman's; the README's viewer column names Raj).

## Design deltas (C-02-T10, DEC-5509)
Each row is the frame it amends (an annotated handoff screenshot) and the build answer; none needs a backend change outside the C-02 backlog.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `screenshots/CLS-08d.png` close pill | Delivered shown alone | Approved shown before Delivered in the release sequence (the reviewer's sign-off inside the dialog) | DF-23; SPEC-701 Q3 |
| `CLS-08c.png` "Entries not posted" | posted only | the precondition accepts posted or Recorded externally | DF-19; SPEC-701 Q6 |
