# Contract-test upkeep, 2027 Q4 (Q-03-T182)

Run Thu Nov 5, 2026 on main `596eba9cd` with the S27 CI triage (#1222). The row is dated 2027 Q4 in
the plan; under the solo amendment it runs with the sprint that schedules it. What a laptop session
can prove is done here; what needs a hosted stack, a provider sandbox or AWS findings is listed as
open, never as met (DEC-1389, DEC-1391).

## Results

- `python -m abacus_tools.contracts --check`: passes.
- **Consumer suites in provider CI: not yet green.** Run 41914647850 failed 5 `tests/contracts` tests
  from S27 (classification on widened fields, the audits family test, T-03's stubs). #1222 fixes them.
  CI has not re-run with it merged.
- **Drift count: 1, not 0.** `PUT /v1/engagements/{id}/auto-mode` (ED-270, owner P-10-T39, S36) is the
  one route fixture mode answers and the live app does not. It stays allowed by name in
  `route-drift.test.ts`. A stub would make `/v1/me` report the capability and AUD-02's switch would
  render live against a 501.
- OpenAPI: `packages/api-client/openapi.json` regenerated in #1222, with no compat exception needed.
- vN+1 overlaps: none due, since no contract holds two versions.

## Open

- The row's zero waits on P-10-T39.
- The nightly report's drift tickets need the nightly runner.
