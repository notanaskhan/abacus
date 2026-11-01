---
id: TASK-2622
title: T-01-T46 Playwright part 2 (j06 D, j06 relock, j28 3, five screen specs at 1400)
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: T-01
plan_key: T-01-T46
branch: s21-t01-t46
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"The specs pass in fixture mode on PRs and full stack nightly on staging, and j28's P0 core is
walkable by Fri Aug 20, 2027."

## Scope
- J06 part 2 (`e2e/journeys/J06-individual-1040.spec.ts`): j06 D (1 of 2 signed keeps Mark
  transmitted locked; both signed, the ERO may record; acks accepted, delivered to the portal; no
  Approve/Send/Sign) and j06 relock (TAX-09 e's import diff) on the gallery artboards in fixture
  mode, with axe and INV-1 to INV-5 per step; j28 3 is a named fixme (no Granite Peak 1120
  scenario or Isaac Moreau persona yet).
- Screen specs at 1400×900 with axe on every artboard: `e2e/screens/tax-09-engine-sync`,
  `tax-12-delivery`, `cli-05-tax-profile`, `adm-05-consents`, `adm-08-integrations`.
- Gallery artboards for TAX-12 (a–e, a2, c2) and ADM-08 (a–g), which had none.
**Deviations (DEC-1669)**: part 1 (T-01-T29, Sprint 19) is not built, so j06's earlier steps stay
where they are; j28 3 waits on a business-return scenario. Full stack and staging stay fixme with
the rest of J06 until E0 carries the delivery slice.

## Progress log
- 2026-11-01: written; specs run at the batch's end review.
- 2026-11-01 end review: ADM-05e's axe found the toolbar firm pill unnamed: scenario e used viewer
  `harold-stein`, which T-01 §2 calls a label error; e now views as Grace (scenario and foot test).
  CLI-05d passed twice on main (one navigation flake in the first run).
