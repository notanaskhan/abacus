# POR-08 · Approvals

| Field | Value |
|---|---|
| Route and params | `/approvals` · `?context=` · `?filter=waiting\|posted\|approved\|declined` · `?ov=decline:<kind>:<id>` · `?ov=ask:<kind>:<id>` |
| Template and host frame | T7 PortalLayout split (rail 336 · main 1030) and T7-M · `Wave 2 - Client Portal.dc.html` |
| Surface | client portal (never renders "Accrued") |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-08 Approvals - Copperleaf August 2026 Close/` (README.md, spec.md; revision.md wins where present) |
| Epic and tasks | R-02 · stubs T03 · bundle T04 · service T11 · screen T19 · threads T22 · parity T24 · SPEC-646 |
| Manifest status | planned (live with its screen task) |

## States
Clock is the demo clock (DEC-27): CDT (UTC−5) until Sun Nov 1, 2026, CST (UTC−6) after.

| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | ben-ashby | Mon Sep 14, 2026 4:40 PM CDT | Copperleaf Aug 2026 package released 4:25 PM by Priya Raman, 5 parts, highlights, AR-C 70 legend; Card B six posted entries 35,300 (QBO 48213–48218), row 5 expanded 14,900 | fixture-only (DV-08; `fs_package` from C-02 or A-08) |
| a2 | ben-ashby | 4:40 PM CDT | O1 confirm "Approve the August 2026 financial statements for Copperleaf Coffee Roasters, Inc.?" | fixture-only (DV-08) |
| b | tess-moreno | Tue Sep 15, 2026 8:42 AM CDT | Approved by Tess Moreno · Sep 15, 8:42 AM; rail Waiting for you 0 | fixture-only (DV-04, DV-08) |
| c | ben-ashby | 4:40 PM CDT | O3 decline sheet: A number looks wrong · Something is missing · Other; card reads Declined · A number looks wrong | fixture-only (DV-02, DV-08) |
| d | ben-ashby | 4:40 PM CDT | Ask about this entry: composer prefilled, row reads Question sent Sep 14 | fixture-only (DV-01, DV-08) |
| e | dana-kowalski | Thu Sep 24, 2026 | Attest: AJE-1 48,600, RJE-1, PAJE-1 35,300, PAJE-2 13,050 with Accept · Decline… · Ask a question | live (T11, T19) |
| e2 | dana-kowalski | Fri Sep 25, 2026 | Decisions recorded; acknowledgement item 22,250 = 35,300 − 13,050 | live (T11, T19; DV-05) |
| f | ben-ashby | 4:40 PM CDT | September context, nothing waiting: Nothing to approve. | live (T19) |
| loading, error, not allowed, flag off, M 390 | as the scenario | — | Skeleton after 200 ms; walls and out-of-scope grants answer 404 (INV-3, INV-4); the designed flag-off state, never a 404 page; M from the spec text | live |

Parity tier: Tier C report-only through S34, locked at exit (R-02-T24); Tier D on toolbar and pane headers.

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/portal/approvals` | `ApprovalsOut` | `client_approval.read` |
| read | `GET /v1/portal/approvals/{kind}/{item_id}` | `ApprovalItemOut` | `client_approval.read` |
| write | `POST …/proposed-entries/{id}/decide` | `ProposedEntryDecideIn` | `proposed_entry.client_decide` |
| write | `POST …/uncorrected-misstatements/{item_id}/acknowledge` | `AcknowledgeIn` | `uncorrected_misstatements.acknowledge` |
| write | `POST …/packages/{id}/decide` | `PackageDecideIn` | `close_package.client_decide` |
| read, write | `GET·POST …/{kind}/{item_id}/questions` | `ItemQuestionIn` | `client_approval.ask` |
| read | `GET …/{kind}/{item_id}/journal` | `RenderAcceptedOut` | `client_approval.read` |

Every endpoint is in `docs/contracts/deliverables.md` (T02) or `docs/contracts/portal-approvals.md` (T03); 501 until its task.

## Status
`client_approval_item` (client words, DF-31; `docs/product/status-vocabulary.yaml`, R-02-T04).

## Copy
"Nothing to approve.", "Brightwater Hale will ask here when statements or an entry need your OK.", "Your auditor proposes these entries. Accepting means the plan records them in its 2025 financial statements.", "Approve statements", "Decline…", "Ask a question", "Ask about this entry", "Prepared by Brightwater Hale. No assurance is provided.". Banned on this screen: "Accrued", "agent", "task", "Within threshold", any threshold or policy name, "materiality", "Post", "SAS 114", red except for Declined, blue, emoji.

## Deviations
- DV-01: Ask about this entry and Ask a question post to the item's thread (P-05) in an inline O3 composer instead of POR-07 compose; N-03 links the thread later
- DV-02: the decline reason reaches the firm as a notification and on the item, not in INB-04 (N-03)
- DV-04: README time labels are wrong; b is Tue Sep 15, 2026 8:42 AM
- DV-05: README names Ben Ashby on e2; e2 is Dana Kowalski's decision
- DV-07: the 390 layout is derived from the spec text and T7-M (DF-03); no PNG, no pixel parity at 390
- DV-08: a to d are fixture-only until a provider registers `fs_package`; production hides the package cards
- DV-11: J22's decline of AJE-3 68,400 by Luis Ferrante has no artboard; it runs on the e and e2 grammar from seed data

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|


## Acceptance
- Every artboard letter above carries live, fixture-only or deferred with its owning task or epic.
- No control lets an agent or a firm user decide; client decisions are five-layer human-only (SPEC-646 AC-5).
- No DTO carries materiality, thresholds, review notes, sign-offs, agent or confidence (SPEC-646 AC-7).
