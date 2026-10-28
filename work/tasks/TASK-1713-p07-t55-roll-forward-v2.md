---
id: TASK-1713
title: P-07-T55 Roll-forward v2 (ENG-13 backend)
spec: SPEC-321
acceptance_criteria: [AC-30]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T55
branch: s14-p07-t55
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ENG-13's backend: roll a released engagement (delivered or archived) into next year's through a
saved draft and one Create, carrying the v1 categories (team, template at its current version,
request list as Draft, prior-year notes) with `prior_engagement_id` and a continuance acceptance
record, behind `engagements.roll_forward_v2`. Acceptance (backlog row): "Northwind PY2025 rolls
into PY2026 with 24 requests as Draft, no evidence copied, and an active source answers 409."

## Plan (amber)
- Contract first, in the same PR: `roll_forward_contract.py` (five routes, models), `make
  regenerate` (client, generated security tests), `docs/contracts/engagements-v2.md` §8a.
- Migration `0291_roll_forward_drafts` (down `0290`): the draft table, owner-scoped, insert and
  update column grants, no delete; `registry.py` entries.
- `roll_forward_v2.py`: draft create/read/autosave/discard, `check_create`, Create in one unit of
  work (insert Prospect, claim the draft, team via `add_rolled_forward_member`, pin the template,
  `acceptance.open_record` → continuance, request copy through the `register_draft_request_copy`
  slot that `requests` fills with `count_prior_items` and `copy_items_as_draft`).
- Matrix: `roll_forward.create` (new), `roll_forward.read` + engagement partner and manager.
  Flag `engagements.roll_forward_v2` (seed and scenario loader on). Error codes
  `roll_forward_source_not_released` 409, `roll_forward_invalid` 422; `stale_version` reused.
  Audit actions in the reviewed fallback list. DEC-805; SPEC-321 AC-30.
- Rollback: flag off; revert the branch and downgrade 0291.

## Acceptance
| Check | Test |
|---|---|
| Northwind PY2025 → PY2026: 24 requests as Draft, no evidence copied, Prospect + continuance record, team carried | `backend/tests/integration/backfill/test_p07t55_roll_forward_v2.py::test_ac_northwind_py2025_rolls_into_py2026_with_24_requests_as_draft` |
| An active source answers 409 (at draft and at Create) | `…::test_ac_an_active_source_answers_409_and_writes_nothing`, `…::test_a_source_made_active_after_the_draft_refuses_create` |
| Skip choices, stale version, invalid choices, replay, discard | four tests |
| Staff refused, another's draft 404, walled 404, firm admin may, flag off 404 | three tests |

## Progress log
- `2026-10-28` — Built. `test_p07t55_roll_forward_v2.py` 12 passed; ruff, pyright, lint-imports,
  banned patterns, error-code catalogue, `make regenerate`. Mistake caught by the tests: a route
  whose declared action the service never authorised (discard, and an idempotent replay) is
  `authz.unchecked_route` → 500; fixed with `check_create` before the key lookup, as ENG-03 does.

## Handoff
- **Current state:** PR open, held for the S14 batch (stacked on #569).
- **Next:** P-07-T60 (ENG-13 screen, fixture a–c, live d–e).
