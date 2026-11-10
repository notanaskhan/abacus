---
id: TASK-6407
title: A-04-T28 remaining planning events - 4:52 PM RA reviewed, Oct 6 materiality v3, planning with review and completion
spec: SPEC-620
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T28
branch: s26p-a04-t28-scenario2
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-08
updated: 2026-11-08
---

# TASK-6407 · A-04-T28: the planning events that can load without the agent runs

TASK-3233 loaded Northwind's planning day up to the 4:40 PM approval. This adds the two events it left out that need no agent run, and fixes two bugs that made the `planning` slice fail when loaded with the review and completion slices.

AC-1 (AUD-05 d): Marcus Delaney's Risk Assessment paper (RA-100) exists from 10:14 AM on Sep 14; he signs L1 at 4:45 PM and Hannah Leclerc reviews it at 4:52 PM, so RA-100 carries one L1 by MD and one review by HL.

AC-2 (AUD-07 d, AC3.6): on Oct 6 Hannah raises the materiality reassessment and Margaret records "No change", so the reassessment card is decided and materiality reaches v3. Each step is skipped when the review slice already wrote it.

AC-3: `--slice planning` loads together with `review` and `completion`. The completion slice reuses RA-100 and its two sign-offs instead of failing on them.

## Decisions (DEC-2957)
- Hannah's 4:52 PM review is her L3. AUD-05 d says "L2", but AUD-17 draws her on RA-100 at L3, and DEC-2428 already follows AUD-17. The pill reads "Reviewed · HL" either way.
- Marcus's L1 at 4:45 PM is a made-up time. The handoff draws only the review, and an L3 needs a current L1.
- RA-100 is the completion slice's matrix row (title, kind, creator). Its `paper_created` skips a paper that already exists, and its `matrix_signed` treats AlreadySigned (same person, level and content) as that sign-off.
- Fixed a load-order bug: the loader orders events at the same instant by handler order. The planning slice's 11:12 AM materiality decision ran before the review slice's, so the review step found no card. The planning slice's skip-if-done kinds now come after the review slice's kinds.
- Fixed a second bug: the planning slice's EBP-140 had no kind, so the completion slice's Send to Findings failed with `route_not_available`. EBP-140 is now `internal_control`.

## Not built (no data or needs an agent run)
- 9:27 AM materiality v1: the handoff gives no proposer or figures for a version before the review slice's 10:30 AM proposal.
- Agent runs at 9:58 AM (IC pack failure), 10:40 AM (GAP waiting on two inputs) and 12:40 PM (SOC draft): these need the fake-model registry's artefacts.
- Sep 22 bridge letter and Sep 29 reliance: both act on Keystone's SOC report evaluation, and only the 12:40 PM soc1 run creates one. No service makes one by hand.
- Granite Peak's significant risks and its RCM and ITGC processes: the handoff has no rows for them. Its 10:12 AM materiality is already loaded by the completion slice.

## Progress log
- 2026-11-08: built on main 2f14f6b9d. Unit tests pass (509 synthetic). The planning load passes at the Oct 6 11:20 AM snapshot, and the completion load still passes. A one-off load of planning with completion ran end to end; it was not committed.
