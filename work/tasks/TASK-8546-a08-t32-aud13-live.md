---
id: TASK-8546
title: "A-08-T32: AUD-13 live host on one analytics set"
spec: SPEC-657
acceptance_criteria: [AC-5]
risk_zone: green
status: in-review
branch: a08-t32-aud13-live
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-18
updated: 2026-11-18
plan_key: A-08-T32
---

## Objective
AUD-13 fixture-to-live: the statement, tallies and dual threshold on GET /v1/analytics-sets/{id}; Accept explanations as a person.

## Plan (green)
1. screens/AUD-13/live.tsx: AUD13Live in the T6 grammar; derived lines as subtotal rows; explanation text through AgentText with its author; status and accepted-by initials from the server; tallies and threshold from the set; Accept explanations… only with analytics.accept, posting the explained lines against review_hash
2. copy.ts tally.thresholdOf; route /audits/$auditId/analytics/$analyticsSetId (audits.cockpit gate)
3. Manifest stays planned (DEC-5531): the cockpit rail's designed links from AUD-13 (SHL-10, AUD-11, AUD-12) have no targets the set names
4. Tests: live.test.tsx (2)

## Progress log
- `2026-11-18` — Built 2026-11-18 (S49 open rows, round 2). Not done: the Ask client sheet and agent drafts on live reads, the cockpit rail links, the staging run. Gates and tests run once at the S49 open-rows end pass (build first, test last).
