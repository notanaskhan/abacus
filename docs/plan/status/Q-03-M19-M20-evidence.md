# M19 and M20 quality evidence (Q-03-T347, TASK-8760, 2026-11-20)

The evidence the founders sign before the M19 (Fri Sep 29) and M20 (Tue Oct 31) gates. Each line names
what was run, where, and its result on 2026-11-20. **Not signed:** both founders' signatures are theirs
to give; this file records the evidence only.

| # | Evidence | Run | Result |
|---|---|---|---|
| 1 | Consolidation goldens (A-09, Harlow & Pike FY2026) | `backend/tests/golden/ledger/consolidation` (local, this worktree) | pass |
| 2 | Close goldens and properties (C-01, C-02) | `backend/tests/golden/closes` (exact `Decimal`, Hypothesis) | pass |
| 3 | I-CONFIRMATION-ISOLATION | `backend/tests/security/test_confirmation_isolation.py` | pass |
| 4 | Portal-scope isolation extended to component auditors (POR-23) | `backend/tests/security/test_a09t37_component_agent_independent.py`; tenant isolation suite in `make test` | pass (59 tests across rows 1–4) |
| 5 | Portal-scope isolation **pen-tested** | — | **deferred** (DEC-1389: no penetration tests); recorded as deferred, never as met |
| 6 | QBO conformance suite green for 30 nights | `connectors-nightly.yml` on GitHub Actions | 21 of 21 runs green from 2026-10-30 to 2026-11-19; **30 nights not yet reached** |
| 7 | Close screens accessibility | `apps/web/e2e/screens/CLS-*.spec.ts`, `POR-11.spec.ts` (C-01-T50, fixture mode) | 64 pass, axe clean in light and forced colors |

## Gate reading
- M19 (integrations catalogue, tenant console): rows 3, 4 and the G-04 screen specs (G-04-T21: 26 screen and 5 journey tests in fixture mode) are green; staging with real auth is not run.
- M20 (close engine): rows 1, 2 and 7 are green; row 6 is short of 30 nights; row 5 is deferred.

## Signatures
| Founder | Gate | Signed | Date |
|---|---|---|---|
| Ayush Bhatia | M19 | — | — |
| Ayush Bhatia | M20 | — | — |
| notanaskhan | M19 | — | — |
| notanaskhan | M20 | — | — |
