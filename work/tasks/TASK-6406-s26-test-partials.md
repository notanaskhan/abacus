---
id: TASK-6406
title: S26 test partials (Q-03-T171 lane) - N-04-T10 foot test, A-04-T30 one card, A-05-T29 PII sinks, A-06-T17 record-mode evidence
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T171
branch: s26p-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-08
updated: 2026-11-08
---

# TASK-6406 · Q-03-T171: S26's missing tests, and record mode refuses evidence off the engagement

S26's test rows left these out: N-04-T10's TypeScript fixture assertions and Whitley figures, A-04-T30's "one card covers every pending proposal", A-05-T29's runtime scan of the sinks, and A-06-T17's record-mode evidence check. Writing the last one found a real gap: record mode accepted any evidence id.

AC-1: The notices fixtures compile against the generated client and foot: 1,870 + 1,250 = 3,120; 22% x 3,120 = 686.40; + 66.61 = 753.01 on NOT-02 and NOT-03; no fixture carries a whole TIN.

AC-2: Northwind's routed register makes exactly one `significant_risk` card, and its options name both R3 and R5.

AC-3: After sealing and revealing a participant's SSN and date of birth, neither appears in the structured log, the audit trail, the outbox, the access record or the reveal record, in any spelling.

AC-4: Record mode refuses a client's decision whose evidence is not on the entry's engagement (422 `record_evidence_not_on_engagement`) and records nothing.

## Decisions (DEC-2956)
- `adjustments.decisions._one` checks record mode's evidence through a slot (`register_evidence_engagement`) that assurance fills with `evidence.api.engagement_of_version`, since adjustments may not import evidence (BOUND-002); with nothing registered it refuses (fail closed). The decision row has no foreign key on it, so a random id was accepted.
- The backfill test that recorded with a random evidence id now uses the engagement's own version.
- A-04-T30's AUD-05 and AUD-07 persona checks already exist on main ("Marcus … no Approve minutes", "Hannah … no Decide").

## Known limits
- Q-03-T171's mutation-survivor tests: no survivor data exists. The nightly mutation run stops before mutating because `test_app_gates::test_ac20_creating_routes_answer_201` fails on main, so every mutant reads "not run".
- A-06-T17's approver-of-record scope belongs to the portal's client decision (R-02's BFF, `apply_client_decision`), which is not on main yet.

## Progress log
- 2026-11-08: built on main a801fff01; tests written, run at the S26 partials end pass.
