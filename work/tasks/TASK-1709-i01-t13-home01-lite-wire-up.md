---
id: TASK-1709
title: I-01-T13 HOME-01 lite wire-up
spec: SPEC-313
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: I-01
plan_key: I-01-T13
branch: s14-i01-t13
created: 2026-10-28
updated: 2026-10-28
---

## Objective
HOME-01 lite in production shape: `home.dashboard` on for Dev and synthetic firms, manifest live, the
Home area at `/home` (`/` redirects there with the flag on), every Waiting-on-you row opening its host
gate until HOME-02 (AUD-03, CLI-07, CLI-08, BND-02), and SHL-04's Approvals tab counting with the C13
counts endpoint so the header, the segmented badge and the drawer show one number (P-01 R4).

## Plan
- Backend (amber):
  - `requests`: `review_hosts(tenant, versions)` (item and list of each version's newest live
    fulfilment; LIST-001 exempt as a system reader the presenter re-authorises).
  - `assurance/review_gates.py`: the `evidence_version` gate presenter: authorise `review.read` on
    each engagement (Forbidden/NotFound → no facts), then `subject_route` = AUD-03 for a PBC list,
    BND-02 for any other list. `review.api` exports `GateView`.
  - Flags: `home.dashboard` and `review.grammar_api` in the scenario loader's `FLAGS_ON` and the Dev
    seed. No migration, no matrix or flag-registry edit.
- Frontend:
  - `screens/HOME-01/hosts.ts`: resolve `subject_route` codes through the manifest builders (UUIDs
    only), else by subkind (CLI-07, CLI-08). Replaces HOME-01's one-subkind `hostHref`.
  - SHL-04 drawer: Approvals count from `humanGateCountsOptions` (`total`), feed count on 404.
  - Nav: Home area path `/home`; manifest HOME-01 `live`. SHL-01 tests: the #555 interim rule goes.
- Rollback: revert the branch; flags off restore the legacy landing.

## Acceptance (I-01 AC1.4, AC2.4)
| Check | Test |
|---|---|
| Rows open their host (AUD-03, BND-02, CLI-07, CLI-08); unknown codes or non-ids open nothing | `apps/web/src/screens/HOME-01/hosts.test.ts` |
| The presenter names AUD-03 for a PBC list, BND-02 for a binder, ids only | `backend/tests/integration/backfill/test_i01t13_home_wire_up.py` |
| SHL-04's Approvals tab = counts `total` (11); feed count while 404 | `SHL-04.test.tsx` "Approvals count is C13's" |
| Home lights on `/` and `/home`; G H opens `/home`; manifest landing = area path | `SHL-01.test.tsx` |

The staging walk (Hannah's three numbers on staging) waits for staging.

## Progress log
- `2026-10-28` — Built; web 237 passed (HOME-01, SHL-04, SHL-01, app-core, routes, shell, dist); backend `test_i01t13_home_wire_up.py` + `test_i01t08_registrations.py` 8 passed; ruff, pyright, lint-imports, banned patterns, validate_docs clean.

## Handoff
- **Current state:** PR open, held for the S14 batch (stacked on #555).
