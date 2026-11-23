---
id: TASK-8901
title: "K-03-T11: Migration templates_v2_core (methodology)"
spec: SPEC-720
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-k03t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-22
updated: 2026-11-22
plan_key: K-03-T11
---

## Objective
engagement_templates and template_versions above K-01's methodology versions, draft-only component tables, scoping_rules, agent_skills and versions, guard triggers, wrapper bootstrap. Acceptance: the migration goes up/down/up on testcontainers, a published version or its components refuse UPDATE and DELETE, and every published methodology version gets exactly one published template-version wrapper.

## Done
- Migration 1010_templates_v2_core: 16 tables (engagement_templates, template_versions, 11 component tables incl. scoping_rules, template_changes, agent_skills, agent_skill_versions), forced RLS, column grants
- template_version_guard (published/deprecated rows move only status→deprecated, deprecated_by/at, effective_to, retired_at, overlay_stats; no delete) and template_component_guard (components move only while their version is a draft; a discarded draft cascades)
- One draft per template (partial unique index); 11 column types and classification NOT NULL on sheet columns and form fields
- Bootstrap: one engagement_templates row per methodology template; one published wrapper (origin bootstrap) per published or superseded methodology version and per version an engagement pins, superseded ones retired
- methodology registry TABLES / INSERT_ONLY / INSERT_COLUMNS / UPDATE_COLUMNS (the S52 TABLE_OWNERS carry), tenant-isolation list, schema-check update snapshot
- tests/integration/test_k03t11_templates_v2_core_migration.py (6 tests; run at the end pass)

## Progress log
- `2026-11-22` — Built in the S53 sequential stack (DEC-5903). Spec §4 template_changes added here (frozen change list per version pair); template_checks stay computed. Pinned non-published versions are wrapped too so K-03-T12's link backfill covers every pin.

## Plan (amber)
1. `backend/migrations/versions/1010_templates_v2_core.py` (down_revision 1003): tables, guards, grants, bootstrap under NO FORCE RLS re-forced in the same transaction.
2. `methodology/registry.py`: tables, insert-only, insert and update columns.
3. Tests: up/down/up with wrappers; pinned draft wrapped; published version and components refuse UPDATE/DELETE (AB409); draft discard cascades; classification NOT NULL and the 11 types; skills and change lists insert-only.
4. Rollback: downgrade drops the 16 tables and both functions; no existing table changes.
