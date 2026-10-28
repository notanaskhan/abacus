---
id: TASK-1707
title: Q-03-T524 back-fill TASK-053 (ledger import web) and TASK-061 (client hub web)
spec: SPEC-028
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T524
branch: s14-q03-t524
test_author: ayushkbhatia
test_session: 2026-10-28, s14 (from SPEC-028 and SPEC-031 only, black-box)
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ADR-078 back-fill: a named `test_ac<N>` for every AC of SPEC-028 (TASK-053) and SPEC-031
(TASK-061), headed `ac-test-author: ayushkbhatia`, passing against the live paths. Retired only when
the replacing epic's AC suite merges (A-02 S17 for the ledger import; R-01 for the client hub).

## Plan and coverage
SPEC-028 (TASK-053, ledger import web; the panel stays live until A-02):
| AC | Test |
|---|---|
| AC-1 | `apps/web/src/legacy/q03t524ledgerimport.test.tsx` test_ac1 (2) |
| AC-2 | same file test_ac2 (3); five systems: `test_ledger_formats.py` test_ac4 (Q-03-T024) |
| AC-3 | `backend/tests/integration/backfill/test_q03t524_ledger_import_storage.py` test_ac3 (2): fingerprint, size, clean scan, versioned object; EICAR refused 422 `file_refused`, nothing snapshotted or fulfilled |
| AC-4, AC-5, AC-8 | `test_ledger_formats.py` (Q-03-T024, same author, independent) |
| AC-6 | web test_ac6 (2) and `test_ledger_formats.py` test_ac6 |
| AC-7 | `backend/tests/unit/connections/test_q03t524_import_capabilities.py` test_ac7 (4) |
| AC-9 | web test_ac9 (4): loading, error, not allowed, no literal colours |

SPEC-031 (TASK-061, client hub web). The legacy client page was retired by R-01-T18; the client
paths are POR-03 and POR-04, so the suite drives POR-04 on its fixture scenarios:
| AC | Test |
|---|---|
| AC-1 | `apps/web/src/domain/portal/q03t524clienthub.test.tsx` test_ac1 (2) |
| AC-2 | web test_ac2; server: `test_q03t047_requests_client_hub.py` test_spec031_ac2 (2) |
| AC-3 | server only (firm edit rights, audit): `test_q03t047_requests_client_hub.py` test_spec031_ac3 |
| AC-4 | web test_ac4 |
| AC-5 | web test_ac5 (2); server: test_spec031_ac5 |
| AC-6 | web test_ac6 (2); server: test_spec031_ac6 |
| AC-7 | web test_ac7 (3); server: test_spec031_ac7 |
| AC-8 | server only (template workbook columns): `tests/unit/engagements/test_workbook_guidance.py` test_ac8 (3) |
| AC-9 | web test_ac9 (3) |

## Progress log
- `2026-10-28` — Suites written. Targeted runs: web ledger 11 passed, web client hub 14 passed, unit AC-7 4 passed. The AC-3 integration file needs Postgres and S3: runs in the batch-end pass.

## Handoff
- **Current state:** PR open, held for the S14 batch.
- **Known gaps:** `test_q03t524_ledger_import_storage.py` not yet run (testcontainers).
