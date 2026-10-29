# POR-05 · Questions · Feld 2025 Tax Organizer

| Field | Value |
|---|---|
| Route and params | Portal `/questions`; `?q=<questionnaire>&section=&filter=` |
| Template and host frame | T7 `PortalLayout` (full shell) · `Wave 2 - Client Portal.dc.html#por05` |
| Surface | portal |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-05 Questions - Feld 2025 Tax Organizer/` (README.md, spec.md; revision.md wins where present) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-02 · contract T-02-T06 (this file); fixtures T08; build T09 onward |
| Spec and ADRs | SPEC-502 AC-7; ADR-231; DEC-43 |
| Manifest status | planned until its build (DEC-195); pilot posture: agents off |

## States
Clock E0 is Mon Sep 14, 2026, 9:24 AM CT.

| Artboard | Viewer | Clock | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | claire-feld | E0 | Default · 3 open | C (lock) | fixture (T-02-T08) |
| b | claire-feld | E0 | Yes with upload | C report | fixture (T-02-T08) |
| c | claire-feld | E0 | Complete | C (lock) | fixture (T-02-T08) |
| d | dana-kowalski | E0 | Fraud inquiries (addressee) | C report | fixture (T-02-T08) |
| e | luis-ferrante | E0 | Analytics questions (addressee) | C report | fixture (T-02-T08) |
| f | claire-feld | E0 | Empty | C (lock) | fixture (T-02-T08) |

Non-artboard: not allowed (404, no count), flag off (C-20 "not turned on"; the portal item hidden), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
`GET /v1/portal/questionnaires`, `/{id}`, `PUT …/answers/{qid}` (If-Match), attachments, `:mark-done`, `:submit`. Every write is a person's; the agent never holds Approve, Release, Send or Submit.

## Status
`questionnaire`.

## Copy
Verbatim from the handoff's spec.md (and revision.md) into `screens/POR-05/copy.ts`; portal copy never says "Accrued".

## Links
Outbound: POR-03 (uploads), POR-02 (home). Inbound: portal nav (hidden with `questionnaires.v1` off).

## Acceptance
- POR-05 acceptance: every artboard renders from its fixture scenario with the persona and clock above.
- POR-05 acceptance: status is never colour alone.

## AVOID
Gradients, emoji, blue, heavy shadows, invented data, boxed inputs, the agent as approver, engine figures not from an approved import.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | White-labelled: the firm's name, never Accrued | T-02 §2 | DEC-1167 |
| D2 | Inquiries are answered and submitted by their addressee only (service) | T-02 §2 | DEC-1167 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, c, f | C (lock at exit) | — | |
| others | C report | — | |
| host | D | — | toolbar 46, subbar 42, tabsbar 44, pane header 46, rows 38/44/56, pills 21/19 |
