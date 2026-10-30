---
id: TASK-2402
title: T-01-T34 CLI-05 frontend part 2 (fixture mode), b, c, e, g
spec: SPEC-501
acceptance_criteria: [AC-11]
risk_zone: green
status: in-review
epic: T-01
plan_key: T-01-T34
branch: s19-t01-t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
CLI-05 part 2 in fixture mode: Authorizations c (8821 fieldset, masked CAF, the 8821-versus-2848
note and Draft Form 2848, State fieldset with Add), None on file g (Request Form 8821), Elections e
(Ridgeline) and Transcripts empty state b.

Acceptance: "Scenario tests for b, c, e and g pass, and no full CAF number or SSN appears in the
DOM."

## Scope
**In**: `apps/web/src/screens/CLI-05/` (sections, copy, scenarios, tests);
`apps/web/src/fixtures/seed/tax-profile.ts` (designees, Ridgeline, Santos);
`fixtures/scenarios/CLI-05.ts` (entities and sections); the gallery artboard's section;
`docs/screens/CLI-05.md`.
**Out**: Transcripts a (register and comparison, T-01-T43/T45); the live swap (T-01-T33); any
contract field (DEC-1452 lists what waits on T-01-T43).

## Plan
Files as in Scope, plus the decision log (DEC-1452). Migrations, registry, flags: none.
Tests: `CLI-05.test.tsx` part 2 — b, c, e, g each on its scenario, a page-text scan for SSN/CAF
shapes and 9+ digit runs, and the section switch.
Rollback: revert the PR.

1. [x] Fixtures. 2. [x] Sections and switching. 3. [x] Tests. 4. [ ] End review run.

## Progress log
- `2026-10-30` — Built on `s19-t01-t34` (build-only; tests run at the S19 end review).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1452 | words from election codes, empty transcripts until the list route, state form code from K-02 | no |

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review; T-01-T43/T45 add transcripts a and the election detail.
