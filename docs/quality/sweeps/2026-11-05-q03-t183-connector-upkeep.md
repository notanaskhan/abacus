# Contract and connector upkeep, 2027 Q4 (Q-03-T183)

Run Thu Nov 5, 2026 on main `596eba9cd` with the S27 CI triage (#1222). The row is dated 2027 Q4 in
the plan; under the solo amendment it runs with the sprint that schedules it. What a laptop session
can prove is done here; what needs a hosted stack, a provider sandbox or AWS findings is listed as
open, never as met (DEC-1389, DEC-1391).

## Result: not met

The row's acceptance is "No fake is reported unverified". All five are unverified, and no
`verified_on` date was set, because none was checked against its provider.

| Fake | Provider | Contract | `verified_on` |
|---|---|---|---|
| `abacus_tools/fakes/ledgers.py` | NetSuite (CSV export), bank, card and sales feeds | C20 | never |
| `abacus_tools/fakes/workos.py` | WorkOS | identity (ADR-165) | never |
| `abacus_tools/fakes/identity.py` | an OpenID Connect provider | identity (TASK-007) | never |
| `communications/fake_ses.py` | Amazon SES | C16 (email half) | never |
| `signatures/contract.py` | DocuSign (the `fake` envelope provider) | C7 | never |

- **Nightly connector suites:** `connectors-nightly` succeeded on Nov 2, 3 and 4, 2026. QuickBooks
  Online shows `FAKE: passed`, `SANDBOX: skipped`, so a green nightly proves the fake only.
- **Consumer suites:** run with `tests/contracts` in main's CI; see Q-03-T182 for their state.

## Open

Sandbox credentials for each provider (human), then the sandbox steps, then the `verified_on` dates.
The signature provider is now DocuSeal (ADR-342), so the register's DocuSign line is due an update
when it is verified.
