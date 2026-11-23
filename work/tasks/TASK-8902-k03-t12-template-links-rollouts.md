---
id: TASK-8902
title: "K-03-T12: Migration template_links_rollouts (engagements, methodology)"
spec: SPEC-720
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-k03t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-22
updated: 2026-11-22
plan_key: K-03-T12
---

## Objective
engagement_template_links with link events, template_rollouts and actions, template_updates and changes, scoping_evaluations, request shown_by_rule_id; backfill links from engagements.methodology_version_id. Acceptance: every engagement with a pinned methodology version has one link in state current, the legacy column is untouched, a Hold or On rollover action without a reason is refused by CHECK, and the migration is expand-only.

## Done
- Migration 1011: engagement_template_links (+ held/updated CHECKs), insert-only template_link_events, template_rollouts, template_rollout_actions (reason CHECK), template_updates (one applying per engagement), template_update_changes (UNIQUE update_id, change_key), insert-only scoping_evaluations, request_items.shown_by_rule_id
- Backfill: one current link + one pinned event per pinned engagement on its 1010 wrapper, written before archived_guard attaches
- Registries: engagements (links, events, updates, changes), methodology (rollouts, actions, evaluations), requests (shown_by_rule_id insert/update); schema snapshot; tenant-isolation list
- S52 carry: event template_update.available (engagements/events.py) and C16 catalogue entry + sentence 'Template update available for {engagement}.' for kind template_update_available (the rollout start emits it, K-03-T32)
- tests/integration/test_k03t12_template_links_rollouts_migration.py (3 tests; end pass)

## Progress log
- `2026-11-22` — Built in the S53 sequential stack (DEC-5904).

## Plan (amber)
1. `1011_template_links_rollouts.py` on 1010; backfill under NO FORCE RLS before guards attach.
2. Registries, schema snapshot, tenant list. 3. Event + C16 catalogue entry (S52 carry).
4. Rollback: downgrade drops seven tables and the request_items column.
