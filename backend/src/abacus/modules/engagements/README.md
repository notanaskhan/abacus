# engagements

One job for one client and one fiscal period (glossary). Owns `engagements`, its work items and their setup records (`registry.py`; ADR-103): `work_items`, `assurance_work_items`, `advisory_projects`, `work_item_assignments`, `engagement_entities`, `engagement_contacts`, `gate_policy_overrides`, `independence_confirmations`, `engagement_letters`, and the methodology tables. Map: `docs/architecture/data-model.md`.

## Work items, the lifecycle and gates (C1; F-03, `docs/contracts/work-items.md`)
- **Work items** (`work_items.py`, migration 0068): the units of work inside an engagement, of kind `assurance`, `tax_return`, `close`, `notice` or `advisory_project`. The `engagement_work_item_defaults` trigger gives every engagement one `primary` `engagement_entities` row and, for the ten attest types, its one `assurance` work item (at most one per engagement).
- **Kinds** (`slots.py`; ADR-106 pattern): each kind's owner calls `register_work_item_kind(kind, provider)` from its `api.py` (`assurance` and `advisory_project` here; `tax_return` in tax, `close` in closes, `notice` in notices). `create_work_item(ctx, engagement_id, kind, *, name, client_entity_id, due_on, details)` (action `work_item.create`, partner and manager) writes the work item and the kind's subtype row in one unit of work and audits `work_item.created`. An unregistered kind is 409 `unknown_work_item_kind`; a breach of the kind's cardinality (a second assurance item, a second close for a period) is 409 `work_item_exists`. Adding a kind: `.claude/skills/backend-module/SKILL.md`.
- **Reads:** `GET /v1/engagements/{id}/work-items` and `GET /v1/work-items?engagement_id=&kind=&status=&cursor=&limit=` (both `work_item.read_metadata`). The firm-wide list uses `visible_scope(..., "work_item", ...)` and the list envelope (`kernel.listing`: keyset cursor, per-status counts without the status filter, capped total). It is live for every firm: `engagements.work_items_api` was retired with P-07-T15.
- **Lifecycle** (`transitions.py`, migration 0069; DEC-39): 14 engagement types and 8 states (`prospect`, `accepted`, `declined`, `contracted`, `active`, `on_hold`, `delivered`, `archived`). Every legal move is one row; anything else is 409 `illegal_transition`. Accept, decline and hold are human-only (INV-1). Each move writes one audit event and one `engagement.status_changed` outbox event.
- **Gates** (`gates.py`, `gate_policy.py`): G1 acceptance, G2 independence, G3 the letter, registered in the gate slot; `required_gates(type, overrides)` gives the gates a type needs. A firm's `gate_policy_overrides` may only tighten a gate.

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
- **Read:** `GET /v1/methodology/templates` and `GET /v1/methodology/versions/{id}`. `?latest=true` keeps each template's newest version only: what "New engagement" and Overview offer (SPEC-025 AC-3; TASK-047). "New engagement" preselects the only template for the type (or asks, with several), creates the engagement, then applies it as its new partner.
- **Drafted guidance (SPEC-035 Q3; TASK-074):** `publish_drafted_version(tx, ctx, version, approved)` makes the next version from the latest, with approved drafted guidance on its items (`guidance_source` `drafted`, `guidance_approved_by`); audited `methodology.published`. Applying or rolling forward carries that provenance into request items, so the client display rule applies.

The workbook has three sheets, each with exact headers in row 1. Blank rows are ignored. `docs/product/methodology-sample.xlsx` is a sample.

| Sheet | Columns |
|---|---|
| `Areas` | `code` (up to 20 characters), `name` (up to 100) |
| `Requests` | `area_code`, `description` (up to 2,000), `tier` (A to E); optional after them (SPEC-031): `why`, `good_looks_like` (up to 1,000 each), `blocks_fieldwork` (yes or no), `effort` (small, medium, large) |
| `Account rules` | `area_code`, `account_from`, `account_to` (an inclusive range compared as text) |

**Rejected workbooks:** a rejected workbook stores nothing and gets 422. Each problem is reported as `loc` (sheet, row, column) and `msg` (a fixed code), never cell contents. The codes:
- `not_a_workbook`, `too_large`, `missing_sheet`, `missing_header`;
- `empty_value`, `too_long`, `invalid_effort`, `invalid_yes_no`;
- `duplicate_area`, `unknown_area`, `no_areas`;
- `invalid_tier`, `invalid_range`, `overlapping_range`;
- `too_many_rows`.

**Pinning:** `pin_methodology` pins an engagement to one version, once (`MethodologyAlreadyApplied`). Callers use it inside their unit of work, as `requests.apply_methodology` does. `area_for` maps an account code to its area: the first rule in rule order wins.

## Engagement types (SPEC-024 AC-6; TASK-040)
- **Types:** SPEC-024 began with `audit`, `review`, `compilation` and `agreed_upon_procedures`. Since migration 0069 (F-03-T12) there are 14: `fs_audit` (formerly `audit`), `ebp_audit`, `review`, `compilation`, `preparation`, `agreed_upon_procedures`, `soc1`, `soc2`, `readiness`, `internal_audit`, `tax_compliance`, `cas_monthly_close`, `notice_response`, `advisory`.
- **Templates:** a methodology template is tagged when created with the types it serves (`engagement_type`, repeatable, on the upload route). Templates stay insert-only, so a new set of types means a new template.
- **Applying:** `pin_methodology` refuses a template that doesn't serve the engagement's type (409 `template_type_mismatch`).

