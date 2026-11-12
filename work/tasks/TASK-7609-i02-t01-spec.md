---
id: TASK-7609
title: I-02-T01 SPEC-654 Today brief; ADR check; Q1–Q5 settled; upstream inventory
plan_key: I-02-T01
spec: SPEC-654
acceptance_criteria: [AC-1]  # the SPEC names every endpoint, rule and flag, with Q1 to Q4 answered
risk_zone: red
status: in-review
branch: i02-t01-spec
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
SPEC-654, chapter 09 §9.4.4's "record as a spec" for the Today brief (the SPEC-027 follow-on):
code composes counts, the fact paragraph, Needs you first and the groups; the model writes
per-engagement prose only. The ADR check against repository numbers, Q1 to Q5 settled, and the
inventory of what I-01, P-10, P-05 and W-02 shipped.

## Plan
- `docs/specs/SPEC-654-i02-today-brief.md` (new). Decision DEC-4608. No code.
- Rollback: revert.

## Findings
- HOME-01 already reads `today_brief.enabled` for its "Open Today →" link, but no such flag is in
  the registry: I-02-T04 creates it (until then `useFlag` reads false, fail closed).
- The epic's ADR numbers map to ADR-233, 230, 234, 169, 166, 160, 145, 167, 232, 148, 235, 143.

## Partial
- The ask binding (§3.7) waits for W-02-T12 and T15; ADR-232 to ADR-235 are proposed (DEC-3016).

## Progress log
- `2026-11-12` — SPEC-654 written (DEC-4608).
