---
name: ac-test-author
description: Write an independent acceptance-test suite (ADR-078) for a task that is already built — a Q-03 back-fill, an epic's "independent AC tests" row, or a golden-figure suite — from the spec, the contract and the ADRs only, never the implementation. Black-box at the HTTP or public-service boundary, `test_ac<N>_…` names, the `ac-test-author` header, failures triaged as defect or spec drift, and test_author/test_session recorded. Use for any row titled "independent AC tests", "ADR-078", "back-fill" or "golden-figure tests".
---

# Independent acceptance tests (ADR-078)

The suite says what the spec promises and checks whether the product keeps it. It is worth
something only if it was written without looking at how the code does it: a test copied from the
implementation passes by construction. Solo edition: the builder writes it, in a session that
follows this skill; the two-person split is void, the clean-session rule is not
(`docs/plan/AMENDMENT-solo.md` item 3).

## 1. Load only these
- The task file(s) the row names (`work/tasks/TASK-*.md`): their `spec` and `acceptance_criteria`.
- The spec (`docs/specs/SPEC-*.md`): §5 acceptance criteria, §8 interfaces, §9 authorisation,
  §12 edge cases, §14 audit events. For an epic row without a spec, the epic's §3 stories.
- The contract the code now answers to: `docs/contracts/<name>.md`, the permission matrix rows
  (`docs/architecture/permission-matrix/<module>.yaml`), `docs/architecture/error-codes.yaml`,
  `docs/architecture/human-only-actions.yaml`.
- The decisions that changed the spec since: search `docs/product/decision-log.md` and
  `docs/plan/09-decisions-adrs.md` for the spec, screen IDs and module. A later DEC or ADR wins.
- The ADRs the spec lists. For screens: `docs/screens/<ID>.md`.

**Never open** a module's `service.py`, `repository.py`, `models.py`, workflow or component body
to decide what a test expects. Allowed, to learn how to *call* the product: route declarations
(path, method, body model names), `api.py` signatures, the OpenAPI document, and the existing test
fixtures in the directory you write into (`backend/tests/integration/backfill/support.py`). If the
expectation is not in the spec, the contract or a decision, it is a spec gap: record it (step 5),
do not read the code to fill it.

## 2. Where the tests go
| Kind | Path | Boundary |
|---|---|---|
| Back-fill of a TASK | `backend/tests/integration/backfill/test_<area>.py` | `create_app()` over HTTP on the migrated testcontainer Postgres (`net`, `seed` fixtures) |
| Independent tests of an epic row | `backend/tests/integration/test_<epic><row>_<area>.py` or `backfill/` to reuse its fixtures | same |
| Contract half | `backend/tests/contracts/<contract>/` | the public `api.py` and the database CHECKs |
| Golden figures | `backend/tests/integration/test_<row>_goldens.py` | the loaded scenario, read through SQL or the read routes |
| Screen states (an AC like "loading, empty, error, not-allowed") | next to the screen in `apps/web/src/**`, `*.test.tsx` | the rendered component with the generated client mocked at the network |

Seed through the superuser helpers (`Seeder`) or the public routes; never through a module's
repository. Expected values are literals typed from the spec or §5.4 tables, never imported from
the scenario package or a module constant (that would be circular).

## 3. How each file starts
```python
# ac-test-author: <github handle>
"""SPEC-0NN AC-1, AC-4 (TASK-0NN): <one line of what the ACs promise>.

<Boundary used. Which later decisions the tests follow instead of the spec's wording.>
"""
```
TypeScript: `// ac-test-author: <handle>` on line 1.

## 4. Names and assertions
- One or more tests per AC, named `test_ac<N>_<behaviour_in_words>`; an AC from an epic story is
  `test_ac<story>_…` (e.g. `test_ac3_1_2_…`); an invariant is `test_inv<N>_…`.
- Assert the promise and its refusals: the allowed case, every role the matrix denies, another
  firm (404, never 403: DEC-43), the audit row (`audit_events.action`, `actor_kind`), and the
  human-only rule (an agent context is refused; INV-1).
- Status codes and bodies come from `error-codes.yaml`, not from what the route happens to return.
- Never weaken an assertion to pass, never `skip`, never lower a threshold (AGENTS.md rule 13).

## 5. When a test fails: triage
| Finding | Do |
|---|---|
| **Defect**, fix small and inside the module the AC covers | Fix it in the same PR as the test. Add a row to `docs/quality/escaped-defects.md` with the layer that should have caught it. |
| **Defect**, fix crosses modules, needs a migration, a contract change or `make generate` | Keep the real assertion and mark it `@pytest.mark.xfail(strict=True, reason="<what fails and why>; recorded in work/tasks/TASK-NNN-….md (#<PR>)")`. `banned_patterns` SKIP-001 needs `#<digits>`: use the PR that records it (DEC-200). Log it in `escaped-defects.md` as `open`. |
| **Spec drift**: a later DEC, ADR or contract changed the promise | Test the current contract, name the superseding decision in the test's docstring, and record the drift in the PR's task file and in `docs/quality/backfill.md`. |
| **Flaky** | Not a pass. Re-run alone to separate it from load; if it still flips, record it as a defect. |

`strict=True` makes the test fail the day the defect is fixed, so whoever fixes it removes the
marker in the same change.

## 6. Record it
- In the PR's task file frontmatter: `plan_key` lists every row (`Q-03-T006; Q-03-T007`), plus
  `test_author: <handle>` and `test_session: <date and branch>`.
- In the task file body: per AC, the test names and pass or xfail; each defect fixed; each xfail
  with its reason; each spec drift item (AC, spec says, contract says, superseding DEC).
- In each back-filled TASK's progress log: one line pointing at the suite and the PR's task file.
- In `docs/quality/backfill.md`: the row's status becomes `back-filled` and the suite path is filled.

## 7. Before the PR
Run the new files, then `make check-fast`, then
`cd backend && uv run pytest tests/unit tests/acceptance tests/security tests/contracts -q`. Report
any failure that is not yours instead of hiding it.
