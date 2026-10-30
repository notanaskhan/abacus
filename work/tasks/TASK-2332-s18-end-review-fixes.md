---
id: TASK-2332
title: S18 lane 2 end review — security, tests and gates fixes
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: T-01
plan_key: S18-review
branch: s18-review-fixes
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
One review of the 30 S18 lane-2 PRs (#751, #816–#867) on a tree with all of them merged onto main:
security review of the red diffs, the gates, targeted tests; fixes land here as the last PR of the
batch so `main` equals the reviewed tree.

## Plan
- Re-chain 0460 onto main's 0407 and 0464–0468 linearly after 0463.
- Gate fixes: ruff, pyright, banned patterns (OWN-001 via `audit_of_targets` and the new kernel
  reader `run_reads`; CLOCK-001; TYPE-001; ANY-001), validate_docs task ACs, isolation suite tables,
  schema_check TRUNCATE triggers and update columns, generated client and security tests.
- Bugs: `signatures.imports` declared `StagedFile` twice (T-01-T10's file record renamed
  `UnconsumedFile`; `stage_file` would have built the wrong class); `dispatch` policies missing in
  two starters; TAX-09 posted JSON to the raw-body engine import; KNW-04 publish lacked its
  Idempotency-Key; the KNW-04 draft fixture lost its effective date.
- Security: standards workbooks now parse in the isolated child (as engine and questionnaire
  imports do); consent CSV neutralises tab and CR leads.
- DEC-1378: C11's frozen `TemplateImportIn` key alias (shape unchanged).

## Progress log
- `2026-10-30` — review tree `s18-review2`; fixes as above. `[skip ci]` until the last merge.
- `2026-10-30` — tests: lane unit 5,347 pass; contracts 5,761 (6 fixed); lane integration 6 files and
  security 3 files pass after fixes (engine routes authorise on the return; overview metadata
  readers; draft fingerprint, guidance null and edited columns; dry-run import as a read; six audit
  refs carried text). Isolation for the 12 new tables 22/22. One re-review done (overview moved
  onto the engagement too). Web tsc, eslint, prettier, vitest (lane files) clean.

## Handoff
- **Current state:** fixes on the review tree; PR opens last in the batch.
- **Exact next step:** merge the 30 PRs in order, then this one with CI.
