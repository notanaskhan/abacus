---
id: TASK-1400
title: The review notes service, raise, respond, clear and withdraw with sealed bodies (P-04-T21)
spec: SPEC-360
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T21
branch: s11-review
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The C3 note routes (`GET|POST /v1/review-notes`, `GET /v1/review-notes/{id}`,
`POST .../respond|clear|withdraw`) answer 501. Make them live on the one notes service, with
sealed bodies and anchors, `review_note_raised` to the assignee, and open notes feeding R-SO-4.
Acceptance: open notes on RA!C14 and RA!C22 block L2 with `open_review_notes` and count 2, and
clearing both lets the same reviewer sign.

## Plan
- **Migration 0210** (`0210_review_notes_sealed`, down 0182): `reviewable_notes.body` nullable
  with exactly one of `body` / `body_sealed`; `reviewable_note_events.body_sealed`, one body form
  at most, a body required only on raised/responded/reopened; the app may insert `id` on both
  (the seal is bound to the row). Reversible: the downgrade refuses while sealed rows exist.
- **Service** `review/notes.py`: every new note and event body is sealed (`kernel.crypto.seal`,
  bound to the note or event id); SPEC-313 plaintext rows still read. C3 functions: `list_notes`
  (`visible(review_note.read)`, no bodies, per-status counts), `note_detail` (authorise, access
  event `review_content.read` before the body leaves), `raise_on_target` (target through
  `reviewable_facts`, fail closed; anchor kind and ref; assignee must be on the team), `respond`,
  `clear` (raiser or partner, human only), `withdraw` (raiser only, open/responded only). Every
  write: lock, authorise, event row, status, audit, outbox (`review_note.raised|responded|
  cleared|withdrawn`). The SPEC-313 routes keep working through the same service.
- **R-SO-4**: unchanged (`notes_of_target`, open = open or responded); withdrawn and cleared
  notes stop blocking. Comments are P-05's and never read here (DEC-29).
- **Notification**: `review_note.raised` -> kind `review_note_raised` to the assignee (or, with
  none, the target's preparers), never the raiser; walls re-checked by notifications.
- **Registries**: audit target `review_note` owned (engagement); activity entries; error codes.
- **Tests first**: `tests/integration/test_p04t21_review_notes.py`.
- **Rollback**: revert the branch and downgrade 0210 (refused while sealed bodies exist: then
  keep the migration and revert only the code, which reads both forms).

## Progress log
- 2026-10-27: planned.
- 2026-10-27: built (acceptance tests written first, run in the end-of-batch targeted pass). Decisions DEC-500 to DEC-504; ED-150. Generated client and matrix regenerated.
