---
id: TASK-1336
title: AUD-06 read model in assurance, the live C9 view by layer and leadsheet by area (A-02-T10)
spec: SPEC-333
acceptance_criteria: [AC-5, AC-9, AC-17, AC-18]
risk_zone: amber
status: in-review
epic: A-02
plan_key: A-02-T10
branch: s10b-ledger-integrations
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The C9 consumer suite passes against live routes, a walled member gets 404 with no hidden count,
and a member without an independence confirmation is refused independence_pending."

Most of the row's list is live since SPEC-309..311 (TB list, candidates with a code-computed diff,
leadsheets, checks projection, adopt routes). Left: C9 v1's view by layer and leadsheet by area
(stubs since A-02-T03), with the binding items from #417's security review.

## Plan
- `assurance/tb_read_model.py` (new): `area_rules` (the engagement's own applied methodology
  version, read in `tenant_session(ctx.tenant)` through `engagements.api.version_detail` on every
  call, no cache); `layer_view` (authorise, flag, read; `ledger.require_balanced`; groups by area
  with Unassigned last and code-computed subtotals; layer balance; provenance with source kind
  and adopter's name; checks summary and off-check flags from `workpapers.api.checks_for`;
  newer-snapshot count from `ledger.api.candidates`; `allowed_actions` from
  `identity.api.allowed_actions`); `leadsheet_area`; the two routes on `tb_router`.
- `tb_contract.py`: the two stubs removed (models stay); `assurance/api.py` imports the router
  from `tb_read_model`.
- `ledger/trial_balances.py`: `VersionInfo.source_kind` and `prior_period_end` (additive).
- `IndependencePending` (403 `independence_pending`, C9 §6) for the `independence` layer only.
- Tests: `tests/security/test_a02t10_tb_read_model.py` (live routes on two firms: groups by the
  engagement's own rules, leadsheet and Unassigned, layer_unavailable, walls 404 identical to a
  missing engagement, independence_pending, flag 404, one firm's rules never group another's);
  `tests/unit/assurance/test_tb_read_model.py` (require_balanced before any other read, rules
  read each call, no module-level cache); C9 stub and security stub tests move the two routes
  from their stub lists to live.
- Generated: OpenAPI and the API client (`make generate`): the two routes stop documenting 501.
- Rollback: revert; the stubs come back (501), nothing else depends on the live shape yet.

## Progress log
- 2026-10-26: plan written; built with the rest of S10 wave B (tests at the end, brief step 7).

- 2026-10-26: one targeted pass at the end of the wave (brief step 7): 1,520 backend tests in the
  touched and covering files (unit integrations, assurance, ledger, workpapers ties, audit
  targets, release and deploy workflows; C9 and C20 contract suites; the three new schema files,
  test_tb_versions, test_schema_check_db, test_retrieval; security a02t10, c09 authz, route
  introspection, tenant isolation, audit targets): 5 failed, fixed, re-run green (expected-map
  and consumer 501 updates; the a02t10 test now turns on `g2_blocks_view` on an attest
  engagement, since G2 binds reads only there, ADR-164; fieldwork registers the adjustment
  source, so all four layers exist in the app). Vitest AUD-06, AUD-02, C9 and C20 fixture
  contracts: 73 passed. Gates: ruff format/check, pyright, lint-imports, banned_patterns,
  error_codes, validate_docs, scope_guards, fresh_mfa, secrets_scan, check-heads,
  check-generated; tsc, eslint, prettier on touched files. Playwright not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-440 | Rule loading without a cache, require_balanced, independence_pending mapping, totals and ticks left empty | No |
