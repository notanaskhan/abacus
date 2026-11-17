---
id: TASK-8409
title: "A-09-T30: Host registrations before the window"
spec: SPEC-658
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: a09-t30-host-registrations
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T30
---

## Objective
Spec section: docs/plan/epics/A-09.md §3.1, §5. Host registrations before the window: ENG-03 g group work item and component engagement_entities under the capability, Group band audit section with rail states, Component auditor index tag and group rows, AUD-06 entity strip API, AUD-07 flag-off routing.

## Plan (amber)
1. Migration `0946_group_work_item.py` on 0945: `assurance_work_items.is_group_audit` writable by the app role; engagements registry.
2. ENG-03 g: `create_from_draft` marks the assurance work item a group audit and inserts the chosen entities of the same client as `engagement_entities` role `component` (`component_entity_ids` on the draft payload; others ignored); audited `engagement.group_audit_set`.
3. `assurance/group_hosts.py`: three Group band rows per AUD-02 revision h (Structure, Scoping, Component auditors) with the handoff's sub-lines, AUD-01 tags `group` and `component_auditor`; every provider answers nothing unless `group_audit_on` and the work item is a group audit; AUD-06 g entity strip (`GET /v1/audits/{wid}/group/entities`).
4. AUD-07 flag-off routing is the screen's (A-09-T32): with the capability off the Materiality row keeps opening AUD-07 because no Group band exists.
5. Tests: `tests/unit/assurance/test_a09t30_group_hosts.py`. Rollback: `alembic downgrade 0945`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5408). Lint and pyright clean; the app imports. Partial: AUD-01's nested group rows (component engagements under the group row) need the index list's grouping, which is the screen row A-09-T32's; the Harlow & Pike demo state (Finalized 10:48 AM) needs the seed slice. Gates and tests run once at the S48 end pass (build first, test last).
