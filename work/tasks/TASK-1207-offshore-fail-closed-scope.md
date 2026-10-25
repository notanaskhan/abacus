---
id: TASK-1207
title: Offshore fail-closed scope - restricted records only (F-03 4.4) or every client (DEC-319)
spec: SPEC-002
acceptance_criteria: [AC-12]
risk_zone: red
status: todo
epic: G-01
plan_key: G-01-T09
branch: none
created: 2026-10-25
updated: 2026-10-25
---

## Context

G-01-T09 (walls v2) implemented offshore fail-closed as a wall: until T-01 registers an offshore
consent provider, an offshore member reaches no client at all (DEC-319). F-03 section 4.4 and
P-07 AC-9 say offshore narrows only the conditioned `tin.reveal` (and other restricted records),
so an offshore manager keeps ordinary work. Four spec tests state the narrower rule and are strict
xfails citing this task:

- `tests/acceptance/test_f03_personas.py::test_an_offshore_manager_cannot_reveal_a_tin`
- `tests/acceptance/test_f03_personas.py::test_an_offshore_manager_keeps_ordinary_work`
- `tests/integration/test_f03_personas_db.py::test_offshore_membership_decides_tin_reveal[True-condition]`
- `tests/integration/test_tin_reveal.py::test_ac9_an_offshore_member_gets_403_and_nothing_is_logged`

## Decision needed (Ayush)

1. Narrow: offshore without consent is refused restricted records only (TINs, PII and the
   other `offshore`-conditioned actions); ordinary work continues. The four tests pass again.
2. Keep wide: confirm DEC-319 in an ADR superseding F-03 section 4.4 and P-07 AC-9, and amend the
   four tests to the wall rule.

## Progress log

- 2026-10-25: opened at the S8 wave A assembly (#395); the wider rule holds meanwhile.
