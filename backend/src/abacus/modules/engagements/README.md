# engagements

One job for one client and one fiscal period (glossary). Owns `engagements` (ADR-103).

## Public interface (`api.py`)
- `router`: `POST /v1/engagements` (`engagement.create`), `GET /v1/engagements` and `GET /v1/engagements/{id}` (both `engagement.read_metadata`; metadata only, ADR-024).
- `get_ref(ctx, engagement_id) -> EngagementRef` raises `NotFound` (404) when the engagement isn't in the active tenant. `ref.resource()` gives the `Resource` to authorise against, with `archived` from the row.

## Rules
- Creating an engagement also creates its client and client entity (organisations) and makes the creator its `engagement_partner` (identity), all in one unit of work. Audit events: `client.created`, `client_entity.created`, `engagement.created`, `engagement_member.added`. Outbox event: `engagement.created`.
- Lists apply `visible(ctx, "engagement.read_metadata", Engagement.id)` (LIST-001).
- Content (request items, evidence) lives in other modules, under their own actions.

## Methodology templates (SPEC-008)
A firm imports its methodology as numbered versions of a named template. Each version is immutable.

- **Import:** `POST /v1/methodology/templates/{name}/versions` takes the raw `.xlsx` workbook as the request body.
- **Read:** `GET /v1/methodology/templates` and `GET /v1/methodology/versions/{id}`.

The workbook has three sheets, each with exact headers in row 1. Blank rows are ignored. `docs/product/methodology-sample.xlsx` is a sample.

| Sheet | Columns |
|---|---|
| `Areas` | `code` (up to 20 characters), `name` (up to 100) |
| `Requests` | `area_code`, `description` (up to 2,000), `tier` (A to E) |
| `Account rules` | `area_code`, `account_from`, `account_to` (an inclusive range compared as text) |

**Rejected workbooks:** a rejected workbook stores nothing and gets 422. Each problem is reported as `loc` (sheet, row, column) and `msg` (a fixed code), never cell contents. The codes:
- `not_a_workbook`, `too_large`, `missing_sheet`, `missing_header`;
- `empty_value`, `too_long`;
- `duplicate_area`, `unknown_area`, `no_areas`;
- `invalid_tier`, `invalid_range`, `overlapping_range`;
- `too_many_rows`.

**Pinning:** `pin_methodology` pins an engagement to one version, once (`MethodologyAlreadyApplied`). Callers use it inside their unit of work, as `requests.apply_methodology` does. `area_for` maps an account code to its area: the first rule in rule order wins.
