---
id: TASK-1125
title: Independent AC tests (ADR-078) for P-07-T15 and P-07-T16 — engagements index, record, recorded letter, catalogue, drafts and create (P-07-T14)
spec: SPEC-321
acceptance_criteria: [AC-16, AC-17, AC-18, AC-19]
risk_zone: amber
status: done
epic: P-07
plan_key: P-07-T14
branch: s7-p07-tests-fe
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The suite passes against T15 and T16 with no edits by notanaskhan's session." Written black-box from
SPEC-321 Story 4 (AC-16 to AC-19), P-07 Stories 6.1 to 6.3, `docs/contracts/engagements-v2.md`,
`docs/screens/ENG-01.md`, DEC-224 and DEC-225, not from `index.py`, `record.py` or `drafts.py`.

## Plan (amber zone)
- **File:** `backend/tests/integration/backfill/test_p07t14_engagements_independent.py` (ac-test-author:
  ayushkbhatia), on the Q-03 back-fill harness (`backfill/support.py`: fresh firm per test, superuser
  seeding, fake-identity tokens, HTTP through `create_app()`).
- **Covers:** tiles and segments foot to `total`, counts ignore the selected tile, a walled engagement
  is absent from rows, tiles, segments and totals (Story 6.1); "Letter │ Not signed" lists Accepted
  engagements and never the Prospect; the record's read-only reason; the recorded letter's G1 rules
  (409 `gate_unmet`, 409 `letter_before_acceptance`, 409 `engagement_archived`, Contracted after a good
  record, one `letter.recorded`); the 18-code catalogue without `single_audit`, SOC behind `attest`,
  group audit only on FS audit; 422 `unknown_engagement_type` on draft and patch; drafts own-scope
  (404 to anyone else) and `stale_version`; G1 blocks step 1 and create; duplicate 409 until
  `confirm_duplicate`; cardinality by type; `Idempotency-Key` required and replayed; agent and system
  refused on `engagement.create`, `letter.record` and `client.intake`.
- **Defects:** small and local → fix with the test and log in `docs/quality/escaped-defects.md`;
  otherwise `xfail(strict=True, reason="ED-nnn: … TASK-1125")`.
- **No** migrations, matrix, flag or registry edits. Rollback: delete the test file.

## Progress log
- 2026-10-24: plan written.
- 2026-10-24: suite written (35 cases + 1 strict xfail), 34 passed on first run against main's code
  apart from my own miscount; three defects found:
  - **ED-017 (fixed):** a partner by level (derived `firm_partner`, DEC-225) got 403 on create: the
    re-check inside the unit of work named the engagement, where derived firm roles never apply
    (DEC-132). It now authorises on the client, as `_check_scope` does (walls still apply).
  - **ED-018 (fixed):** a replay with the same `Idempotency-Key` answered 500
    (`authz.unchecked_route`); the route now calls `drafts.check_create` (action + owner) before
    the idempotency lookup, as binder publish does.
  - **ED-019 (open, strict xfail):** ENG-01 a counts 2 Archived inside 275 under "Period │ Current";
    DEC-224's `current` excludes archived. Needs the period filter decided against the screen
    contract; not a local fix.
  - **Not a defect, reported:** the row's "Hannah creates" — Hannah Leclerc is a Manager, and
    DEC-225 defers DEC-38's manager cell on `engagement.create`; the suite uses a partner by level.
  - **Not testable on the backend yet:** the E0 figures of ENG-01 a–d (275 = 224 + 27 + 23 + 1):
    the backend Brightwater Hale load carries the 27 audits and 214 tax engagements, not ENG-01's
    CAS, advisory, Prospect and Archived rows (waits on F-04-T31's exported seed); the footing is
    proved on a constructed firm instead.
  - Commands: `uv run pytest tests/integration/backfill/test_p07t14_engagements_independent.py
    tests/integration/test_engagement_drafts.py tests/integration/test_engagements_v2_live.py`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
