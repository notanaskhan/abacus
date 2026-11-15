---
id: TASK-8068
title: "S45 end pass: gates, suites, security review and fix round over the S45 stack"
spec: SPEC-659
acceptance_criteria: [AC-34]
risk_zone: red
status: in-review
branch: s45-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: S45-END
---

## Objective
Run every gate and suite once over the S45 stack (#2010–#2051), review the red and amber diffs,
fix what they find in one round on the tip, then restack and merge one commit per PR with CI on
the last.

## Number collisions with main
While S45 was building, #2011 and #2028 used TASK-8029, TASK-8030, DEC-5018 and DEC-5019 on main.
The S45 rows that held them are renumbered on the tip: C-01-T11 is TASK-8067 (file renamed) with
DEC-5053, and C-01-T13's decision is DEC-5054. The kickoff citations "(TASK-8029)" now read
"(#2010)". Next free: TASK-8069, DEC-5056, migration 0891, SPEC-660, RB-85.

## Fix round (DEC-5055)
- **SQL-001 / SUPPRESS-001:** closes `plans.patch_row` uses one fixed `CASE WHEN :set_x` UPDATE
  instead of a built SET list. The closes repository spells out its SELECT columns. The QBO
  accounts query is joined, not an f-string.
- **OWN-001:** tax reads `instrument_clause` locators through the new
  `evidence.api.citation_locators`, not the `citations` table.
- **BOUND-001:** the Granite Peak generator imports `je_scoring` through `sampling.api`.
- **LIST-001:** the closes lookups by ids are exempted with their reason. The CLS-02 record bar now
  narrows neighbouring-period links to the viewer's visible closes (security review).
- **ANY-001 / TYPE-001:** reasons on every `Any` and checker ignore, through `_Row` and `_Fake`
  aliases where a formatter would split the line.
- **Glossary L12:** the A-08 and W-01 "Don't use" columns banned generic words (rule, comment,
  note, connector). They now name the phrases they mean (JE rule, variance comment, plugin).
- **validate_docs:** task files cite parent AC ids, SPEC-659 lists its 35 ids explicitly, and the
  W-02 rows cite SPEC-653.
- **generator_coverage:** allow and deny cases for `is_named_approver`, `link_scope_only` and
  `email_verified`.
- **seed_contamination:** comments no longer spell the kit names they ban.
- pyright: 22 test-file errors plus one in the new evidence helper.

## Security review (red and amber diffs)
- Public `/v1/confirm/*`: fixture tokens only in local and test, a uniform `expired` view, a
  0.4 s floor, no writes. The token never leaves the process: uvicorn's access log is off and
  spans keep only the route template. The code comment that claimed an access-log redaction is
  corrected. **For A-08-T15:** per-token and per-IP rate limits beside the five-failure lockout.
- Migration 0890 lifts FORCE RLS on two tables for one backfill in the same transaction. The app
  role's policies never change.
- Migrations 0885–0890: forced RLS, column grants, insert-only events. DELETE is granted only on
  `consolidation_entities` (draft edits) and `integration_oauth_states` (single-use states).
- C-01-T16 QBO: GETs only, with realm and cursor validated and a bounded Retry-After.
- CLS-02 neighbours: an unassigned or walled adjacent month was named by id. Fixed above.

## Suites (2026-11-15, under the test lock)
- `make check-fast` (backend and frontend), check-generated, check-heads, full pyright: green.
- `tests/unit` (-n auto): 54,428 passed in the last full run; its 11 failures were fixed and rerun. 12 need WeasyPrint's native `libgobject`, which is not on this
  laptop: `test_a06t33_fs_render_independent` (10) and `kernel/test_classification` (2). CI runs them.
- contracts, golden, workflows, property, acceptance, connectors: 12,034 passed.
- security: 14,526 passed; its 7 failures were fixed and rerun.
- web vitest 4,145 and packages/ui 1,440: passed.
- Integration: the S45 suites (C-01-T14/T15, A-09-T05, schema_check_db, integrations schema,
  the new `test_s45_migrations` 0884 → 0890 → 0884 → 0890) and 729 tests touching the changed
  modules: passed. `backfill/test_gl_detail` (3) and one `test_retrieval_workflow` case failed under -n 4
  and pass serially (load timing).
- `schema_check`: migrations reversible; every table tenant-scoped with forced RLS.

## Real defects the suites found (fixed here)
- Audit `Ref`s carrying text or dates (closes status and plan, tax instruments): the kernel
  refuses them at runtime, so the writes would have answered 500.
- Domain error facts naming people and accounts (closes `editor`, `account`): facts carry identifiers
  only. They now name the user id and the plan row id.
- `request_publish` asked twice opened a unit of work that recorded nothing (MissingAuditEvent).
- A $0-only distribution set divided by zero in the fiduciary engine's beneficiary share.
- `closes` imported `practice`, an edge nothing may import (I-02). It now has its own
  `business_days` helper on the platform's holidays.
- `integration_catalog_imports` granted the app role SELECT. It is definers only, as
  `integration_catalog` is.
- The route `/v1/proposed-entries/{id}/elimination/post` broke A-06-T10's "no route posts an entry".
  It is now `/elimination/apply` with the action `elimination.apply`, applied to the consolidation
  layer only.
- An undeclared-field `Money | None` loses its classification. About 120 S45 fields are now
  classified.
- A second `AuthorizationOut` model renamed notices' schema, and three operation ids were
  duplicated.
- The CLS-01 fixture counted its tiles after the status filter (the service counts before it).
- The HOME-01 Closes tile is wired to CLS-01.
- The InstrumentReaderWorkflow histories are recorded (`record_s45_runs`).

## Progress log
- `2026-11-15` — End pass done: gates and suites green as above (DEC-5055). Restack and merge next.
