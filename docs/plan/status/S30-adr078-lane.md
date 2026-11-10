# ADR-078 catch-up lane 2027 Q4, part 2 (Q-03-T206)

Recorded 2026-11-08 at the S30 build. One builder, so "another founder's session" reads as a suite
written from the row, spec and contract only, apart from the implementing work (AMENDMENT-solo).
Part 1 is `S29-adr078-lane.md`. A row marked open reaches no gate until it has a suite; the S30
end pass's security review is the interim control, not a substitute.

## Part 1 rows, closed in S30

| Row | Zone | Independent suite |
|---|---|---|
| A-05-T48 | red | `tests/integration/test_a05t48_estimates_rp_independent.py` (Q-03-T206) |
| A-06-T29 | amber | `tests/unit/reporting/test_a06t33_fs_render_independent.py` (A-06-T33) |
| A-07-T13 | red | `tests/integration/test_a07t20_immutable_independent.py` (A-07-T20) |
| A-07-T14 | red | same (A-07-T20) |
| A-07-T15 | red | `tests/unit/assurance/test_a07t15_gates_independent.py` (Q-03-T206) |
| P-10-T02 | red | `tests/integration/test_p10t17_runtime_migrations_independent.py` (P-10-T17) |
| P-10-T03 | red | same (P-10-T17) |
| P-10-T04 | amber | `tests/integration/test_p10t18_runtime_tables_independent.py` (P-10-T18) |
| P-10-T05 | amber | same (P-10-T18) |
| P-10-T06 | amber | same (P-10-T18) |
| P-10-T07 | red | same (P-10-T18: status registry and glossary) |
| R-02-T04 | red | `tests/unit/portal/test_r02t04_bundle_independent.py` (Q-03-T206) |

## Part 1 rows still open

| Row | Zone | Why |
|---|---|---|
| A-05-T46, A-05-T49 | amber | open |
| A-07-T16 | amber | open |
| F-09-T211, F-09-T213 | amber, red | not code (vendor and counsel refresh) |
| N-04-T25 | red | needs real eval runs (evaluation account) |
| N-04-T27 | amber | open |
| P-10-T01, P-10-T58 | red | documents (SPEC and ADR drafts): reviewed, not tested |
| P-10-T08 | red | open: matrix tests only |
| Q-03-T192, Q-03-T193, Q-03-T196 to T199 | red, amber | ops: x100 re-test, pen test #2 (deferred, DEC-1389) |
| Q-04-T105, Q-04-T108, Q-04-T109 | amber, red | ops and support reserve |
| T-03-T18 | amber | open |

## S30 red and amber rows (built in one session; the next part of the lane)

| Row | Zone | Independent suite |
|---|---|---|
| R-02-T05 | amber | open: migration test only |
| R-02-T07 | red | open: unit and integration tests by the implementing session |
| R-02-T08 | amber | contract tests (C10, C18 providers) |
| P-10-T12 | red | open |
| P-10-T13 | red | open |
| P-10-T14 | red | partly: `test_p10t17` covers 0711's backfill door |
| P-10-T15 | red | open: infra test by the implementing session |
| P-10-T16 | amber | open: the frozen C06 v2 contract |
| A-07-T18 | amber | open |
| A-07-T19 | red | open |
| A-05-T53, A-05-T54 | amber | open |
| A-05-T55, A-05-T56 | red | open: eval cases, not run |
| A-06-T37 | amber | open |
| P-11-T33 | red | open |
| Q-03-T205 | red | n/a (it is the mutation shard rebalance) |
| Q-04-T110 | amber | n/a (flag record) |

Finding for the end pass: `parties_in_interest.transactions` is unconstrained `jsonb`, so nothing at
the database stops a writer copying a remittance amount into it; the row's "no copy of
late-remittance amounts" holds only while the writer keeps it out. Raised for A-05's owner, not
fixed here (it would be a migration on a table already on `main`).
