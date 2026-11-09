---
id: TASK-6506
title: "A-07-T33: flags audits.completion, audits.letters, audits.report_release, audits.archive replace LIVE and COMPLETION_LIVE"
spec: SPEC-644
acceptance_criteria: [AC-flags]
risk_zone: red
status: in-review
branch: s33-a07-t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: A-07-T33
---

## Objective
The four A-07 flags exist (boolean, per firm, default off), every A-07 route and provider reads
them, and the S27 kill constants are gone.

## Plan (red)
1. `feature-flags/assurance.yaml`: four flags (owner notanaskhan, DEC-137's 180-day override as
   every 2026 flag; the plan's Thu Jan 27, 2028 train and Wed Apr 26 expiry map to the build clock).
2. `a07_registrations.py`: `FLAGS`, `live(tenant, flag)`, `require_live`; rail rows, envelope
   checks, the envelope consumer, decision cards and new C11 renders read the firm's flag
   (`tenant_variables_provider`); `LIVE` removed.
3. `completion_projector.projector_live` and the bring-down starter read `audits.completion`;
   `completion_dark.py` (COMPLETION_LIVE) deleted.
4. `release_contract._gate` and `completion_contract._gate`: authorise, then the family's flag
   (404 off) — so the 501 stubs and the live S32 handlers are flag-gated.
5. Tests that pinned `LIVE`/`COMPLETION_LIVE` read the flag defaults and patch `flag_enabled`.
Rollback: revert; flags default off, so behaviour off equals before.

## Progress log
- `2026-11-09` — Built. Not run (end pass). SPEC-314's `completion_routes.py` (live) untouched.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3106 | The flag families and the gate order | no |
