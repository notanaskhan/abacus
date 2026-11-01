---
id: TASK-2540
title: "N-02-T37 live swap, repo side: the composer reads sent and signed from the letter envelope"
spec: SPEC-381  # N-02 §3.11; ENG-04 d, e; DEC-1574
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T37
branch: s20e-eng04-live
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Backlog row: "on staging the Ridgeline letter moves Draft to Partner approved to Sent." The
screen already reads the live composer; the read left `sent_at` and `signers[].signed_on` empty
(DEC-1574), so d and e could not render from live data.

## Plan
- `engagements.letter_send`: the `LetterSigning` port; `signatures.sources.envelope_signing`
  registers it; `letters.composed_letter` fills `sent_at`, `signed`, `signed_on` (DEC-1581).
- Test: `backend/tests/integration/test_n02t37_letter_live.py`.

## Progress log
- 2026-11-01: built; the new test and the N-02-T33/T35 suites pass (11).
  Hosted: flip `engagements.letter_composer` on staging and walk the Ridgeline letter.
