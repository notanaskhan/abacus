---
id: SPEC-313
title: "Review notes on any reviewable, trial balance sign-offs, the sign-off matrix and the review gate (G5)"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-136, ADR-140]
related_specs: [SPEC-041, SPEC-308, SPEC-309]
created: 2026-10-21
updated: 2026-10-21
---

## 1. Summary
This is P-04's review grammar beyond sign-offs, and A-06's AUD-17.

- A fail-closed `register_reviewable` slot lets owners list what can be reviewed on an engagement, each with its current content hash. Working papers register from workpapers; trial balances register from assurance.
- Notes and sign-offs work on any reviewable.
- The matrix and G5 read every registered provider.

Migration 0076 adds `reviewable_notes` and `reviewable_note_events`, both insert-only. Fieldwork's procedure notes (`review_notes`, SPEC-041) move onto these later (DEC-110).

## 2. Acceptance criteria
- **AC-1 Read.** `GET /v1/engagements/{id}/review-notes?target_type=&target_id=` (`workpaper.read`) returns notes with their status, events and target code. The status is the newest event's: open, answered or cleared.
- **AC-2 Raise.** `POST …/review-notes` (`review_note.raise`: reviewers, the EQR included) raises a note on a registered reviewable, with an optional anchor (a cell or an account). An unknown target gives 404.
- **AC-3 Events.**
  - `…/respond` (`review_note.respond`) needs a body.
  - `…/clear` and `…/reopen` (`review_note.clear`) can be done only by the raiser or the engagement partner (409 `not_the_raiser`). Reopen needs a reason, and only applies to a cleared note.
  - Events are append-only. The agent is denied all of these.
- **AC-4 Matrix.**
  - `GET …/review-matrix` returns every reviewable with its five levels (signer, stale, required), open notes, missing required levels, and a status: not started · needs sign-off · changed after sign-off · open notes · complete.
  - The required levels are L1 and L2. K-02 will set more by area and risk.
- **AC-5 G5.**
  - The review module registers G5. It is met when there is at least one reviewable and every one has its required levels signed on its current content, with no open notes.
  - Blockers name what's missing. A provider failure leaves G5 unmet (`review_unavailable`).
- **AC-6 Sign-offs.**
  - L2 and above are refused while the target has an open or answered note (409 `review_notes_open`).
  - Trial balances can be signed: `POST …/trial-balances/{tb}/sign-offs/{prepare|review|manager|partner|eqr}`. The hash covers the current version's fingerprint and every account's area and WP ref; tie-out definitions aren't in it yet. The trial balance view carries its levels.
- **AC-7 Web.**
  - The working paper gets a Review notes panel (raise on the selected cell), and cells with an open note are marked.
  - The trial balance gets Sign-offs and Review notes (raise on a single selected account).
  - A new "Sign-offs" tab shows the gate (Review complete, or Review open with what's left), the matrix with links, and every note.
