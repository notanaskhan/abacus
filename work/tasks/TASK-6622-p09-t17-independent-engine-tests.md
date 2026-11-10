---
id: TASK-6622
title: "P-09-T17: ADR-078 independent tests for P-09's amber engines"
spec: SPEC-648
acceptance_criteria: [AC-8]
risk_zone: amber
status: in-review
branch: s34-p09-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-09-T17
---

## Objective
The tests merge green and fail under a seeded mutation of each rule.

## Plan (amber)
`apps/web/src/domain/agents/p09t17.ac.test.tsx` (`ac-test-author: notanaskhan`), from the P-09
epic and the row. Each rule is a check over an implementation, run on the real one and on a
seeded mutant that must fail it:
- RunStore: seq order (mutant: no sort), duplicate seq applied once (mutant: no dedupe), resync
  replaces (mutant: merges); one snapshot per page.
- Polling: a terminal state (succeeded, needs_input, failed) stops for good and never restarts;
  queued keeps polling; a hidden tab does not poll and visibility resumes it; stop() in flight
  drops the page; the after_seq cursor follows last_seq.
- AgentBlocks: hostile markup renders as text, an unknown part shows no payload, an unknown
  fact shows a dash (mutant: renders the payload as HTML).
- HumanAction renders nothing for the agent, an agent-assisted change, a policy or the system
  (mutant: any actor); formatActor reads "Policy: BH AJE thresholds v2" and an assisted approval
  "Raj Malhotra via Agent", never "Accrued Agent" (mutants: agent naming, version dropped).
No production code. Rollback: delete the file.

## Progress log
- 2026-11-10: written; run at the S34 end pass. The polling mutants are not seeded (they would
  duplicate PollingRunSource); its rules are asserted on the real source with fake timers.
