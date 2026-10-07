---
id: SPEC-008
title: Engagement graph and methodology configuration v1
status: draft
owner: founder
risk_zone: amber
related_adrs: [ADR-053, ADR-056, ADR-050, ADR-004, ADR-024, ADR-052, ADR-031]
related_specs: [SPEC-000, SPEC-004]
created: 2026-10-07
updated: 2026-10-07
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
This spec covers two pieces of the Context layer in Phase 1 §5.3.
- **Methodology configuration v1:** a firm imports its audit methodology as a versioned template. The template holds:
  - the firm's audit areas;
  - the standard request items for each area;
  - rules that map ledger accounts to areas.

  An engagement is pinned to one template version, and its request list is seeded from that version.
- **The engagement graph:** one deterministic, read-only view of how an engagement fits together:
  - audit areas, their accounts and their request items;
  - evidence and its screening and review state;
  - coverage gaps.

  People and agents (as context) read the same view.

## 2. Problem and context
Each engagement's structure exists today only as loose rows:
- request items carry a free-text `audit_area`;
- trial balance lines carry account codes;
- evidence links to items.

Nothing says which accounts belong to which area, which areas have no requests, or which material accounts nobody is asking about. Each firm has its own methodology, usually kept in spreadsheets, and staff retype the same request list for every engagement. Agents need a compact, correct picture of the engagement (ADR-053's structured memory, facts in tables), not a pile of rows.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Firm admins and practice leaders | Import and publish methodology templates (Q3) |
| Engagement partners and managers | Apply a template version to an engagement |
| Engagement team | Read the graph |
| Agents | Read the graph as context through `ai_gateway`'s context builder (later increments) |

## 4. Goals and non-goals
**Goals**
- **Import:** a methodology template is imported from an `.xlsx` workbook with a fixed layout (Q1), validated deterministically, and stored as an immutable version.
- **Apply:** a template version is applied to an engagement, which pins it and seeds the request list. This happens once per engagement (Q4).
- **Account mapping:** deterministic code maps trial balance accounts to audit areas by rule (ADR-050).
- **The graph:** an engagement graph read API, computed on read from the owning modules' APIs (Q2), with coverage gaps:
  - areas without requests;
  - mapped accounts without requests;
  - unmapped accounts;
  - requests without evidence.

**Non-goals**
- **Engagement facts and memory beyond the graph:** carried-forward facts and agent-proposed memories are a later spec.
- **Knowledge retrieval (pgvector):** the next spec.
- **Methodology documents as prose:** they belong to knowledge retrieval (ADR-056).
- **Materiality, risk assessment and procedures beyond request items.**
- **Editing templates in the UI:** a new version is a new import.
- **Any UI:** this spec is API only.

## 5. User stories and acceptance criteria
### Story 1: A firm brings its methodology
- **AC-1** Given a firm admin and a workbook in the fixed layout (Q1), when they import it under a template name, then a new immutable template version is stored with its areas, request items and account rules. `methodology.imported` is audited with the version and the workbook's fingerprint.
- **AC-2** Given a workbook that breaks the layout or the limits, when it is imported, then nothing is stored and the caller gets 422 with a list of problems (sheet, row, column and a fixed code), never cell contents. Workbooks are hostile input (ADR-052). Problems include:
  - a missing sheet or header;
  - a duplicate area code;
  - an item or rule for an unknown area;
  - an invalid tier;
  - a malformed or overlapping account rule;
  - over the size or row limits.
- **AC-3** Given template versions, then they are never updated or deleted (ADR-004). Importing under an existing name creates the next version number.

### Story 2: An engagement starts from the methodology
- **AC-4** Given an engagement partner or manager and a template version, when they apply it to an engagement with no template, then in one unit of work:
  - the engagement is pinned to the version;
  - one request item is created for each template item, with its area's name as `audit_area` and its retrievability tier;
  - `methodology.applied` is audited.
- **AC-5** Given an engagement already pinned, when a template is applied again, then 409 `methodology_already_applied` (Q4). Existing request items are never changed.

### Story 3: The engagement makes sense at a glance
- **AC-6** Given an engagement, when its graph is read, then the response holds:
  - the engagement, client, entity, period and team;
  - the pinned template version, if any;
  - every audit area, from the template's areas plus any `audit_area` used by its request items;
  - per area: its request items (status, latest evidence version, latest screening action, review state) and its mapped accounts from the latest ledger snapshot (code, name and balance, with no amounts beyond the snapshot's own).
- **AC-7** Given the pinned version's account rules and the latest snapshot, then every account maps to the first matching rule in rule order, or to `unmapped`. The mapping is deterministic code, never a model (ADR-050).
- **AC-8** Given the graph, then it lists coverage gaps:
  - areas with no request items;
  - areas with mapped accounts but no request items;
  - unmapped accounts whose absolute balance is at least the threshold (Q5);
  - request items with no evidence.
- **AC-9** Given a person without access to the engagement (a wall, no membership), when they read the graph, then they get the same 404 as for any engagement they can't see (SPEC-002).

## 6. Behaviour and flows
1. **Import:** a firm admin uploads the workbook. The file is parsed in memory with fixed limits and validated into typed rows. If clean, it is stored as version *n+1* in one unit of work. If not, nothing is stored and the response is 422 with the problems.
2. **Apply:** a partner applies a version to an engagement. In one unit of work, the engagement is locked, the version is pinned, the items are inserted, and the action is audited.
3. **Read the graph:** read the engagement through its module's API, then:
   - request items with their latest evidence, screening and review state;
   - the latest ledger snapshot's accounts;
   - the template's areas and rules.

   The accounts are mapped and the gaps computed in code. No model is involved.

## 7. Domain and data changes
All tables are tenant-scoped with forced RLS, insert-only, and owned by `engagements` (Q3).
- **`methodology_templates`:** `id`, `tenant_id`, `name` (unique per firm), `created_by`, `created_at`.
- **`methodology_versions`:** `id`, `tenant_id`, `template_id`, `version` (unique per template), `source_fingerprint` (SHA-256 of the workbook), `imported_by`, `created_at`.
- **`methodology_areas`:** `version_id`, `code` (unique per version), `name`, `position`.
- **`methodology_request_items`:** `version_id`, `area_code`, `description`, `retrievability_tier` (A to E), `position`.
- **`methodology_account_rules`:** `version_id`, `area_code`, `account_from`, `account_to` (an inclusive code range compared as text; a single code has from equal to to), `position`.
- **`engagements.methodology_version_id`:** nullable, set once (an UPDATE grant on that column only, checked as null-to-value by the service under lock).
- **`request_items.retrievability_tier`:** a nullable column (A to E), set when items are seeded from a template.

The workbook itself isn't stored, only its fingerprint. The firm keeps its source.

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `POST /v1/methodology/templates/{name}/versions` (multipart `.xlsx`) | Import (AC-1 to AC-3); `methodology.manage` |
| `GET /v1/methodology/templates` and `GET /v1/methodology/versions/{id}` | List templates and versions, and read one version; `methodology.read` |
| `POST /v1/engagements/{id}/methodology` `{version_id}` | Apply (AC-4, AC-5); `engagement.apply_methodology` |
| `GET /v1/engagements/{id}/graph` | The graph (AC-6 to AC-9); `engagement.read` |
| `engagements.api.engagement_graph(ctx, engagement_id) -> EngagementGraph` | The same view, for agents' context later |

## 9. Authorisation and tenancy
- **New matrix actions (a protected change):**
  - `methodology.manage`: firm admin and practice leader, with fresh MFA;
  - `methodology.read`: firm admin, practice leader, engagement partner and manager;
  - `engagement.apply_methodology`: engagement partner and manager on the engagement (not archived).
- **The graph:** reuses `engagement.read`, which includes walls and membership.
- **Tenancy:** everything is tenant-scoped through `tenant_session`. Templates are firm-wide, and versions are visible across the firm's engagements.

## 10. AI behaviour
No model calls. The graph is built for agents to read later. When it is rendered into context it goes through `ContextBuilder` with classifications (account names and balances are confidential, as in the ledger).

## 11. Integrations
None. The workbook is uploaded by a person.

## 12. Edge cases and failure modes
- **No template pinned:** the graph's areas come from the request items' `audit_area` values, and every account is `unmapped`.
- **No ledger snapshot yet:** the graph has no accounts, and the account gaps are empty.
- **Overlapping account rules:** rejected at import (AC-2), so mapping never depends on ties.
- **Very large workbooks:** limits of 5 MB, 50 areas, 2,000 request items and 2,000 rules (settings). Formulas are read as their cached values and never evaluated. Macros and external links are ignored, since the file is opened read-only with `openpyxl` (already a dependency).
- **An area renamed in a later version:** the pinned version doesn't change. Re-pinning is deferred.

## 13. Security and privacy
- **The workbook is hostile input:** it is parsed with limits, never evaluated, and its cell contents never appear in logs or errors.
- **Classification:** template content is the firm's methodology (internal). Account names and balances in the graph are confidential, as in the ledger.
- **Who can change what:** only firm admins and practice leaders with fresh MFA import methodology; only the engagement's partner or manager applies it.

## 14. Audit trail and evidence integrity
- **Audited:** `methodology.imported` (the version, the workbook's fingerprint and the counts) and `methodology.applied` (the engagement, the version and the number of items).
- **Integrity:** template versions are insert-only.

## 15. Observability
- **Logs:** `methodology.import_rejected` (problem codes and counts only).
- **Metric:** graph read latency.

## 16. Performance and scale
The graph reads one engagement: hundreds of items and accounts, built in a few indexed queries. The target is p95 under 300 ms. It is not cached in v1.

## 17. UX
None in this spec.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-3 | unit + integration | Parsing a valid and each invalid layout; versions; immutability; audit |
| AC-4, AC-5 | integration | Apply seeds items once; 409 on reapply; audit |
| AC-6 to AC-8 | unit + integration | Account mapping by rule; each gap kind seeded |
| AC-9 | integration | Walls and non-members get 404 |

## 19. Rollout
No flag. The migration is additive, and existing engagements have no template pinned.

## 20. Open questions
- [ ] **Q1: the workbook layout.** *Recommendation:* three sheets.
  - **`Areas`:** `code`, `name`.
  - **`Requests`:** `area_code`, `description`, `tier`.
  - **`Account rules`:** `area_code`, `account_from`, `account_to`.

  Headers are exact, and rows are kept in order. A sample workbook and its layout go in `docs/product/`.
- [ ] **Q2: the graph is computed on read, not stored.** *Recommendation:* yes. It's always consistent with its sources, and there's no sync to get wrong. Materialise it later only if reads get slow.
- [ ] **Q3: owner of the methodology tables, and who imports.** *Recommendation:*
  - the `engagements` module owns the tables (methodology configures engagements; no new module, so no ADR-101 change);
  - firm admins and practice leaders import, with fresh MFA.
- [ ] **Q4: applying a template.** *Recommendation:* once per engagement, and only seeding. Request items added later by hand are untouched. Re-pinning or merging a newer version is deferred.
- [ ] **Q5: unmapped-account threshold for a gap.** *Recommendation:* any unmapped account with a non-zero balance, as a setting. Materiality-based thresholds come with the materiality work.

## 21. Future / explicitly deferred
- Engagement facts carried forward, and agent-proposed memories (ADR-053).
- Re-pinning to a newer version, and template diffs.
- Template editing in the UI.
- Materiality-driven gaps.
- Graph caching.
