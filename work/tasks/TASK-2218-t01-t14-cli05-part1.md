---
id: TASK-2218
title: T-01-T14 CLI-05 tax profile, part 1
spec: SPEC-501
acceptance_criteria: [AC-11]
risk_zone: green
status: done
epic: T-01
plan_key: T-01-T14
branch: s17-t01-t14
created: 2026-10-30
updated: 2026-11-01
---

## Objective
CLI-05 frontend part 1 at /clients/$clientId/tax-profile/:sub on the T2 cockpit (fixture mode):
rail rows with discs, Open notices band (planned link), identity band with masked SSN and Reveal
(logged) re-masking after 10 s, small Segmented, Consents section d with per-document sub-rows
and the partially signed banner f with Resend; agents-off copy per DF-04.

Acceptance (backlog row): "Scenario tests for d and f pass, the reveal leaves nothing in the DOM
after re-mask, and the consent row reads Use · AI disclosure (2 consents)."

## Done
- `screens/CLI-05/{index.tsx, copy.ts, scenarios.ts, CLI-05.test.tsx}`; route; manifest
  `fixture`; gallery.
- Fixtures: `seed/tax-profile.ts` (Whitley, Ferris; synthetic TINs), the tax-profile and reveal
  handlers, `scenarios/CLI-05.ts`.
- Contract (additive, regenerated): TaxProfileOut header and identity fields; ConsentOut
  `template_name` (DEC-1263). Stacked on T-01-T13 (ConsentOut signers).

## Progress log
- 2026-10-30: built in S17 Lane 2 on T-01-T13; tests run in the end review.
- 2026-11-01: merged to main in #790 (621488445).
