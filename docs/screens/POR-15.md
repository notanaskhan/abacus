# POR-15 · Governance room

| Field | Value |
|---|---|
| Route and params | `/governance`, `/governance/$communicationId` · `?tab=communications\|reports\|questions` |
| Template and host frame | T7 rail 336 · paper pane 1030 with the T10 paper card; reduced nav; T7-M · `Wave 2 - Client Portal.dc.html` |
| Surface | client portal (never renders "Accrued") |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-15 Governance room - Northwind benefits committee/` (README.md, spec.md; revision.md wins where present) |
| Epic and tasks | R-02 · stubs T02 · bundle T04 · service T12 · screen T15 · threads T22 · parity T24 · SPEC-646 |
| Manifest status | planned (live with its screen task) |

## States
Clock is the demo clock (DEC-27): CDT (UTC−5) until Sun Nov 1, 2026, CST (UTC−6) after.

| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | victoria-lam | Mon Sep 21, 2026 8:30 AM CDT | Planning letter sent Sep 18 (dated Sep 17), acks Dana Sep 18 and Robert Sep 19, 2 of 3 | live (T12, T15) |
| b | victoria-lam | 8:31 AM CDT | All acknowledged; rail reads Acknowledged by the committee · Sep 21 | live (T12, T15) |
| c | victoria-lam | 8:30 AM CDT | Two private AU-C 240 inquiries, Send answers | live (T12, T15) |
| d | victoria-lam | Tue Nov 24, 2026 CST | Completion letter Sent Oct 8 · acknowledged; AU-C 265/703 letter sent Nov 20, due Dec 8 | live (T12, T15; DV-12) |
| e | victoria-lam | Mon Oct 12, 2026 | Reports tab: report and FS 14 pages, Download | live (T09, T15) |
| f | victoria-lam | Wed Sep 16, 2026 | Nothing from your auditor yet. | live (T15) |
| loading, error, not allowed, flag off, M 390 | as the scenario | — | Skeleton after 200 ms; walls and out-of-scope grants answer 404 (INV-3, INV-4); the designed flag-off state, never a 404 page; M from the spec text | live |

Parity tier: Tier C report-only through S34, locked at exit (R-02-T24); Tier D on toolbar and pane headers.

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/portal/governance/rooms`, `…/rooms/{room_id}/communications` | `GovernanceRoomsOut` | `tcwg.read` |
| read | `GET /v1/portal/governance/communications/{id}`, `…/{id}/pdf` | `GovernanceLetterOut` | `tcwg.read` |
| write | `POST …/communications/{id}/acknowledge` | `AcknowledgeIn` | `tcwg.acknowledge` |
| read, write | `GET·POST …/communications/{id}/questions` | `ItemQuestionIn` | `tcwg.ask` |
| read | `GET …/rooms/{room_id}/inquiries`, `…/reports` | `RoomInquiriesOut` | `tcwg.read` |

Every endpoint is in `docs/contracts/deliverables.md` (T02) or `docs/contracts/portal-approvals.md` (T03); 501 until its task.

## Status
`governance_communication` (client words, DF-31; `docs/product/status-vocabulary.yaml`, R-02-T04).

## Copy
"Nothing from your auditor yet.", "Planning communications usually arrive before fieldwork.", "Acknowledging confirms you've received and read this letter.", "Your answers go only to the Brightwater Hale audit team. Other committee members and plan management can't see them.", "Ask the auditor…". Banned on this screen: "Accrued", "agent", "task", "Within threshold", any threshold or policy name, "materiality", "Post", "SAS 114", red except for Declined, blue, emoji.

## Deviations
- DV-03: Ask the auditor… is a private thread on the communication; INB-04 flagged TCWG arrives with N-03
- DV-07: the 390 layout is derived from the spec text and T7-M (DF-03); no PNG, no pixel parity at 390
- DV-10: the member email on send is the new Governance letter database template (DF-40)
- DV-12: README labels board d Completion frame; the spec's d is the internal control letter (Tue Nov 24, 2026)

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|


## Acceptance
- Every artboard letter above carries live, fixture-only or deferred with its owning task or epic.
- No control lets an agent or a firm user decide; client decisions are five-layer human-only (SPEC-646 AC-5).
- No DTO carries materiality, thresholds, review notes, sign-offs, agent or confidence (SPEC-646 AC-7).
