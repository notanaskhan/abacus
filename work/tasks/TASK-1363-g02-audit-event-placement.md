---
id: TASK-1363
title: Fill client_id and office_id on audit events; the explorer uses them (G-02-T08 gap)
spec: SPEC-349
acceptance_criteria: [AC-4, AC-7]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T08
branch: s10c-audit
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Writers fill neither `audit_events.client_id` nor `office_id` (DEC-434, DEC-436), so ADM-07's
Office filter matches nothing and the explorer's stored-client wall clause never fires. Make the
unit of work record both, without the kernel importing a module or naming a module's table
(ADR-101, OWN-001), and make the explorer rely on them on top of the ref-based rule.

## Plan
- **Kernel** (`kernel/uow/placement.py`, new; `kernel/uow/__init__.py`):
  - `Scope` gains `client_id` and `office_id` (optional), for events whose writer knows them
    and that have no engagement.
  - Two registration slots, as `request_context.register_session_resolver` does for identity:
    `register_engagement_placer` (engagement, work item -> client, office) and
    `register_client_placer` (client -> primary office). The kernel calls them on the unit of
    work's own connection (same transaction, same tenant RLS) and never names their tables.
  - `_write` places each event: its engagement is `scope.engagement_id`, else the target when
    the target is an engagement; with one, the engagement placer's client is authoritative, and
    the office is the work item's, else the engagement's, else the client's primary office
    (DEC-415 Q9 "engagement or client primary office"). With none, a `client` target is its own
    client; otherwise the scope's explicit values. An explicit scope value that disagrees with
    the derived one raises (a writer bug, never silently stored). One batched query per placer
    per commit.
  - Both columns are already in the hash chain's leaf v2 (`chain.py` `LEAF_V2_COLUMNS`) and the
    app may already insert them (0172 `insert_columns`): they are written with the row and never
    updated, so the chain stays valid. **No migration** (0199 not used).
- **Engagements** (`engagements/audit_placement.py`, registered from `engagements/api.py`) and
  **organisations** (`organisations/audit_placement.py`, from `organisations/api.py`): the
  placers, each over its own tables only.
- **Explorer** (`audit_trail/explorer.py`): the stored-client wall clause stays (it applies to
  every reader and kind); the ref-based firm-level rule (`FIRM_SAFE_REFS`,
  `CLIENT_SIDE_TARGETS`, `targets.FIRM_LEVEL`) is unchanged, since history stays unfilled.
  Office filter on the event's stored office. The actor-office fallback (DEC-415 Q9) needs an
  identity reader of an office's people; identity has none (`member_facts` is one person), so it
  stays a gap.
- Docs: DEC-458 (supersedes DEC-436's gap note in part), `docs/contracts/audit-log.md`.

## Tests
`tests/integration/test_g02t08_audit_placement.py`: the unit of work fills both from a scope's
engagement, from an engagement target, from a work item's office override and from a client
target; a mismatched explicit client raises; the hash chain verifies over placed rows; a walled
firm-level reader cannot see an event whose stored `client_id` is walled (list, detail, counts);
the Office filter matches a placed event and not others.

## Rollback
Revert the commit: the columns go back to null for new events; rows already placed stay placed
(they are part of the sealed leaf) and the explorer reads them as before.

## Progress log
- 2026-10-27: built as planned, no migration (0199 unused: both columns are already in leaf v2
  and insertable). The explorer's stored-client wall clause already existed (S9 review); it now
  has data, and its test shows it hiding a firm-level hold the ref rule alone would show. Office
  filter: stored office only; actor-office fallback still a gap (no identity reader of an
  office's people). DEC-458. Targeted pass (17 files, -n 2): 452 passed, 3 failed, none from
  this change: ED-127 (`agent_stage.changed` uncatalogued and unplaced, two unit tests) and
  ED-128 (0172 up-down-up fails re-adding 0180's `methodology_templates.family`).
