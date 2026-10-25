---
id: TASK-1215
title: AUD-06 fixture scenarios a–h plus loading, empty, newer-TB, error and not-allowed (A-02-T05)
spec: SPEC-333
acceptance_criteria: [AC-29]
risk_zone: green
status: done
epic: A-02
plan_key: A-02-T05
branch: s8b-audits-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"/components/screens/AUD-06?st=a..h renders each artboard's persona, clock and figures, and footing assertions (six funds 14,895,000.00; AJE-1 48,600.00) pass on the fixtures."

## Plan
- `apps/web/src/fixtures/seed/aud06.ts`: Northwind views b, c, d (Final with AJE-1), the Investments leadsheet (Δ% half-even), the three ties with the rollforward formula; Harlow & Pike Manufacturing Interim (g); Granite Peak FY2026 (h, newer, empty).
- `apps/web/src/fixtures/scenarios/AUD-06.ts`: `tbHandlers` for the C9 v1 reads (list, layer view with `layer_unavailable`, checks, leadsheet by area, candidates; a wall answers 404) and the 13 scenarios with OPENS.
- `apps/web/src/screens/AUD-06/{scenarios.ts, artboard.tsx, AUD-06.test.tsx}`; gallery registration.

## Progress log
- 2026-10-25: built; 20 AUD-06 tests pass (every view and list validated against the OpenAPI document; six funds 14,895,000.00; AJE-1 33,540.00 + 15,060.00 = 48,600.00; Final net assets 16,861,000.00; off 1,560.00; leadsheet Δ/Δ% exactly as the handoff; Harlow 86,000,000 and net income 3,400,000; Granite Peak 26,410,000 and 71,910,000; frames a–h render persona, clock and figures). Decisions and derived figures in DEC-342. The scenario export (F-04-T31) should take these over when it renders Granite Peak and Harlow & Pike.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-342 | Contract gaps (b draft, leadsheet subtotal, f eligibility) and the derived figures | No |
