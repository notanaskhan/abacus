# AUD-12 · Testing workspace · details · controls · JE

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/testing` (`?variant=je|details|controls&test=<id>&entry=<ref>&ov=expand-testing`; `?ov=signoff` SHL-12 L1, `?ov=exception` SHL-15) |
| Template and host frame | T2 RecordCockpit with the Viewer dock (rail 330 · canvas 536 · viewer 490); audit bar 59 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-12 Testing workspace - details - controls - JE (`revision.md` R2 wins over `spec.md`)/` |
| Epic and tasks | A-08 · SPEC-657 · A-08-T01 (contract), A-08-T05/T06 (stubs), A-08-T08 (content), screen rows per A-08 §9 |
| Persona | Simone Baptiste (Audit Senior) on every state (DV-1: b and h keep her as the README states) |
| Flags | `audits.fieldwork_testing` (expansion inside it); runs behind `audits.fieldwork_agents` |
| Priority | P1 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

Every artboard is **built** (A-08 §2.1). Fixture-only parts are named in their row. 8 artboards (a–e original, f–h R2).

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | JE testing | Granite Peak FY2026 JE test: 18,426 entries tie 214 of 214 · $0.00; criteria 142 · 38 · 61 · 17 · 9 → 236 unique; 40 selected (34 by score ≥ 61 + 6 unpredictable), approved by HL Oct 2; JE-26-17994 support lit | Tue Oct 6, 2026, 11:20 AM CT | E0 | D · **C locked** | planned · `granite-peak.je-testing` |
| b | Test of details · Northwind | Contribution testing, Dec 12, 2025 payroll, 25 participants (seed `0x5E2A91`); rows 8 and 15 flagged → EBP-03 | Tue Oct 6, 2026, 11:20 AM CT | E0 | D · C report-only | planned · `northwind.contribution-testing` |
| c | Test of controls | Credit approval, 25 sales orders, 0 deviations; UDL 8.8% < tolerable 10% | Tue Oct 6, 2026, 11:20 AM CT | E0 | D · **C locked** | planned · `granite-peak.controls-credit-approval` |
| d | Agent testing | A `fieldwork_attribute` run on the 40: spinner discs, viewer skeleton until each item lands (C6 v2) | Tue Oct 6, 2026, 11:20 AM CT | E0 variant | D · C report-only (spinners masked) | planned · `granite-peak.je-testing` |
| e | Exception raised | JE-26-17950 (no independent approval for the $50,000.00 bonus accrual reduction): brick Flag, red-tint Exception, AUD-15 finding | Tue Oct 6, 2026, 11:20 AM CT | E0 variant | D · **C locked** | planned · `granite-peak.je-testing` |
| f | Expand testing (R2) | O3 500 over e: next 10 by score, 0 unpredictable, "Selected becomes 50 · code recomputes coverage", rationale (agent draft, C-31), approver Hannah Leclerc | Tue Oct 6, 2026, 11:20 AM CT | E0 variant | D · C report-only | planned · `granite-peak.je-testing` |
| g | Awaiting approval (R2) | "Selected entries · 40 + 10 pending approval (HL)"; footer pill "Waiting on Hannah Leclerc"; the 40 unchanged | Tue Oct 6, 2026, 11:20 AM CT | E0 variant | D · C report-only | planned · `granite-peak.je-testing` |
| h | Expand · Northwind (R2) | State b with rows 8 and 15 flagged: Expand testing primary; "Add participants" ⇕ 10, same approval rule | Tue Oct 6, 2026, 11:20 AM CT | E0 variant | D · C report-only | planned · `northwind.contribution-testing` |
| loading | — | skeleton per the template's loading grammar | — | — | D | planned |
| error | — | the read failed: designed error with Retry (chapter 10 §10.3 kind 10) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3); a client principal always 404 on confirmation routes | — | — | — | planned |
| flag off | — | C-20 "not turned on" state for the screen's flag; never a blank pane | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/AUD-12/scenarios.ts` (A-08 §5.4), exported from the Python scenario (`make fixtures`, F-04-T31) and derived from the seed's footing figures, never typed by hand. Copy keys are `aud12.<state>.<element>` in the screen's `copy.ts`.

## API

Every state reads this endpoint set (A-08 §4.3; stubs in A-08-T05 / T06):