## Onboarding checklist (SPEC-024 AC-7; TASK-042)
`onboarding.py`, routes on `firm_router`:
- `GET /v1/firm/onboarding` (`firm.read_settings`);
- `POST /v1/firm/onboarding/{sso|budget|walls}/acknowledge` and `/dismiss` (`firm.manage_settings`).

Seven steps, each computed from data (identity's `firm_facts` plus this module's template and engagement counts), never stored as done. SSO can only be skipped while it's held.

## Clients you already have (SPEC-025 AC-1; TASK-043)
- **Picker:** `GET /v1/firm/clients/search?q=` (`client.read`) lists matching clients with their entities, minus any the person is walled off from.
- **Creating:** `POST /v1/engagements` takes an existing `client_id` (and `client_entity_id`, or a new entity name).
  - A walled creator is refused before anything is written, and again by `authorise` on the engagement inside the unit of work.
  - A new client whose normalised name matches an existing one is refused (409 `possible_duplicate`) unless `confirm_new`.
- **Labels:** `engagement_label` gives communications the engagement, client and fiscal year for invitations in the firm's name.

## Acceptance, independence, the letter and the gate (SPEC-025 AC-4 to AC-7; TASK-044)
`setup.py`. These are recorded, not performed.
- **Acceptance** (`acceptance.record`, the engagement partner, fresh MFA): decision, kind (pre-filled from the client's earlier engagements), where it's documented, the predecessor auditor (new clients), and the partner's independence conclusion. Each save is a new row; the newest is live, and the file and predecessor fields carry forward.
- **Independence:**
  - every team join (added member, creator, self-joined administrator) asks the person to confirm, through identity's `register_member_added` hook, and notifies them (`independence.requested`);
  - `independence.confirm` is for oneself only; a decline needs a note, which only the partner and manager see.
- **Letter** (`letter.record`, partner and manager): status, date, a reason (when not required this year), and a link or signed copy.
- **The gate:** `gate_client_data` / `require_open` refuse client invitations, connections, retrievals, client uploads and inbox actions until acceptance is `accepted` and the partner has concluded (and the letter is recorded, if the firm requires it). Each refusal is audited `client_data.gate_refused`, with codes `acceptance_missing`, `acceptance_declined`, `independence_conclusion_missing` and `letter_missing`. Automatic retrieval waits too.
- **Roll-forward (AC-2; TASK-048):** `POST /v1/engagements/proposal` (nothing stored) finds the entity's latest earlier engagement of the same type (others offered as a choice) and proposes its team (anyone who has left or is walled shown as not available), its template at the latest version, and its items: accepted ones ticked, all others unticked, the template's additions (matched by area and description, case and spacing ignored) flagged and ticked. `roll_forward.read` is checked on that engagement, so walls apply. `POST /v1/engagements` with `roll_forward` creates exactly what was confirmed in one unit of work: `prior_engagement_id`, the creator as partner, the team through identity's `add_rolled_forward_member` (re-checked), the latest version pinned, and the ticked items copied by requests through `register_roll_forward_items` (ADR-106); audited `engagement.rolled_forward`. A template that changed since the proposal (`proposal_changed`) or a person no longer available (`team_member_unavailable`) refuses the whole creation.
- **The setup page (AC-10; TASK-046):** `GET …/setup` also returns `steps` (client and period, team, request list, acceptance, the partner's conclusion, team independence, letter, client contacts: each with a state, who acts next and, when blocked or a warning, a plain reason) and a one-line `summary`. Both are computed in `setup_steps.py` from facts the view already reads, never by a model. Client contacts are counted only; who they are stays behind `client_contact.read`. The web's Setup tab shows them with the records' panels, and an engagement opens on Setup until it's open for client data.
- **Per person (TASK-045):** engagements registers `confirmed_subquery` / `confirmed_for` with identity (`register_independence`), so a team member reaches the engagement's client data only once their own confirmation is `confirmed`. Someone added later is restricted alone; declining closes it to them again. The web shows "Confirm your independence to see client data" on the engagement until they do.
- **Existing engagements:** marked "accepted, before Act 1", with their staff confirmed, by migration 0036.
- **Still to come:** per-person access to client data is TASK-045, in `authorise`.

## AI exclusion (SPEC-036; TASK-076)
`GET/PUT /v1/engagements/{id}/ai-exclusion`: the engagement partner (`engagement.ai_exclude`) switches AI off with a reason, or on again; audited, and the gateway refuses every model call on the engagement while it's off (`ai_excluded`, registered).

## Frozen contracts (P-07-T64; DEC-1054)

Frozen at v1 on 2026-10-29; the snapshots under `backend/tests/contracts/p07_*/v1.json` fail the
contract tests on any removed or retyped field, newly required field or removed enum member. A
breaking change ships the next version with overlap (`python -m abacus_tools.contracts --freeze`).

- `docs/contracts/engagements-v2.md`
- `docs/contracts/acceptance-independence.md`
- `docs/contracts/intake-import.md`
