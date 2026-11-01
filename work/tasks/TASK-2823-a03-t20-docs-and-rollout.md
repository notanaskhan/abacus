---
id: TASK-2823
title: A-03-T20 docs and rollout for sampling and the TB mapping
spec: SPEC-580
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-03
plan_key: A-03-T20
branch: s23-a03-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "The CPA sign-off is recorded before the Sep 21 flip, the runbook re-performs a
  sample from its record on staging, and both flags carry dated flip and retirement entries."

## Plan (green, docs)
- **Contracts frozen:** `docs/contracts/ledger-mapping.md` (C9 v2) and `docs/contracts/sampling.md` (v1).
- **Module READMEs:**
  - Sampling: populations, sample sets, item requests and rollout.
  - Ledger: grouping sets, mapping, TB following and rollout.
- **Runbook** `docs/runbooks/RB-46-sampler-and-mapping.md`:
  - Re-perform a sample from its record.
  - A stale mapping.
  - The flips with rollback (the ops request, `make flag`).
  - Renewal, because both flags expire Apr 28, 2027, before the flips.
  - Retirement.
  - It is indexed in the runbook README.
- **Skill notes:**
  - temporal-workflow: one frozen draw.
  - migration: frozen versions and the human-only publish.
- **CPA memo** `docs/quality/golden-reviews/sampling@2.3.md`: size, UDL, projection, stratification and re-performance, each with its pinned test. The signature is the CPA's.
- **Flags:** both descriptions carry the dated flip and the Oct 21 retirement.
- **Human:**
  - The CPA signs the memo.
  - The staging re-performance (RB-46 §A) and the flips. Real firms wait (DEC-1391); PF-X1 stands in.
- Rollback: revert.

## Progress log
- `2026-11-01`: written. `make regenerate` covers the flag descriptions; it runs in the end pass.

## Decisions made during this task
None.
