# S28: rows not built, and why (DEC-2324)

Recorded at the S28 build (2026-11-05, on main ab2cef04c plus the S28 stack #1230 onward). None is
marked done, and no gate they guard is treated as met (DEC-1389, DEC-1391).

## Code rows held back
Update 2026-11-06: T-03-T15 and T-03-T19 are built with recorded partials (DEC-2371, DEC-2372), and A-06-T28 is built only as the checklist import and its 142 items (DEC-2373). The table is the state at the S28 build.

| Row | What holds it |
|---|---|
| T-03-T15 | The Brightwater Hale extensions and estimates load through service APIs, and no service creates a `filing_extensions` or `estimate_schedules` row yet: that's T-03-T07's recorded partial (prepare, estimates). Writing rows directly would break the row's own rule. Organizer v6 and the Feld questionnaire exist through `tax_content`. |
| A-06-T28 | The ASC 962 checklist (142 items) loads through the checklist import route, a 501 stub until A-06-T29 and T-30 (S29); Dana's approval needs the same rows. AJE, RJE and SUM are partly in `review_slice`. |
| T-03-T19 | Retiring `tax.returns_v1`, `tax.k1_release` and `questionnaires.v1` removes each flag check across about 40 files on the premise that T-03 has adopted those paths, and T-03-T05 is still partial. The renewals are dated to the Tue Nov 16, 2027 train, and every flag already runs past today. Do it with T-03-T05's lifecycle routes. |

## Quality lanes
| Row | How it stands |
|---|---|
| Q-03-T190, Q-03-T191 | Filled by the S28 end pass's fixes; results in `docs/plan/status/S28-end-pass.md`. |
| Q-03-T189 | No perf stack on main and no runtime v2 schema until P-10 (S29 on). The S28 migrations' up, down and up run in the end pass, on a small database, which isn't this row's x100 rehearsal. |

## Not code
| Row | What holds it |
|---|---|
| F-09-T204, F-09-T206, F-09-T207, F-09-T208 | Programme, partners and spend: human work. F-09-T206 also needs F-09-T181, not built. |
| Q-04-T100, Q-04-T101 | Season-2 firms: none exist (DEC-1391). |
| Q-04-T102, Q-04-T103 | Support reserves: no on-call rota or partner desk, as with Q-04-T098 and T099. |
| Q-03-T187 | Fixes for Q-03-T176's x100 findings; that test hasn't run. |
| F-09-T205, Q-03-T188 | Pen test #2: deferred in full (DEC-1389). |
