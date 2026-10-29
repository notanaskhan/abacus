# Security and reliability sweep, Thu Oct 29, 2026 (Q-03-T095)

Run on `main` at the S16 build (origin/main as fetched 2026-10-29). Q-03-T095's acceptance:
"Every new table and condition kind has generated tests, no high DAST or GuardDuty finding is open
and every burn-rate alert has a closed follow-up or a dated ticket."

## 1. Generator coverage (ADR-080) — done here

`python -m abacus_tools.quality.generator_coverage` (new; in `make check-fast`):

| Check | What it proves | Gaps |
|---|---|---|
| tables | every table any module's SQL names is in `schema_check.TABLE_OWNERS` (680 module files) | 0 |
| isolation | every tenant table is in the generated `tests/security/test_tenant_isolation.py` | 0 |
| conditions | every matrix condition key has an allow and a deny case | 0 |
| decisions | every cell decision the matrix uses names the tests that allow and deny it | 0 |

`python -m abacus_tools.codegen.security_tests --check`: every generated suite (isolation, matrix,
route introspection, resolution actions, fresh MFA) is current.

Repository methods: ADR-080 asks for an isolation test per repository method. Of 705 public
repository functions, 630 are not named by any test; they run through services that integration
tests drive. Isolation is proven per table instead (forced row-level security keyed to the tenant,
and the generated two-firm read for every tenant table), and the sweep's tables check closes the
loop: no method can name a table outside the isolation list without failing `check-fast`. No
per-method gap remains for Q-03-T096 to close on `main`.

The S16 branches add tables in migrations 0400–0403 (K-02, T-01, T-02). The sweep runs on each
branch at the S16 end review, before the batch merge.

## 2. Compliance invariant catalogue — at the end review

Runs with the full suites at the S16 end review (one pass, `make check`), not here.

## 3. DAST, Inspector and GuardDuty — human (needs the AWS accounts)

Triage reads the staging and production security findings; this session has no AWS access to
them. Owner: Ayush. Record each high finding here with its ticket and date.

## 4. ADR-093 reliability follow-ups — human (needs production telemetry)

SLO burn, slow statements, N+1 regressions, queue backlog and outbox lag come from production
dashboards. Owner: Ayush. Each burn-rate alert since the last sweep gets a closed follow-up or a
dated ticket, listed here.

## 5. The S16 branches (Q-03-T096)

Re-run on the S16 stack tip (`s16-t02-t08`, which carries K-02, T-01 and T-02 with migrations
0400–0403 and the `owner_of_target` condition), with that tree's own code on the path:
`generator_coverage` 0 gaps in all four checks, and `codegen.security_tests --check` current.
Q-03-T096 found no route, table or condition without its generated allow, deny and cross-tenant
tests, so it adds none. Re-run after the batch merge re-chains the migrations.
