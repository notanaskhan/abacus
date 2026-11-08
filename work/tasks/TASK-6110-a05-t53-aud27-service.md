---
id: TASK-6110
title: "A-05-T53 AUD-27 service: estimates by code, the EP's conclusion card, related parties, parties in interest"
spec: SPEC-000  # row (A-05-T53)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T53
branch: s30-a05-t53
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A-05 F11: estimates (components foot to TB 1450, rollforward, retrospective %, auditor range, bias) with Request partner conclusion as a C3 card reserved to the EP; related parties with a reasoned screen-out; parties in interest with prohibited transactions read from the late remittance.

## Plan
- `assurance/compute/ebp/estimates.py`: pure Decimal engine (foot, rollforward, retrospective with percent half-up to 0.1, range check, bias).
- `assurance/aud27.py`: `estimates`, `set_method` (evaluates), `request_conclusion` (card `estimate_conclusion`, EP-reserved, the estimate in the question key), `_conclusion_card` (figures: balance, range), `related_parties`, `add_related_party`, `screen_out`, `parties_in_interest` (+ `v_prohibited_transactions`).
- `assurance/ebp_contract.py`: AUD-27 routes call the service (behind the `assurance.estimates_rp` gate as before).
- `assurance/api.py`: registers the decision kind.
- Tests: `tests/unit/assurance/test_a05t53_estimates.py`.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean; the app and worker import.

## Decisions made during this task
DEC-2708
