---
id: TASK-1426
title: Knowledge catalog read model - provider and usage slots, methodology provider, queue, change log, search (K-01-T03)
spec: SPEC-008
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: K-01
plan_key: K-01-T03
branch: s11-home
created: 2026-10-27
updated: 2026-10-27
---

## Objective
`GET /v1/knowledge/items`, `/review-queue` and `/change-log` answer for real: cards from
registered providers with status counts and category facets, usage counts over `visible()`,
lexical search with match ranges, the Draft and Review-queue counting rule. Acceptance: the live
methodology cards with facet counts, an unregistered category returns no count, a walled
engagement is never counted or listed.

## Plan
- `methodology/catalog.py`: `register_catalog_provider`, `register_usage_counter` (fail closed),
  the guard (client 404, `knowledge.read`, flag), `catalog_items`, `review_queue`, `change_log`,
  `match_ranges`. `allowed_actions` decides who sees drafts (manage or approve; no fresh factor:
  seeing is not acting).
- `methodology/catalog_provider.py`: the `methodology` and `pbc_templates` providers (family
  decides the category), cards by the counting rule, queue, change log; registered in
  `methodology.api`.
- `engagements/index_facts.py: methodology_usage` over `visible(engagement.read_metadata)`,
  registered from `engagements.api` (engagements -> methodology is the allowed edge).
- Routes in `methodology/contract.py` (501 dropped); stub tests split into live and stub routes.
- Tests: `tests/unit/methodology/test_k01t03_catalog_slots.py`,
  `tests/integration/backfill/test_k01t03_knowledge_catalog.py`.
- Contract `docs/contracts/knowledge-catalog.md`; `make generate`. DEC-571.
- No migration. Rollback: revert; the flag stays off.

## Progress log
- 2026-10-27: built.
- 2026-10-27: targeted pass green (backend pytest -n 2 on the new and directly covering files, vitest on the touched FE files); gates clean (ruff, pyright, lint-imports, quality tools, check-heads, check-generated, tsc, eslint, prettier, vite build, bundle budget 245.9 of 250 KB). Playwright and axe-in-browser not run in this lane.
