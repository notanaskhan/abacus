# engagements

One job for one client and one fiscal period (glossary). Owns `engagements` (ADR-103).

## Public interface (`api.py`)
- `router`: `POST /v1/engagements` (`engagement.create`), `GET /v1/engagements` and `GET /v1/engagements/{id}` (both `engagement.read_metadata`; metadata only, ADR-024).
- `get_ref(ctx, engagement_id) -> EngagementRef` raises `NotFound` (404) when the engagement isn't in the active tenant. `ref.resource()` gives the `Resource` to authorise against, with `archived` from the row.

## Rules
- Creating an engagement also creates its client and client entity (organisations) and makes the creator its `engagement_partner` (identity), all in one unit of work. Audit events: `client.created`, `client_entity.created`, `engagement.created`, `engagement_member.added`. Outbox event: `engagement.created`.
- Lists apply `visible(ctx, "engagement.read_metadata", Engagement.id)` (LIST-001).
- Content (request items, evidence) lives in other modules, under their own actions.
