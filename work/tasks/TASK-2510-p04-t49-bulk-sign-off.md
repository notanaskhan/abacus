---
id: TASK-2510
title: P-04-T49 SHL-12 f bulk sign-off, sign-off slots that open SHL-12, TPL-02 dock decision card unmask
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T49
branch: s20-p04-t49
created: 2026-10-30
updated: 2026-10-30
---

## Objective
[AC-1] "Bulk shows Sign off 3 as Reviewer (L2) with 3 excluded rows and their reasons, and clicking
any slot opens SHL-12." (backlog row; P-04 §3 F2, R-SO-7; F-05 R4.)

## Plan
- `apps/web/src/screens/SHL-12/Bulk.tsx` → `BulkSignOffSheet`: reads each picked workpaper's
  eligibility at the level (`useBulkEligibility`), derives the exclusion in words from the server's
  checks and ladder ("Waiting on inputs" with a half disc when no L1 yet, "1 open note", "You
  prepared this"), disables and unticks excluded rows, CTA "Sign off N as Reviewer (L2)" as a
  HumanAction, `POST /v1/sign-offs:bulk` with an Idempotency-Key and the seen hashes
  (`useBulkSignOffWrite`), then each item's result ("Signed" or the exclusion words).
- Seed: SHL-12 f's six workpapers (`BULK_ELIGIBILITY`, `BULK_TARGET_IDS`); `BULK_F` reordered to
  the sheet's rows (exclusion codes unchanged); review handlers match frames on query values.
- `packages/ui` `SignOffSlots` (ladder): never signs; every slot level and the next "Sign off…"
  call `onOpenSignOff(level)` (renamed from `onSignOff`).
- `DecisionCard` dock variant (`openDecision`): read-only options, one "Open decision" control;
  TPL-02c's dock shows SHL-11 frame 5's card (F-05 R4 unmask); DECISIONS.md row.
- Rollback: revert; no backend change.

## Acceptance
| Check | Test |
|---|---|
| 3 excluded in words; CTA "Sign off 3 as Reviewer (L2)"; no write before the click | `apps/web/src/screens/SHL-12/SHL-12.bulk.test.tsx` |
| The click sends the three eligible targets; per-item results | same |
| Slots and Sign off… open SHL-12 only | `packages/ui/src/gates/gates.test.tsx` (P-04-T49 cases) |
| Dock decision card cannot decide | same |

## Progress log
- 2026-10-30: built (tests first, run at the end review). DEC-1559.
