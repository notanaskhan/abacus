# AUD-13 · Analytics · preliminary · substantive · final

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/analytics` (`?stage=preliminary|substantive|final&ov=ask-client`; `?ov=accept` SHL-10) |
| Template and host frame | T6 WorkbookLayout grammar inside the T2 cockpit (rail 330 · canvas 1036, no dock) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-13 Analytics - preliminary - substantive - final/` |
| Epic and tasks | A-08 · SPEC-657 · A-08-T01 (contract), A-08-T05/T06 (stubs), A-08-T08 (content), screen rows per A-08 §9 |
| Persona | Hannah Leclerc (Manager) |
| Flags | `audits.analytics`; runs behind `audits.fieldwork_agents` |
| Priority | P1 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

Every artboard is **built** (A-08 §2.1). Fixture-only parts are named in their row. 5 artboards plus one composed tab (Substantive, DF-05), fixture-only and never locked.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Preliminary · 2 unexplained | 14 lines; 8 over 10% **and** $116,250 (PM from provisional $155,000, decider Margaret Okonkwo); 6 explained, 2 unexplained (amber); interest 26.8% Within | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `granite-peak.analytics` |
| b | Agent running | Three run rows (code tie-out, `flux_explain`, "Prepare client questions" as code); tallies "Pending" | Sun Sep 13, 2026, 5:36 PM CT | E0 variant | D · C report-only (spinners masked) | planned · `granite-peak.analytics` |
| c | Ask client | O3 500, two cards from the firm template to Luis Ferrante → POR-05; editable, a person sends | Mon Sep 14, 2026, 9:24 AM CT | E0 variant | D · C report-only | planned · `granite-peak.analytics` |
| d | Answered | Inventory "Explained" with chip "Client answer Sep 16 · Luis Ferrante" + Accept | Wed Sep 16, 2026, 2:10 PM CT | E0 variant | D · C report-only | planned · `granite-peak.analytics` |
| e | Final analytics | Adjusted FY2026 vs audited FY2025 after 3 recorded adjustments; pre-tax income −114,480 (DV-5) | Mon Oct 26, 2026, 1:58 PM CT | E0 after adjustments | D · **C locked** | planned · `granite-peak.analytics` |
| s (composed) | Substantive tab | Same engine over the latest unadjusted TB with expectations (DF-05 frame composed from the Preliminary grammar) | Mon Sep 14, 2026, 9:24 AM CT | E0 variant | D · C report-only vs a (never locked) | planned · `granite-peak.analytics` (fixture-only) |
| loading | — | skeleton per the template's loading grammar | — | — | D | planned |
| error | — | the read failed: designed error with Retry (chapter 10 §10.3 kind 10) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3); a client principal always 404 on confirmation routes | — | — | — | planned |
| flag off | — | C-20 "not turned on" state for the screen's flag; never a blank pane | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/AUD-13/scenarios.ts` (A-08 §5.4), exported from the Python scenario (`make fixtures`, F-04-T31) and derived from the seed's footing figures, never typed by hand. Copy keys are `aud13.<state>.<element>` in the screen's `copy.ts`.

## API

Every state reads this endpoint set (A-08 §4.3; stubs in A-08-T05 / T06):

- `POST /v1/work-items/{wid}/analytics-sets` (`analytics.run`, 202)
- `GET /v1/analytics-sets/{aid}` · `GET …/lines/{pos}/provenance` (`analytics.read`)
- `PUT …/lines/{pos}/explanation` (`analytics.explain`; 422 `explanation_uncited`)
- `POST …/explanations/accept` (`analytics.accept`; not the author)
- `POST …/client-questions` (`client_question.send`)
- `PUT /v1/work-items/{wid}/prior-year-figures` (`analytics.configure`) · `GET …/export.xlsx` (`analytics.export`)

Matrix actions from `permission-matrix/{sampling,workpapers,assurance,identity}.yaml` (A-08-T03): every adopt, accept, approve, decide, send and close is a person's (`agent: deny`); every client principal is denied.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, e | C (locked; A-08-T37) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/AUD-13.spec.ts`) | data-stable frames |
| b | C (report only) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/AUD-13.spec.ts`) | masked (running analytics) |
| c, d | C (report only) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/AUD-13.spec.ts`) | — |
| host | D | — | audit bar 59, pane header 46, tiles 120×72 |

## Links

| From | To | Status |
|---|---|---|
| Any number | SHL-09 provenance | live |
| Source chip | SHL-08 | live |
| Ask client (2)… | POR-05 questionnaire | live |
| Accept | SHL-10 | live |
| Threshold ⓘ | AUD-07 materiality | live |
| Opens SHL-12 · sign off | SHL-12 | designed (handoff link graph) |
| Opens CLI-02 · client record | CLI-02 | designed (handoff link graph) |
| Opens KNW-03 · program editor | KNW-03 | designed (handoff link graph) |
| Opens AUD-03 · source documents | AUD-03 | designed (handoff link graph) |
| Opens AUD-29 · activity log | AUD-29 | designed (handoff link graph) |
| Opens AUD-06 · trial balance & mapping | AUD-06 | designed (handoff link graph) |
| Opens AUD-08 · risk assessment | AUD-08 | designed (handoff link graph) |
| Opens AUD-09 · internal control & ITGCs | AUD-09 | designed (handoff link graph) |
| Opens AUD-11 · sampling | AUD-11 | designed (handoff link graph) |
| Opens AUD-12 · Controls Testing — Revenue Cycle | AUD-12 | designed (handoff link graph) |
| Opens AUD-16 · summary of misstatements | AUD-16 | designed (handoff link graph) |

## Notes

No "$" in the statement table; negatives in parentheses with `aria-label` "negative …"; unexplained rows amber, never red; status is text. The threshold tooltip names the provisional materiality and the deciding partner and is keyboard reachable.

## Deviations

- DV-4 question cards are firm templates (database content) a person edits and sends; b's third run row is a code step.
- DV-5 e reads adjusted FY2026 vs audited FY2025 (README and built screen), not the spec's adjusted vs unadjusted.
- DV-3 closed data boundary shows DF-04.

## Acceptance

SPEC-657's criteria for this screen; each becomes a test named "AUD-13 acceptance: <criterion>".
