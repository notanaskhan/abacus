# Presence v1 — who is where, without locking

| Field | Value |
|---|---|
| Owner | platform (F-08-T13; F-08 §F1; ADR P-15; DEC-5844) |
| Status | live (F-08-T13, 2026-11-20) |
| Code | `backend/src/abacus/modules/platform/presence.py`, `presence_routes.py`; `kernel/ephemeral.py` |
| Storage | `presence_heartbeats` (1001; UNLOGGED, forced RLS; one row per person and object) |
| Consumers | C-28 Presence in T18 (cells), T19 (cards), T20 (sections), record bars |

| Method and path | Action | Notes |
|---|---|---|
| `PUT /v1/presence {object_kind, object_id, anchor_kind, anchor_key}` | `presence.update` | a heartbeat every 15 s; `anchor_kind` ∈ cell · section · card · record (`anchor_key` required except for record); 404 for an unregistered kind or an object the caller cannot read |
| `GET /v1/presence?object_kind=&object_id=` | `presence.read` | who else is on the object now (seen in the last 45 s), oldest join first; never the viewer |

**Slot.** An object kind joins only through its owner's `register_presence_kind(kind, may_read)`
(fail closed). `work_item` is registered by engagements (content read on the work item).

**Topic.** `presence:<kind>:<id>` (identifiers only), subscribed only with the object's read access;
each heartbeat wakes it.

**Documented exception (chapter 03 §7.1).** Heartbeats are not audited and never go through the
outbox: `kernel.ephemeral.ephemeral_write` accepts only tables in `EPHEMERAL_TABLES`. Presence never
locks a cell, section or card.
