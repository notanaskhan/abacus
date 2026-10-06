# organisations

Clients and client entities (glossary). Owns `clients` and `client_entities` (ADR-103).

## Public interface (`api.py`)
- `create_client(tx, tenant_id, client_name, client_entity_name) -> NewClient` runs inside the caller's unit of work and records `client.created` and `client_entity.created`. The caller authorises the action that needs it (for now `engagement.create`; client management routes come later).
- `client_names(session, entity_ids)` returns the client and entity names for engagements the caller has already authorised.
