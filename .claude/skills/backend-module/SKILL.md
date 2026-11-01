---
name: backend-module
description: How to add or extend a backend module — layout, registry.py and api.py ROUTERS, the module graph, tenancy, authorisation, the list envelope, unit of work, registration slots, and adding a work-item kind. Use when creating a module, service, repository, route or work-item kind.
---

# Backend module pattern

**Reference implementation:** `docs/architecture/reference/backend-module.md` (worked example: `modules/requests`). Read it first, with `tenancy-and-authz.md`, `unit-of-work.md` and, for evidence, `evidence-storage.md`. Tables and owners: `docs/architecture/data-model.md`. Schema changes: `.claude/skills/migration/SKILL.md`.

## Layout
```
backend/src/abacus/modules/<name>/
  __init__.py
  api.py          public interface: the only thing other modules import; ends with ROUTERS
  registry.py     TABLES, INSERT_ONLY, INSERT_COLUMNS, UPDATE_COLUMNS (P-39; F-03-T07)
  routes.py       thin FastAPI routes on an AbacusRouter: validate, call service
  service.py      business rules; uses the unit of work
  repository.py   all database access; tenant-scoped session; visible() on lists
  models.py       SQLAlchemy models and Pydantic schemas, every response field classified
  events.py       domain events this module emits
  workflows.py    Temporal workflows, if any
  README.md       purpose, tables, interface, rules
```

## Wiring a module in (each is one edit, no central list beyond these)
- **`abacus/modules/__init__.py` `MODULES`**: the module's name, sorted. The API, the worker and `schema_check` collect every module's `registry.py` and `api.py` from this tuple; a static check keeps it in step with the packages on disk.
- **`api.py` `ROUTERS`**: a tuple of the module's `AbacusRouter`s in mount order (`ROUTERS: tuple[()] = ()` when it has none). `abacus/api/app.py` mounts them in `MODULES` order.
- **`registry.py`**: the four declarations, even if empty. See the migration skill §4.
- **Module graph** (`MODULE_DEPENDENCIES` in `backend/src/abacus_tools/quality/banned_patterns.py`; ADR-008): which modules' `api.py` this one may import. A module not listed may import identity only. Nothing imports portal, notifications, practice, workbench or audit_trail; shared engines never import a service line. A new edge also updates the expected map in `tests/unit/quality/test_banned_patterns.py`.
- **In-module layering** (`[tool.importlinter]` in `backend/pyproject.toml`): add the module to the `routes -> service -> repository` containers list. `uv run lint-imports` checks it.
- **Permission matrix:** actions live in `docs/architecture/permission-matrix/<module>.yaml`; regenerate `_matrix.py` with `uv run python -m abacus_tools.codegen.permission_matrix`, then `uv run python -m abacus_tools.codegen.security_tests` (the generated matrix and route cases). `make check-generated` checks every generator.

## Rules
- Every route is on an `AbacusRouter` and declares one matrix action and a response model (`@router.get(path, action="x.read", response_model=...)`); the route-introspection security test is generated from them (ADR-012, 027).
- Every list query applies `visible(ctx, action, Model.engagement_id)` or `visible_scope(ctx, action, "<kind>", column)` with a literal scope kind (`engagement`, `work_item`, `client`, `client_entity`, `portal_scope`); it also applies ethical walls (ADR-026, LIST-001).
- **Lists use the envelope** from `abacus.kernel.listing`: `clamp_limit`, `query_hash`, `decode_cursor` (bound to tenant, resource and query), `keyset(...)`, `page_of(...)`, `status_counts(...)` (counts ignore the status filter), `capped_total(...)`, then `envelope(...)`. Copy `engagements/work_items.py` `list_work_items`.
- Engagement resources come from `EngagementRef.resource()` (`engagements.api.get_ref` / `lock_ref`) only: it carries the client the wall check needs and `archived`.
- State changes: `async with uow(ctx.tenant) as tx:` → change via `tx.session` → `tx.record("thing.done", target=Target(...))` → `tx.emit(...)` (ADR-018). Never `session.commit()`.
- Modules guarded by a plan use `platform.api.require_entitlement("<module>")` (403 `entitlement_required`); module rollout is never a feature flag (ADR-148).
- Cross-module behaviour flows through **registration slots**: the owner of a slot exposes `register_*` in its `api.py`, the provider calls it at import time in its own `api.py` (for example `register_work_item_kind`, `register_gate_provider`, `register_scope_resolver`, `register_engagement_resource`). A missing registration fails closed.
- New tables: `tenant_id NOT NULL`, row-level security, column grants and the registry (migration skill). Classify every Pydantic response field with `classified(...)` (ADR-031).
- Use glossary names for tables, classes and routes (`docs/product/glossary.md`).
- Log, trace and report errors the observability way: `.claude/skills/observability/SKILL.md` (ADR-022).
- After changing routes or response models: `make generate`; `make check` fails on client drift. A frozen contract's models are checked by `python -m abacus_tools.contracts --check` (`docs/contracts/README.md`).
- Shared infrastructure comes from the kernel (`from abacus.kernel.uow import …`); other modules only via `from abacus.modules.<m>.api import …` (ADR-101).

