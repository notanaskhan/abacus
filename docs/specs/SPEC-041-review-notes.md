---
id: SPEC-041
title: "Fieldwork, part 4: review notes — a reviewer raises a note on a row or a workpaper, the preparer responds, the reviewer clears it; open notes block reviewer sign-off"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-131]
related_specs: [SPEC-037, SPEC-038, SPEC-040]
created: 2026-10-20
updated: 2026-10-20
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.

## 1. Summary
Review notes are the reviewer's formal points (epic P-04, the plan's AUD-17), distinct from comments, which never block (DEC-29).

On a fieldwork procedure:
- a reviewer raises a note on a tested row or on the workpaper;
- the preparer responds;
- the reviewer who raised it clears it, or responds again.

While a row has a note that isn't cleared, nobody can sign that row as reviewer. While the procedure or any of its rows has one, nobody can sign the workpaper as reviewer.

## 2. Actors
| Actor | Can |
|---|---|
| Senior, manager, engagement partner, EQR (`reviewer`) | Raise a note; clear their own |
| Staff, senior, manager, engagement partner | Respond |
| Agent | Nothing (`agent: deny`) |
| Client | Never sees notes |

## 3. Acceptance criteria
- **AC-1** Given a selected procedure, when a reviewer raises a note on a row of the current selection or on the procedure (the workpaper), then the note records the target, the text (1–2,000 characters), who raised it and when. It starts **Open**, and an audit event is written.
- **AC-2** Given an Open note, when a staff member, senior, manager or partner responds, then the response is recorded and the note is **Responded**. The raiser can respond again, which makes it **Open** again.
- **AC-3** Given a note, when the person who raised it clears it, then it's **Cleared**. Anyone else is refused with `not_note_raiser` (409). A cleared note can't be responded to or cleared again (409 `note_cleared`).
- **AC-4** Given a row with a note that isn't cleared, when anyone signs that row as reviewer, then it's refused with `notes_open` (409). Preparer sign-off is never blocked by a note.
- **AC-5** Given a procedure where it or any of its current rows has a note that isn't cleared, when anyone signs the workpaper as reviewer, then it's refused with `notes_open` (409).
- **AC-6** Notes and responses are never edited or deleted (insert-only). A note's state is worked out from its newest event.
- **AC-7** Each row shows its open notes. The workpaper pane shows "Review notes (n open)". A drawer shows a thread: raise, respond, clear.
- **AC-8** Home's "Waiting on you" adds "Respond to n review notes" for Open notes on procedures where the person prepares, and "Clear n responded notes" for notes they raised that are Responded.

## 4. Data
- `review_notes` (insert-only): `tenant_id`, `engagement_id`, `procedure_id`, `selected_item_id` (null for the workpaper), `body`, `raised_by`, `created_at`.
- `review_note_events` (insert-only): `tenant_id`, `review_note_id`, `kind` (`responded` | `reopened` | `cleared`), `body` (required for responded and reopened), `by`, `created_at`.

## 5. Permissions
- `review_note.raise`: engagement_partner, manager, senior, reviewer; agent deny; independence required.
- `review_note.respond`: engagement_partner, manager, senior, staff, reviewer (the raiser replying); agent deny; independence required.
- `review_note.clear`: engagement_partner, manager, senior, reviewer; agent deny; independence required. The service also requires the raiser.

## 6. Decisions (founder, 2026-10-20: "approved, proceed")
- **Q1** The EQR can raise and clear notes (review is their job); they still never sign rows (SPEC-040).
- **Q2** Notes don't block preparer sign-off. They block the reviewer's sign-off of the row and of the workpaper.
- **Q3** Notes on request items and documents come later, on the same tables with a new target.
