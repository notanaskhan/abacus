# Quarterly reserve review · 2028 Q3 (Q-03-T348, TASK-8761, 2026-11-20)

Plan quarter 2028 Q3 covers S45–S51 (built in the repo's calendar from 2026-11-15 to 2026-11-20). Solo
builder (AMENDMENT-solo): every lane ran in AY's sessions, including N-owned rows.

## Burn by workstream (task-equivalents, plan vs built)
| Workstream | Planned in the quarter | Built | Note |
|---|---|---|---|
| Design system tier 5 (F-08) | S50–S51 rows | T01–T11 built; parity and axe wait on the handoff folder | handoff folder not on this machine |
| Close engine (C-01, C-02) | S44–S51 | C-01 screens, specs (T50) and docs (T55, T56) built | runbooks not rehearsed on staging |
| Platform console (G-04) | S47–S51 | T01–T22 built; T22 infra not applied | staging verification is the builder's |
| Entity depth (T-06) | S50–S55 | T22–T31 built (fixture mode) | contract gaps for TXP-08 noted |
| Fieldwork and group audit (A-08, A-09) | S48–S51 | A-08-T37 parity and specs; A-09-T42 step 3 blocked on data | |

Exact per-row hours are not kept; the plan's sizes are the unit, recorded per task file.

## Escaped defects this quarter (and the layer that should have caught them)
| Defect | Found by | Layer that should have caught it |
|---|---|---|
| `firms_tenant_code` collided for a second firm with the same initials (RLS-blind probe) | main CI (#2383) | an integration test provisioning two firms with one prefix (added in #2383) |
| Menu triggers rendered as `<span>` (aria-allowed-attr) on CLS-02 and CLS-09 | C-01-T50 axe specs | a kit lint: Menu triggers must be buttons |
| Readable text and explicit zeros at ink-4 (contrast) | C-01-T50 axe specs | the Amount kit's own test, now fixed (DEC-5745) |
| Parity tables wrote "locked in <task>", which the parser reads as scheduled | A-08-T37 lock test | a unit test over every Parity table's lock wording (added for G-04, C-01, A-08) |
| Task files with empty `acceptance_criteria` (13 in S51) | `validate_docs` at C-01-T55 | the task recorder; fixed in the recorder and the files |
| Stale tests on main: CLS-02 "renders Deliverables disabled", `test_portal_edge.py` (13) | targeted runs | the batch CI on the last PR, which was skipped in recent batches |

## Lane reallocation for the next quarter
- Put the handoff folder on the build machine before any screen or parity row; without it parity and copy fidelity stay open across F-08, T-06 and C-01.
- Run full CI once per batch, on the last PR, and treat red as a stop (the stale tests above were masked by skipped CI).
- Keep the ADR-078 catch-up lane (Q-03-T352) ahead of the gates: write it before the next red row, not after.

## Calibration inputs
Screen rows without the handoff take about the plan's size but leave parity open; docs rows take less; infra rows stop at "not applied" in a solo session. Recorded for the capacity ledger.