## Adding a work-item kind
Work items (`engagements`, C1) are the units of work inside an engagement; each kind has a subtype table owned by its service-line module. Today's kinds: `assurance` and `advisory_project` (engagements), `tax_return` (tax), `close` (closes), `notice` (notices). To add one, say `foo` owned by module `m`:

1. **Migration** (migration skill): widen the `work_items.kind` CHECK to include `foo` (drop and re-add the constraint); create the subtype table keyed by `work_item_id` with `FOREIGN KEY (tenant_id, engagement_id, work_item_id) REFERENCES work_items (tenant_id, engagement_id, id)`, `tenant_table`, the revokes and `insert_columns`. Express the kind's cardinality as a constraint: a `UNIQUE (...)` or a partial unique index (`closes`: one per engagement and period; `work_items_one_assurance`: one assurance item per engagement). Copy 0089.
2. **Registry:** `m/registry.py` lists the table, `INSERT_ONLY` if it has no lifecycle yet, and its `INSERT_COLUMNS`.
3. **Provider:** `m/kind.py` with a class implementing `WorkItemProvider` (`status(tenant, work_item_id)` and `create(tx, item: NewWorkItem)`), writing the subtype row through `m/repository.py` in the caller's `tx`. Copy `closes/kind.py`.
4. **Register** in `m/api.py`: `register_work_item_kind("foo", FooKind())`. `m` must be allowed to import `engagements` in `MODULE_DEPENDENCIES`.
5. **Contract:** add `"foo"` to the `kind` `Literal` on both `WorkItemOut` and `WorkItemRowOut` in `engagements/routes.py`, then `make generate`. A new enum member is additive to frozen C1; update `docs/contracts/work-items.md` (kinds list) and the glossary's Work item row in the same commit.
6. **Tests:** `engagements.api.create_work_item(ctx, engagement_id, "foo", name=..., details={...})` writes the work item and the subtype row in one unit of work; the cardinality breach answers 409 `work_item_exists`; an unregistered kind answers 409 `unknown_work_item_kind`; run as the app role (copy `tests/integration/test_work_item_kinds.py`).

## Adding a document kind (C11; P-11-T17)
A document kind is something `reporting` renders for another module (an engagement letter, a K-1 package, a notice response). The owner module never imports `reporting` when its own dependencies forbid it: it asks through a port it declares (`engagements.api.register_letter_renderer`), and `reporting` registers the kind. To add `foo_letter` owned by module `m`:

1. **Kind** in `reporting/<foo>.py` (copy `reporting/engagement_letters.py`): `c11.register_document_kind(DocumentKind(kind=..., layout=..., variables_provider=..., approval_provider=..., source_events=(...), retention_record_type=..., formats=(...)))`, once per process (`ensure_kind`). `kind` joins the `GeneratedDocumentKind` literal in `reporting/contract.py` (additive to frozen C11; `make generate`).
2. **Variables provider:** answers every declared template variable for the owner, formatted by code (ADR-050); an unresolved key is refused as `missing_variable`, never rendered blank. A provider that answers only inside its consumer's call (a context variable) keeps regenerate on the sealed values.
3. **Approval provider:** answers the approver and the content hash only for the approval the owner is recording in the same call; without it no final render exists (`final_requires_approval`).
4. **Source events:** the outbox events whose change makes a document out of date (`out_of_date` through `reporting.api.SUBSCRIPTIONS`). Name them, or a data change never reaches the document (DEC-1664: `engagement_letter` names none yet).
5. **Retention:** the record type through `evidence.register_retention_record_type`; rendered files are stored under Object Lock (`evidence.api.store_generated`).
6. **Template content** loads through the report-template import (database content, never a constant); a golden render fixture for the kind joins `backend/tests/golden_render/` with both founders approving any re-baseline (RB-43 §5).
7. **Tests:** a missing variable refuses; an agent's render is a draft; a final render without the matching approval is refused; a locked document answers `document_locked`; a source event marks the document out of date within one relay cycle.
## Registering an envelope source and a gate (C7 v1.1; N-02-T45)
A module whose records are signed (a letter, a consent set, an 8879, a rep letter, a notice response) registers an **envelope source** with `signatures`; it never writes envelopes itself. Copy `signatures/sources.py` (`engagement_letter`), `tax/consent_capture.py` (`consent_set`) or `tax/filing.py` (`tax_return`).

