# POR-13 · K-1 recipient view · My K-1s

| Field | Value |
|---|---|
| Route and params | Portal `/k1s` (reduced shell when `/v1/me.portal.shell = "k1"`; full shell for role union, DV-11) |
| Template and host frame | T7 `PortalLayout` reduced 720 · `Wave 2 - Client Portal.dc.html#por13` |
| Surface | portal |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-13 K-1 recipient view - My K-1s/` (README.md, spec.md; revision.md wins where present) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-02 · contract T-02-T06 (this file); fixtures T08; build T09 onward |
| Spec and ADRs | SPEC-502 AC-7; ADR-231; DEC-43 |
| Manifest status | planned until its build (DEC-195); pilot posture: agents off |

## States
Clock E0 is Mon Sep 14, 2026, 9:24 AM CT.

| Artboard | Viewer | Clock | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | nora-calloway | Tue Sep 29, 2026, 6:40 PM | Released | C (lock) | fixture (T-02-T08) |
| b | pell-street-member | E0 | Not released yet · Pell Street | C (lock) | fixture (T-02-T08) |
| c | pell-street-member | Tue Sep 15 | Released · Pell Street | C (lock) | fixture (T-02-T08) |
| d | nora-calloway | Tue Sep 29 | Update taxpayer ID (sheet) | C report | fixture (T-02-T08) |
| e | nora-calloway | Mon Oct 5, 2026 | Superseded | C report | fixture (T-02-T08) |
| f | meera-shah | E0 | Role union · Meera Shah | C report | fixture (T-02-T08) |

Non-artboard: not allowed (404, no count), flag off (C-20 "not turned on"; the portal item hidden), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
`GET /v1/portal/k1s`, `/{pid}`, `/download`, details change, e-furnishing consent. Every write is a person's; the agent never holds Approve, Release, Send or Submit.

## Status
`k1_package` (client words: "Not released yet").

## Copy
Verbatim from the handoff's spec.md (and revision.md) into `screens/POR-13/copy.ts`; portal copy never says "Accrued".

## Links
Outbound: none beyond downloads. Inbound: K-1 release email (R-01 template).

## Acceptance
- POR-13 acceptance: every artboard renders from its fixture scenario with the persona and clock above.
- POR-13 acceptance: status is never colour alone.

## AVOID
Gradients, emoji, blue, heavy shadows, invented data, boxed inputs, the agent as approver, engine figures not from an approved import.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-11 | Role union renders inside the full shell | T-02 §2 | DEC-1167 |
| D1 | `pell-street-member` is "Pell Street Ventures LLC · authorized member"; no invented name | T-02 §2 | DEC-1167 |
| D2 | White-labelled: never Accrued | T-02 §2 | DEC-1167 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c | C (lock at exit) | — | |
| others | C report | — | |
| host | D | — | toolbar 46, subbar 42, tabsbar 44, pane header 46, rows 38/44/56, pills 21/19 |
