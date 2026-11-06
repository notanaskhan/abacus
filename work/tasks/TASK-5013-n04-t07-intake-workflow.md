---
id: TASK-5013
title: N-04-T07 remainder - NoticeIntakeWorkflow, client and return match, authorization, duplicates, attach
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T07
branch: s26r-n04-t07-intake
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-06
updated: 2026-11-06
---

# TASK-5013 · N-04-T07: the intake's read

TASK-3218 built the intake service and left the read out. This closes the row's code gaps.

AC-1: the Santos CP14 reads eight fields from P-11's form extraction, a 0.71 respond-by stays low
confidence, and Create notice still answers 409 until a person confirms it.

AC-2: the client is matched by last four and name (one matched, several a pick, none the picker),
the return by entity and year, the authorization from CLI-05's register, and a repeat (entity, code
and date, or the same bytes) is flagged.

AC-3: a refusal or a file no map covers opens manual entry with the reason in words; ten minutes
without text fails to entering the fields; nothing is guessed.

## Decisions (DEC-2326)
- `NoticeIntakeWorkflow` (`notice_intake:<tenant>:<intake>`, interactive) starts from the outbox.
- The reason for manual entry is a code on the intake's `match` (`manual_reason_code`): no migration.
- P-11's map keys are translated to the notice's field keys in `intake_read._FROM_MAP`.

## Known limits
- No map carries the taxpayer's name, so code's match is `tin` until one does (`name_tin` is built
  and tested). No map reads the form either, so the return matches on entity and year.
- A file whose text was ready before the intake, with no map and no recorded refusal, waits out the
  ten minutes and then fails to entering the fields.
- Attach closes the intake on the chosen notice and records it; it does not move the file onto the
  notice's work item (no evidence API re-files a stored version). An inbox-only intake has no version
  to read, so it opens in manual entry.
- `notices.responder` mode `extract` is not called for an unmapped notice: it stays manual entry.
- Create anyway records that it went past a duplicate; the contract has no reason field yet.
- Functions (preparer, reviewer, signer) are not copied at Create notice.

## Progress log
- 2026-11-06: built on main 49922a2fd; integration, unit and replay tests pass locally.
- 2026-11-06: the end pass moved the two notification kinds into the catalogue (its own test pins the set and each needs an email sentence).
