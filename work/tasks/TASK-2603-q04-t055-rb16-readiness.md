---
id: TASK-2603
title: Q-04-T055 RB-16 busy-season readiness runbook (operator half)
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T055
branch: s21-q04-t055
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Write RB-16 sections 1 to 8 (chapter 06; ADR-075, P-29): the R4 checklist with an owner per step,
extended on-call, deadline-week rules, mini-freezes, provider rate-limit requests and the Tuesday
slot, and link it from the R4 dossier template.

- **[AC-1]** "RB-16 is merged with owners per step and linked from the R4 dossier template."

## Scope
**In**: `docs/runbooks/RB-16-busy-season-readiness.md`; the runbooks index row;
`abacus_tools.go_live_dossier` Operations item `operations-5` and the regenerated
`docs/ops/go-live/_TEMPLATE.md`; DEC-1653.
**Out**: the partner-facing section (Q-04-T056); the rehearsal (Q-04-T057); the extended rota itself
(Q-04-T066); the R4 review (Q-04-T063).

## Plan
Sections 1–8 from the runbook template; R4 checklist as a table (step, owner, evidence, due);
provider quota table; window rules as the operating procedure of `docs/ops/release-windows.md`.
Rollback: revert the PR.

1. [x] Runbook. 2. [x] Dossier link and template. 3. [x] Dossier test and validate_docs run once
(10 passed; clean). 4. [ ] End review.

## Progress log
- `2026-10-30` — Written on `s21-q04-t055`. The go-live dossier unit tests (10) and `validate_docs`
  ran once, green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1653 | R4 step owners and due dates; quota sizing; dossier operations-5; Tuesday-slot procedure | no |

## Handoff
- **Current state:** written, PR open, held for the batch.
- **Exact next step:** Q-04-T056 adds the partner section; Q-04-T057 rehearses it on staging.
