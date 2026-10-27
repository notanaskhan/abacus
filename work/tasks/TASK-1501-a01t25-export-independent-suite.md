---
id: TASK-1501
title: Independent AC tests for the engagement export (A-01-T25)
spec: SPEC-344
acceptance_criteria: [AC-4, AC-10]
risk_zone: red
status: in-review
epic: A-01
plan_key: A-01-T25
branch: s12b-a01-t25
created: 2026-10-27
updated: 2026-10-27
---

## Objective
ADR-078 independent tests for A-01-T18, T19, T22 and T23 plus I-AGENT-NEVER rows, manifest schema
tests and a determinism property test.

## Plan
- `tests/unit/evidence/test_a01t25_package_properties.py` (offline, hypothesis): hostile client
  names always become safe, unique archive paths; the same inputs give the same bytes in any order;
  every manifest file and checksum verifies; the published manifest schema is the generated one.
- `tests/integration/test_a01t25_export_lifecycle_independent.py` (on the A-01-T19 Northwind
  fixtures): expiry after 7 days, voiding on a withdrawn version (once), the agent and the system
  never create an export, a stale second factor asks for a step-up and writes nothing, two builds
  of one export are byte-identical.
- Walls and offshore refusals stay with A-01-T18's suite (`test_a01t18_engagement_exports.py`),
  whose world seeds them.

## Not done here (DEC-641)
- **ADR-078 independence:** these suites were written in the same session that built the S12
  batch, not a separate one (Ayush asked for one sequential session with no sub-agents).
- **Northwind eval cases** (BrokerWindow vs schedule of account balances, Harborline
  certification, SOC 1 as bridge letter): they need notanaskhan's approval to merge and real-model
  runs (`make evals` is never run here). Recorded as a follow-up.

## Progress log
- 2026-10-27: suites written; not run yet (one test pass at the end of the S12 batch).
