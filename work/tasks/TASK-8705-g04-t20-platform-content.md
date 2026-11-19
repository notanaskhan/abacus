---
id: TASK-8705
title: "G-04-T20: Platform content as DB rows: operator writers, content-import loader and runbook"
spec: SPEC-680
acceptance_criteria: [AC-50, AC-53]
risk_zone: green
status: in-review
branch: g04-t20-platform-content
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: G-04-T20
---

## Objective
Production platform content (help articles, status component catalogue, region rows, support hours) loads as database rows from a reviewed content folder outside the repository: migration 0980 adds the operator-only writers the catalogue lacked, `platform_console content-import` loads a folder in one transaction, and the runbook names the two-founder steps. No content row is committed.

## Plan (green)
1. Migration 0980 (on 0969; re-chain at merge): status_component_upsert, platform_region_upsert, platform_setting_put (support_hours only, version-checked), SECURITY DEFINER, abacus_ops only, each audited.
2. schema_check: the three in DEFINER_FUNCTIONS and OPS_ONLY_FUNCTIONS.
3. abacus_tools/platform_console.py: content-import --dir [--dry-run].
4. tests/unit/platform_module/test_g04t20_content_import.py (temporary folder; nothing committed).
5. docs/runbooks/platform-content-v1.md.
6. Rollback: downgrade drops the three functions; content rows stay as data.

## Progress log
- `2026-11-19` — Built; unit tests pass (4). Not done (human): the reviewed production content itself, the staging and production loads and the second founder's publishes; email template rows through R-01's import. Migration round trip at the S51 end pass (schema_check). Gates and tests run once at the S51 end pass (build first, test last).
