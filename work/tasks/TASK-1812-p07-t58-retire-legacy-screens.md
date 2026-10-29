---
id: TASK-1812
title: Retire the replaced legacy engagement screens and supersede their tests (P-07-T58)
spec: SPEC-321
acceptance_criteria: [AC-23, AC-24]  # ENG-01 and ENG-02 carry what the legacy index and layout did
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T58
branch: s13r-p07-t58
created: 2026-10-29
updated: 2026-10-29
---

## Objective
No route renders a replaced legacy screen (P-07 §8 Files, "Replaced"); the AC-test count does not fall without the approval line below (chapter 10, TEST-001).

## Plan
- Delete `apps/web/src/legacy/{Engagements,EngagementLayout,Setup,EngagementRecords,MyConfirmations,People,Contacts,RollForward}.tsx`.
- Keep `legacy/engagementTypes.ts` and `legacy/engagementLabels.ts`: their remaining readers are screens other epics retire (legacy Clients and Methodology; A-01's Overview and MapView), so they go with the last of those (DEC-904).
- Routes: `/engagements` and `/engagements/$engagementId` show the F-05-T19 flag-off state with `engagements.v2` off (never a legacy screen); `/` and `/home` with `home.dashboard` off redirect to `/engagements`; the record's `/setup` and `/people` children go (they rendered Setup and People); the overview child renders Overview without Setup's `DefaultToSetup`.
- `make seed` turns `clients.v2`, `engagements.v2` and `engagements.acceptance_v2` on for the Dev firm, so local development lands on ENG-01 (Ayush, 2026-10-29). E0 and staging keep their own flags until P-07-T59.
- `e2e/journey.spec.ts` (F-01-T08's setup-first walk over the legacy Setup page) becomes `test.fixme`: the v2 journeys (`eng-cli-core`, J02, CLI-06, J19) walk the same ground on fixtures and full stack once P-07-T59 turns the flags on in E0.
- Rollback: revert the PR; nothing persistent changes (the seed flags are local only).

## Approval (TEST-001; chapter 10 §10.3.3, QD-3)
Approved by Ayush, 2026-10-29 ("Build P-07-T58 next"; flag-off handling "Seed flags on"). Superseded vitest suites, each covered by the named AC suite:
| Removed | Tests | Superseded by |
|---|---|---|
| `legacy/Engagements.test.tsx` | 6 | ENG-01 (`screens/ENG-01/ENG-01.test.tsx`; SPEC-321 AC-23) |
| `legacy/spec025clients.test.tsx` | 2 | CLI-01 and ENG-03 wizard (`screens/CLI-01`, `screens/ENG-03`) |
| `legacy/spec025template.test.tsx` | 5 | ENG-03 type catalogue (SPEC-321 AC-25) |
| `legacy/spec025setup.test.tsx` | 6 | ENG-02 gates (`screens/ENG-02`; SPEC-321 AC-24) |
| `legacy/spec025states.test.tsx` | 8 | ENG-02 and CLI-08 artboard states |
| `legacy/spec025records.test.tsx` | 6 | ENG-02 record (AC-24) and CLI-08 team confirmations |
| `legacy/spec025independence.test.tsx` | 2 | CLI-08 (`screens/CLI-08`; SPEC-332) |
| `legacy/spec025rollforward.test.tsx` | 2 | ENG-13 (`screens/ENG-13`; SPEC-321 AC-30) |
| `legacy/spec017people.test.tsx` | 7 | ENG-05 team and roles (`screens/ENG-05`) |
| `legacy/spec016.test.tsx` ac5 and SPEC-017 ac7 | 2 | CLI-04 contacts (AC-26 to AC-29) and ENG-05 |
| `legacy/q03ledgerstates.test.tsx` roll-forward review and its tokens case | 2 | ENG-13 (`screens/ENG-13`) |

## Progress log
- 2026-10-29: built. Removed 8 screens and 48 vitest cases (table above); `legacy/Overview.tsx` loses its link to the retired `/people` route. `tsc`, eslint and prettier clean; web vitest 2326 of 2327 (`gallery/seed-fixtures` timed out under full-suite load and passes alone, 2/2); fixture journeys eng-cli-core, J02, KNW-01, J01 17 passed, 9 skipped (full-stack steps). The record's other tab routes (Planning, Fieldwork, Review, Workpapers and the rest) render nowhere now that no host has an outlet; their owning epics retire them.