- `POST /v1/work-items/{wid}/je-tests` (`je_test.create`; 409 `population_not_tied`)
- `GET /v1/je-tests/{jid}` · `GET …/entries` (`je_test.read`)
- `PUT /v1/je-tests/{jid}/criteria` · `…/posting-user-roles` (`je_test.configure`)
- `POST /v1/je-tests/{jid}/score` (`je_test.score`, 202)
- `POST /v1/je-tests/{jid}/selection` (`sample_set.create`)
- `POST /v1/sample-sets/{sid}/expansions` (`sample_expansion.request`; 422 `expansion_rationale_required`, `approver_required`, `approver_not_eligible`)
- `POST /v1/sample-expansions/{xid}/decide` · `…/withdraw` (`sample_expansion.decide`, condition `is_named_approver`; `sample_expansion.request`)
- `POST /v1/work-items/{wid}/tests`, `GET /v1/tests/{tid}/items`, `GET …/items/{iid}`, `PUT …/results/{attr}` (A-05 `test.*`)
- `POST /v1/tests/{tid}/runs` (`test.run`) · `POST …/adopt` (C3 L1) · `POST …/items/{iid}/exception` (`finding.create`) · `POST …/deviations` (`test.mark`) · `GET …/export.xlsx` (`test.export`)

Matrix actions from `permission-matrix/{sampling,workpapers,assurance,identity}.yaml` (A-08-T03): every adopt, accept, approve, decide, send and close is a person's (`agent: deny`); every client principal is denied.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, c, e | C (locked; A-08-T37) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/AUD-12.spec.ts`) | data-stable frames |
| b, f, g, h | C (report only) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/AUD-12.spec.ts`) | — |
| d | C (report only) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/AUD-12.spec.ts`) | spinner discs and the viewer skeleton masked (ch. 04 §9.3) |
| host | D | — | audit bar 59, pane header 46, drawer 480, sheet 500 |

## Links

| From | To | Status |
|---|---|---|
| Value chip | SourceViewer region (in-screen, MatchProvider) | live |
| Adopt results (L1)… | SHL-12 | live |
| Raise exception… | SHL-15 → AUD-15 | live |
| Review in package | SHL-19 | fixture-only (DV-2, K-04) |
| Flag → EBP-03 | EBP-03 | live |
| Rail rows | AUD-03 · AUD-06 · AUD-07 · AUD-08 · AUD-04 · AUD-09 · AUD-11 · AUD-29 | live where built, else planned |
| NetSuite GL detail | SHL-08 | live |
| Opens CLI-02 · client record | CLI-02 | designed (handoff link graph) |
| Opens KNW-03 · program editor | KNW-03 | designed (handoff link graph) |
| Opens EBP-01 · plan profile | EBP-01 | designed (handoff link graph) |
| Opens AUD-10 · service organizations & SOC 1 | AUD-10 | designed (handoff link graph) |
| Opens EBP-02 · plan provisions review | EBP-02 | designed (handoff link graph) |
| Opens EBP-06 · investments & certification | EBP-06 | designed (handoff link graph) |
| Opens EBP-05 · distributions & loans | EBP-05 | designed (handoff link graph) |
| Opens EBP-08 · participant accounts | EBP-08 | designed (handoff link graph) |
| Opens EBP-09 · admin expenses & compliance | EBP-09 | designed (handoff link graph) |
| Opens EBP-07 · Form 5500 tie-out | EBP-07 | designed (handoff link graph) |

## Notes

Value chips are the only source links (INV-2). The lit region gets a 2 px ring and an `aria-live` description, not colour alone; criteria rows are toggle buttons with `aria-pressed`; the criteria table filters and the footer carry the selection (no basket, DF-05). Weekend dates are true weekends; Fri Jul 3, 2026 reads "Holiday". A firm with a closed data boundary shows DF-04 in the run area (DV-3).

## Deviations

- DV-1 b and h persona is Simone Baptiste (README); the Northwind J03 walk keeps Marcus Delaney.
- DV-2 "Review in package" renders in fixture scenarios for parity; live only when K-04 registers `review_packages`.
- DV-3 closed data boundary: DF-04 "AI isn't available for real client data yet"; code steps still run.

## Acceptance

SPEC-657's criteria for this screen; each becomes a test named "AUD-12 acceptance: <criterion>".