1. **Source** at import in `m/api.py` (or a `register()` it calls): `signatures.api.register_envelope_source(EnvelopeSource(kind=..., documents=..., signers=..., retention_record_type=..., gate=..., checks=(...), completed_label=..., draft=...))`. `m` must be allowed to import `signatures` in `MODULE_DEPENDENCIES` (and `signatures` must never import `m`).
2. **Draft provider** (`SourceDraft`): purpose and policy family (one of the four: letters, consents, e-file authorization, general), client, title, documents (`SourceDocument`: a stored evidence version or a C11 final, its anchors or placement) and signers (`SourceSigner`: contact or member, identity method within the family's policy, routing group). It authorises the caller on its own record first; the builder authorises `envelope.draft` again. `consent_set` and `tax_return` must provide one (422 `source_contract_broken` otherwise).
3. **Checks:** pre-send problems as codes (`letter_changed`, `ero_before_taxpayer`); Send refuses while any is open.
4. **Retention:** the record type the package is locked under (`signature_evidence`, `consent_evidence`); never shorter than the published floor. Extend, never shorten, with `extend_retention` when a later fact (an IRS acknowledgement) sets the date.
5. **Gate:** name a gate kind if the source's completion meets one (G3 `engagement_letter`; `efile_authorization`), and answer it from `envelope_gate_facts(ctx, gate_kind, target_ref)`: met only by a completed, non-superseded envelope of the source. For a C13 human gate (a person must act) register the kind with `review.api.register_gate_kind(code, check)` in the owner module (copy `tax/approval.py`, `sampling/sample_sets.py`).
6. **Events:** react to `envelope.completed`, `envelope.declined`, `envelope.expired`, `envelope.superseded` and the signer-level events through your module's `SUBSCRIPTIONS`, by the source kind and id they carry (identifiers only).
7. **Tests:** a consumer suite in `backend/tests/contracts/c7_<you>/` (copy `c7_t01`): the draft prefill, a check blocking Send, the gate met only on completion, a superseded envelope unmet, a shortening `extend_retention` refused.

## Registering a TRI tool (T-01-T54)

A tool or agent that reads tax return information (§7216) declares it; nothing else opens the gate.

1. The agent spec lists `data_classes: [tri]` (`agents/spec.py`). It loads only when C19's use and
   AI-disclosure consent checks are registered (`validate_data_classes`), so a fresh environment
   without `organisations` refuses it at start, not at the first call.
2. Every gateway call carrying TRI passes its `DataSubject`s; condition 6
   (`ai_gateway.boundary.enforce_tri_consent`) answers the covering consent ids or raises
   `consent_7216`. Never call a provider for TRI without subjects, and never cache an allowance:
   `access.changed` ends it.
3. The tool's reads record `tri.tool_read` access events naming the consent ids; ADM-05's "Agent
   reads since signature" counts them.
4. Agents-off is the default posture (`tax_agents.enabled` arrives with T-04-T09); a screen draws
   agent blocks only where `PLANNED_VISIBLE`. RB-17 is the runbook when consents lapse in a wave.

## Checklist before done
- [ ] Cross-tenant test for every repository method (and the regenerated `tests/security/` cases)
- [ ] Permission tests regenerate cleanly from the matrix
- [ ] `MODULES`, `ROUTERS`, `registry.py`, `MODULE_DEPENDENCIES` and the import-linter containers agree
- [ ] Module README updated (tables, interface, slots it registers with)

## Frozen contracts (P-07-T64, DEC-1054)

A frozen contract (`docs/contracts/*.md` with **frozen**, snapshot under `backend/tests/contracts/<family>/v<n>.json`) takes additions only. A rename, retype, newly required field or removed enum member ships the next version with overlap: `python -m abacus_tools.contracts --freeze <family> v<n+1>`, never an edit of the old snapshot.
