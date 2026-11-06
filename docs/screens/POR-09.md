# POR-09 · Deliverables

| Field | Value |
|---|---|
| Route and params | `/deliverables`, `/deliverables/$deliverableId` · `?v=` · `?page=` · `?section=k1s` |
| Template and host frame | T7 PortalLayout split (rail 336 · viewer 1030 with comment column 280; paper from T10) and T7-M · `Wave 2 - Client Portal.dc.html` |
| Surface | client portal (never renders "Accrued") |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-09 Deliverables - Northwind Robotics 401-k- Plan/` (README.md, spec.md; revision.md wins where present) |
| Epic and tasks | R-02 · stubs T02 · bundle T04 · service T09 · serving T07 · screen T17 · threads T22 · parity T24 · SPEC-646 |
| Manifest status | planned (live with its screen task) |

## States
Clock is the demo clock (DEC-27): CDT (UTC−5) until Sun Nov 1, 2026, CST (UTC−6) after.

| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | dana-kowalski | Tue Oct 6, 2026 11:10 AM CDT | Draft v3, DRAFT watermark, page 2 of 14, pin 1 (10:14 AM) and Hannah's reply (11:02 AM) | live (T09, T17, T22) |
| a2 | dana-kowalski | Thu Oct 8, 2026 | Draft v4, confirm "Approve the 2025 financial statements (the latest draft)?" | live (T09, T17) |
| b | dana-kowalski | Thu Oct 8, 2026 | Approved by you · Oct 8; watermark stays until release | live (T09, T17; DV-04) |
| c | dana-kowalski | Fri Oct 9, 2026 10:30 AM CDT | Report 3 pages, FS 14 pages, both Final, no watermark, Download | live (T09, T17; A-07's release) |
| d | meera-shah | Tue Sep 15, 2026 | Role union: 2025 Tax Return Not ready yet; My K-1s, Ridgeline K-1 released Sep 15 (468,008 / 6,992 / 2,356 / 228,000; 38%) | live (T17; DV-09) |
| e | tess-moreno | Mon Sep 14, 2026 4:40 PM CDT | Copperleaf August package row, Waiting for approval, AR-C 70 legend on every page | fixture-only (DV-08) |
| f | luis-ferrante | Tue Oct 6, 2026 11:10 AM CDT | Nothing delivered yet. | live (T17) |
| g | luis-ferrante | Fri Oct 23, 2026 10:20 AM CDT | Suggest edits, R2 revision | deferred (DV-06; A-10) |
| h | luis-ferrante | Mon Oct 26, 2026 9:00 AM CDT | Changes after firm review, R2 revision | deferred (DV-06; A-10) |
| i | marisol-vega | Fri Nov 13, 2026 4:00 PM CST | SOC 2 report, R2 revision | deferred (DV-06; X-01) |
| loading, error, not allowed, flag off, M 390 | as the scenario | — | Skeleton after 200 ms; walls and out-of-scope grants answer 404 (INV-3, INV-4); the designed flag-off state, never a 404 page; M from the spec text | live |

Parity tier: Tier C report-only through S34, locked at exit (R-02-T24); Tier D on toolbar and pane headers.

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/portal/deliverables` | `DeliverablesOut` | `deliverable.read` |
| read | `GET /v1/portal/deliverables/{id}`, `…/versions/{v}` | `DeliverableOut` | `deliverable.read` |
| read | `GET …/versions/{v}/pages/{n}` | PNG | `deliverable.read` |
| read | `GET …/versions/{v}/download` | 302 | `deliverable.download` |
| write | `POST …/versions/{v}/approve` | `DeliverableApproveIn` | `statement.client_approve` |
| read, write | `GET·POST …/versions/{v}/comments` | `PageCommentIn` | `deliverable.comment` |

Every endpoint is in `docs/contracts/deliverables.md` (T02) or `docs/contracts/portal-approvals.md` (T03); 501 until its task.

## Status
`deliverable` (client words, DF-31; `docs/product/status-vocabulary.yaml`, R-02-T04).

## Copy
"Nothing delivered yet.", "Finished documents from Brightwater Hale will appear here.", "Click anywhere on a page to add a comment.", "Approved by you · Oct 8", "Brightwater Hale will release the final statements with the report.", "A newer draft is available". Banned on this screen: "Accrued", "agent", "task", "Within threshold", any threshold or policy name, "materiality", "Post", "SAS 114", red except for Declined, blue, emoji.

## Deviations
- DV-04: README time label is wrong; b is Thu Oct 8, 2026
- DV-06: g, h, i are not built (A-10, X-01); the CoReview kit is not mounted and the Comment · Suggest edits control is absent
- DV-07: the 390 layout is derived from the spec text and T7-M (DF-03); no PNG, no pixel parity at 390
- DV-08: e is fixture-only until a provider registers `fs_package`
- DV-09: K-1 attachment chips use T-02's routes and its electronic-furnishing consent sheet

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|


## Acceptance
- Every artboard letter above carries live, fixture-only or deferred with its owning task or epic.
- No control lets an agent or a firm user decide; client decisions are five-layer human-only (SPEC-646 AC-5).
- No DTO carries materiality, thresholds, review notes, sign-offs, agent or confidence (SPEC-646 AC-7).
