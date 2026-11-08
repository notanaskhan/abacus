---
id: TASK-6405
title: A-05-T23 follow-ups - Raise exception opens SHL-15, the Flag records the handoff's finding, provision cards, HR record from the citation
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T23
branch: s26p-a05-t23-ebp03-2
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-08
updated: 2026-11-08
---

# TASK-6405 · A-05-T23: Raise exception opens SHL-15, Flag records the finding, provision cards

TASK-5015 (my DEC-2328) wired Raise exception… to record an AUD-15 finding under a title I wrote. The handoff has Raise exception… open SHL-15 and the row's Flag record the finding, titled "Missed deferral opportunities — auto-enrollment not applied (N participants)". The provision cards were not drawn, and a row's HR record depended on the agent writing its id.

AC-1: "Raise exception…" opens SHL-15 on a new issue about the eligibility test (the host's overlay), and records nothing itself.

AC-2: An exception row's Flag records one AUD-15 draft finding titled with the handoff's words and the sample's exception count; once raised, the Flag stops offering it.

AC-3: EBP-03 draws the handoff's "Auto-Enrollment Provisions" and "Auto-Escalation Provisions" cards from EBP-02's provisions, and a row's HR record is the version its hire date's first citation quotes.

## Decisions (DEC-2955)
- Corrects DEC-2328: the finding is the Flag's and its title is the handoff's; Raise exception… is SHL-15's.
- The provision cards read `GET …/ebp/plan-reviews/current` (EBP-02's review), read-only.

## Known limits
- The finding's count is the sample's exceptions. The handoff's "(4 participants)" is the population (`eligible_not_enrolled_no_optout`), which needs every participant's date of birth and deferral history read by code; that read is not wired.
- `recordkeeper_entry_on` stays empty: no recordkeeper enrollment report is imported to compare against.

## Progress log
- 2026-11-08: built on main a801fff01; tests written, run at the S26 partials end pass.
