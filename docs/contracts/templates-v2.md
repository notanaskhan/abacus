# TV-1 · Templates v2 (C22) v1 — stub

| Field | Value |
|---|---|
| Register row | C22 in `docs/contracts/README.md` (K-03-T01, DEC-5810) |
| Owner | methodology (templates, versions, components, scoping rules, publish, rollout, skills) and engagements (link, update, hold, scoping results) — K-03; SPEC-720; ADR-213 |
| Status | stub (K-03-T08, 2026-11-20; DEC-5849) |
| Code | `backend/src/abacus/modules/methodology/templates_v2_contract.py` (`templates_v2_router`), `backend/src/abacus/modules/engagements/templates_v2_contract.py` (`template_link_router`) |
| Flag | `templates_v2.enabled` (default off; off: 404; on: 501 until each K-03 build task) |
| Fixtures | `apps/web/src/fixtures/seed/templates-v2.ts`; scenarios `KNW-06`, `KNW-07`, `SHL-22`, `SHT-03` (24 artboards) |
| Consumer tests | `backend/tests/contracts/tv1_templates_v2/` and `apps/web/src/fixtures/contracts/tv1-templates-v2.contract.test.ts` (K-03-T10) |

Every route answers: a client principal 404 → flag off 404 → a write that is not a live person's 403 (INV-1) → 501. One matrix action each (K-03-T06, DEC-5848).

| Method · path | Action | Notes |
|---|---|---|
| `GET /v1/engagement-templates` · `/{id}` | `template.read` | drafts only for draft readers |
| `POST /v1/engagement-templates/{id}/versions {from_version_id}` | `template.edit` | 409 `draft_exists` |
| `GET /v1/template-versions?template_id=` · `/{id}` | `template.read` | rail counts, used-by over `visible()` |
| `GET` · `PUT /v1/template-versions/{id}/components/{kind}` | `template.read` · `template.edit` | ETag autosave (412; 409 `not_draft`) |
| `GET …/checks` · `GET …/changes?against=` · `POST …/preview` | `template.read` | checks and preview are code (ADR-050); no model (INV-1) |
| `GET` · `PUT …/scoping-rules` · `POST …/scoping-rules/preview` · `GET …/scoping-sources` | `template.read` · `scoping_rule.edit` | 422 `rule_conflict`, `unknown_source` |
| `POST …/publish {effective_from, previous}` · `POST …/deprecate` | `template.publish` | fresh MFA; 409 `checks_failing`, `skill_not_published` |
| `GET …/used-by` | `template.read` | walled engagements absent |
| `GET …/rollout` · `PUT …/rollout/actions/{engagement_id}` · `POST …/rollout/start` | `template.rollout` | 409 `missing_reason` |
| `GET /v1/engagements/{eid}/template-link` · `GET …/template-update?to=` · `GET …/template-update/{update_id}` | `template_update.read` | dry run, progress |
| `POST /v1/engagements/{eid}/template-update {to_version_id}` | `template.apply_update` | 202 + workflow id; `Idempotency-Key` |
| `POST …/template-hold {reason}` · `POST …/template-hold/release {reason}` | `template.apply_update` | |
| `GET /v1/engagements/{eid}/scoping` | `scoping.read` | evaluated rules, read-only |
| `POST /v1/skills/import` · `GET /v1/skills` · `GET /v1/skill-versions/{id}` | `skill.import` · `knowledge.read` | import with fresh MFA |

**Status words:** `template_version` (Superseded only when retired), `engagement_template_link`, `rollout_action`, `template_update`, `template_update_change`, `scoping_result` (K-03-T07). **Examples (foot):** Added 3 + Changed 5 + Removed 0 = 8; 6 live = 3 Update now + 0 On rollover + 3 Hold; 35 → 38 steps, 12 → 14 sheets, requests 41 + 6 by rule.
