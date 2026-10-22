---
id: TASK-409
title: Migration 0094 - decision cards and decisions, checkpoints, issues (P-04-T04)
spec: SPEC-308
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T04
branch: p04-t04-cards-checkpoints-issues
created: 2026-10-22
updated: 2026-10-22
---

## Objective
P-04-T04: a decision or checkpoint decision with actor_kind agent is refused by the database. The decision, checkpoint and issue tables follow P-04 §4.2 and ADR-160.

## Plan
- Migration 0094.
- `review/registry.py` owners and insert-only lists.
- The schema_check immutable list and its test expectations.
- Regenerated isolation tests.
- Rollback: `alembic downgrade 0093`.

## What changed
- **`decision_cards`:** registered kind, version, question key, reserved role (engagement partner, manager, EQR reviewer, signer), and code-computed options, context and factors. Blocking refs, `supersedes_id`, raised-by and run. The app may update only `status`.
- **`decisions`:** one per card, insert-only by trigger. The sealed rationale is required. The human-only CHECK is bound to the `app.actor_*` settings, so an agent decision is refused.
- **`checkpoints`:** a seq per target. The app may update only name, star and status; "Current" is derived (ADR-160).
- **`checkpoint_diffs`:** insert-only.
- **`checkpoint_decisions`:** insert-only and human-only.
- **`issues`:** the kinds, priorities and statuses of §4.2, sealed title, client wording and internal note. `blocks` ⊆ {final_approval, export, release, sign_off}, with a partial unique index on `(tenant, work_item, source_ref)` for dedupe.
- **`issue_events`:** insert-only; the actor is the transaction's, and resolved, verified or not-applicable events must be a human's.
- **`issue_links`:** insert-only.
- All of them are tenant tables with forced RLS.

## Progress log
- 2026-10-22: `test_schema_check_db` passes (180), including up, down and up, with 0094 and 0095 stacked.
