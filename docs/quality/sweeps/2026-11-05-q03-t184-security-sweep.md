# Security and reliability sweep, 2027 Q4 (Q-03-T184)

Run Thu Nov 5, 2026 on main `596eba9cd` with the S27 CI triage (#1222). The row is dated 2027 Q4 in
the plan; under the solo amendment it runs with the sprint that schedules it. What a laptop session
can prove is done here; what needs a hosted stack, a provider sandbox or AWS findings is listed as
open, never as met (DEC-1389, DEC-1391).

## Done

- **Generator coverage:** `python -m abacus_tools.quality.generator_coverage` reports tables 0,
  isolation 0, conditions 0, decisions 0 gaps, S27's tables included.
- **Invariant catalogue and generated suites:** the `security` job passed in main's CI on
  `596eba9cd` (run 41914647850).

## Not done, and why

- **DAST:** `dast.yml` was skipped on its Oct 27 and Nov 3, 2026 runs, so there is no report to triage.
- **Inspector and GuardDuty:** not read. The attempt to read AWS stopped at sign-in: "Your session
  has expired. Please reauthenticate using 'aws login'." No finding is claimed absent.
- **ADR-093 follow-ups:** burn-rate, slow statements, N+1, queue backlog and outbox lag need the hosted
  stack's data. Not read.

So the row's first clause is met on the repo side. "No high finding is open" and "every burn-rate
alert has a follow-up" are **unverified, not met**.

## Noted for its owner

Main's own red, not from S27: `test_t30_grace_holloway...` fails because `evidence.ocr_retry` is allowed
for `client_service` since #1130, and that test says a firm admin holds no evidence content action.
The route returns a status, not content, but this is a permission decision, so it was not changed here.

## Open

`aws login`, then read-only triage on staging. Pen tests stay deferred (DEC-1389).
