---
id: TASK-1274
title: ENG-05 Team and roles inside ENG-02 with the inspector, states a–e (P-07-T39)
spec: SPEC-332
acceptance_criteria: [AC-13, AC-14, AC-15, AC-16]
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T39
branch: s9b-kit-screens
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Scenarios a to e pass with axe and hours foot to 172.0 and 24.0." ENG-05 as ENG-02's Team tab:
T1 with the 330 inspector, the blocked-assignment dialog, the EQR inspector and the Replace EQR
picker with eligibility, the team approval footer, the portal toggle, the Request confirmations
sheet, and the agent row without minutes.

## Scope
**In**
- `apps/web/src/domain/engagements/team.ts` (L3, generated client only): roster, team approval,
  team candidates, EQR candidates; writes add, change role, edit hours, remove, portal flag,
  reminders, replace EQR; hours in tenths (no float sums).
- `apps/web/src/screens/ENG-05/{index.tsx, copy.ts, scenarios.ts, ENG-05.test.tsx}`.
- `apps/web/src/screens/ENG-02/index.tsx`: the Team tab hosts ENG-05 over the subbar and tabs (as
  CLI-02 hosts CLI-04); the interim roster host (`TeamHost`, DEC-272) is gone, and its ENG-02 test
  now asserts the same three people and roles in ENG-05's table.
- Fixtures: `fixtures/seed/team-roles.ts`, `fixtures/handlers/team-roles.ts`,
  `fixtures/scenarios/ENG-05.ts`, `fixtures/team-roles.foot.test.ts` (172.0 and 24.0; the
  confirmed team is AUD-02's rail MO · TW · HL · MD · AC).
- Gallery `ENG-05` artboards a–e; `e2e/screens/ENG-05.spec.ts` (axe); manifest comment.
- `docs/screens/ENG-05.md`: states, deviations, open gaps.

**Out**
- Fields the roster does not carry (office, title, pronoun, confirmation date), the EQR approval
  read, role history: open gaps in the contract (a backend contract change, not this FE task).
- Actual hours (I-04) and agent-minutes (P-10), per P-07 §2.1.

## Definition of done
- [x] 18 tests in `ENG-05.test.tsx` (a–e, acceptance, writes, loading, error, walled, no add right)
- [x] 2 footing tests; ENG-02's 29 still pass
- [x] tsc, eslint and prettier for the touched files in `apps/web`
- [ ] Playwright with axe (`e2e/screens/ENG-05.spec.ts`): not run locally — chromium 1243 wanted,
      1248 cached (S9 brief)

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-386 | ENG-05 as built on the roster the API returns: the deviations and gaps in the contract, c's viewer, the composed dialogs | no |

## Progress log
- 2026-10-26: built on fixtures over the live team routes (all exist in the generated client).
  vitest 18 + 29 (ENG-02) + 2 (foot) + gallery/route/scenario parity suites green; tsc, eslint and
  prettier clean. Playwright skipped (chromium mismatch). Built `packages/api-client` types
  (`build:types`, gitignored dist) so `tsc` resolves the generated client.
