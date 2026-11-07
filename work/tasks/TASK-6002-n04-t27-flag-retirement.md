---
id: TASK-6002
title: "N-04-T27 retire notices.workspace and notices.responder (held for the Dec 16 batch)"
spec: SPEC-000  # row (N-04-T27)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T27
branch: s29l-n04-flags
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
No N-04 flag remains in the Jan 1-Apr 20 window.

## Plan
Delete docs/architecture/feature-flags/notices.yaml (codegen refuses an empty list) and regenerate kernel/_flags.py. Backend: contract._gate_firm and _gate stop reading the flag; intake_sources' answer effect and triage destinations stop reading it; notice_responder.analyze and extract_fields read only the firm's stage (the gateway keeps clearance, consent and the platform pause). Frontend: /notices and /notices/$noticeId lose their FeatureGate; NOT-02 drops its flag-off state; NOT-01 and NOT-02 fixtures lose the `off` scenario and the capability flag; e2e NOT-03 and j09 drop `?flags=`. Seed: no flag event. Tests: the stub's gate test authorises then serves; the protected-bundle test asserts both flags are gone; integration fixtures stop seeding the flag; NOT-02's off test reads the screen with no flag. Rollback: revert this PR (the flags come back default off).

## Progress log
- 2026-11-07: built. pyright clean on the changed backend files; web tsc and eslint clean. Tests written; run at the end pass.

## Decisions made during this task
DEC-2602
