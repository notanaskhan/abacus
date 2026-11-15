# AUD-26 · Review, compilation & preparation workspace (SSARS)

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId` when the work item's engagement type is review, compilation or preparation (A-01 dispatch; `?section=inquiries|analytics|fs|report&dock=agent`) |
| Template and host frame | T2 RecordCockpit with the Agent dock (rail Inquiries · Analytics · FS · Report) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-26 Review- compilation and preparation workspace - SSARS/` |
| Epic and tasks | A-08 · SPEC-657 · A-08-T01 (contract), A-08-T05/T06 (stubs), A-08-T08 (content), screen rows per A-08 §9 |
| Persona | Laura Kemp (Manager) |
| Flags | `audits.ssars_workspace`; the agent dock behind `audits.fieldwork_agents` |
| Priority | P1 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

Every artboard is **built** (A-08 §2.1). Fixture-only parts are named in their row. 5 artboards.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Analytics | Lakeshore FY2026 review (AR-C 90): revenue 4,174,000, expenses 4,014,000; Grants (360,000) (24.3%) over 10% and $50,000; agent explanation (run #4119) awaiting acceptance | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `lakeshore.review` |
| b | Inquiries | 11 of 14 answered; 3 "Requested Sep 10"; Send reminder… · Publish to portal | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · C report-only | planned · `lakeshore.review` |
| c | Compilation · Fenwick | AR-C 80, partner Priya Raman; rail "Read the FS for obvious material misstatements" (L1); report row → AUD-23 | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · C report-only | planned · `fenwick.compilation` |
| d | Preparation · Juniper & Oak | AR-C 70: "No assurance is provided." on every page; "No report — AR-C 70"; "Approved by Carla Juniper (POR-08)" | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `juniper-oak.preparation` |
| e | Over threshold · unexplained | Grants amber with TriangleAlert and "Ask client…" (SHL-14 → POR-05), before Monica answered | Mon Sep 8, 2026 | E0 variant | D · C report-only | planned · `lakeshore.review` |
| loading | — | skeleton per the template's loading grammar | — | — | D | planned |
| error | — | the read failed: designed error with Retry (chapter 10 §10.3 kind 10) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3); a client principal always 404 on confirmation routes | — | — | — | planned |
| flag off | — | C-20 "not turned on" state for the screen's flag; never a blank pane | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/AUD-26/scenarios.ts` (A-08 §5.4), exported from the Python scenario (`make fixtures`, F-04-T31) and derived from the seed's footing figures, never typed by hand. Copy keys are `aud26.<state>.<element>` in the screen's `copy.ts`.

## API

Every state reads this endpoint set (A-08 §4.3; stubs in A-08-T05 / T06):

- `GET /v1/work-items/{wid}/ssars` (`ssars.read`)
- `POST /v1/work-items/{wid}/ssars/inquiries` · `…/publish` · `…/remind` (`ssars.inquiry_manage` · `client_question.send`)
- Analytics as AUD-13 (`kind = ssars_review`): `GET /v1/analytics-sets/{aid}`, `PUT …/expectation`, `PUT …/explanation`, `POST …/explanations/accept`

Matrix actions from `permission-matrix/{sampling,workpapers,assurance,identity}.yaml` (A-08-T03): every adopt, accept, approve, decide, send and close is a person's (`agent: deny`); every client principal is denied.

## Links

| From | To | Status |
|---|---|---|
| Ask client… | SHL-14 → POR-05 | live |
| Compilation report (AR-C 80) | AUD-23 compilation mode | live |
| FS paper preview | AUD-20 render | live |
| Approval row | POR-08 (C18) | live |

## Notes

The mode is read-only, set at ENG-03, and announced as read-only. "Conclusion", never "opinion" (copy lint). Review mode shows no audit-only artefacts (risk register, sampling, confirmations, control testing). Inquiry status words are request vocabulary (Requested / Answered). Inquiry cards are list items with their status in text.

## Deviations

- DV-4 reminders are firm templates a person edits and sends.
- DV-3 closed data boundary shows DF-04 in the dock.

## Acceptance

SPEC-657's criteria for this screen; each becomes a test named "AUD-26 acceptance: <criterion>".
