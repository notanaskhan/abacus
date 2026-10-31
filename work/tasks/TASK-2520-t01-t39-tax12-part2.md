---
id: TASK-2520
title: "T-01-T39 TAX-12 frontend part 2 (fixture mode): c, c2, d, e and the packet editor"
spec: SPEC-501  # AC-11; docs/screens/TAX-12.md
acceptance_criteria: [AC-11]
risk_zone: green
status: in-review
epic: T-01
plan_key: T-01-T39
branch: s20b-t01-t39
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
TAX-12 frontend part 2 (fixture mode): c2 Mark transmitted confirm dialog for Daniel only, d
Accepted with the ack timeline, Delivered to portal and the planned estimate-reminder row, e
Rejected with the reject code and engine text, Create issue to TAX-06 and the agent fix card
rendered only in fixture builds, packet editor with voucher toggles, Regenerate letter and
Approve.

Acceptance (backlog row): "Scenario tests for c2, d and e pass, the confirm dialog lists the four
jurisdictions and Sep 18, 2026, and the agent card is absent in production builds."

## Plan (green)
- Fixtures (`fixtures/seed/tax/feld-delivery.ts`, `handlers/tax-compliance.ts`): the envelope
  completes from c; d's four acknowledgements; e's federal rejection; c2 grants Daniel
  `transmission.record`; transmission, packet patch, regenerate and approve handlers.
- `screens/TAX-12`: the gate (Daniel's confirm through C-22, Grace's "Waiting for Daniel Reyes to
  transmit" with Notify), the acknowledgment timeline, Rejected with Create issue, the fix card
  behind `FIXTURE_BUILD` (`VITE_FIXTURES`), rail sub-lines and status words, and the packet
  editor (voucher toggles, Regenerate letter, Approve when allowed). Copy verbatim from the
  handoff.
- Tests: c, c2, d, e scenarios and the fixture-build gate.

## Notes
- The handoff's gate label has no ellipsis, so the button carries `aria-haspopup="dialog"`
  rather than the kit's `opensDialog` (which requires "…").
- The packet editor sends `seen_version` 1: `DeliveryOut` carries no packet version. A live swap
  reads the packet (additive `version` on DeliveryOut) with T-01-T41.
- Two fixture tests (`GET /v1/binders` Feld row, SHL-12 scenarios) fail on main without this
  change.

## Progress log
- `2026-10-31` — Built on `s20b-t01-t39` off main 1d73f5d8e. TAX-12 tests 10 passed.
