# Front-end integration lane and escaped defects, Q4 2028 (Q-03-T380 part 1, Q-03-T381 part 3; DEC-6044)

Each entry: what broke, the layer it passed, and the test that now holds it (same PR).

| Found in | Defect | Passed | Fixed with |
|---|---|---|---|
| K-03-T22 | SHT-01 row drawer: collaboration had no `sheet`/`sheet_row` comment anchors, so the Comments tab would 404 live | fixture-mode tests | `sheet_anchor.py` + Postgres case in `test_k03t20_sheets_core.py` (K-03-T23) |
| K-03-T22 | SHL-07 citation card mounting late under a loaded run (flaky) | CI timing | longer wait for the portal card (`RowDrawer.test.tsx`) |
| T-06-T53 | TAX-11 fixture: the entity handlers' return record 404'd for the tax-returns id | screen tests | scenario puts the tax-returns record last (`fixtures/scenarios/TAX-11.ts`) |
| T-06-T52 | every consent-bearing tax read (8 actions) failed closed for everyone: no resource set `consent_subjects` | unit suites | return resource names its client entity (`overview._resource`); `test_t06t52_other_entity_lines.py` |
| T-08-T31 | every standards run read answered 500: untyped `:r IS NULL` parameters | unit suites | cast parameters; `test_t08t31_standards_run_rows.py` |
| C-02-T42 | close package release passed at 9 of 21 reconciled; its 409 would 500 on facts | unit suites | `release.py`; `test_c02t42_package_handoff_ac.py` |
| C-02-T48 | ANY-001 on the hand-off target | banned patterns at end | commented `Any` |
| T-08-T31 | TENANT-001: a test wrote actor settings with `set_config` | banned patterns | the kernel's unit of work |
| T-08-T32 | the Write tool overwrote a tracked slice file | review | restored from git; check a path before writing |

Merge conflicts in routes and copy registries: none this period (the stack was linear).
