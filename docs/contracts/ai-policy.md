# AI policy (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` (G-02) |
| Version | v1 |
| Status | stub (G-02-T15, 2026-10-27): every route answers 501 with the flag on |
| Provider epic | G-02 (`agents`: tables and compiled defaults G-02-T23, services and routes G-02-T24, ADM-04 G-02-T25) |
| Consumers | ADM-04 (G-02-T25); P-10's run planner (effective autonomy, S36); K-02 KNW-04 (policy-principal section, display only); P-07 ENG-03 ("Firm policy: Auto mode off for audits"); N-02 ENG-04 (AI-use disclosure in letters); C-02 (the locked policy-acceptance row); K-04, K-05, I-03 (schema_version 2 sections); Q-05 ADM-11 (override tolerance) |
| Freeze sprint | the sprint review after the stub; frozen for consumers at S13 with T24 |
| Flag | `ai_policy.v1` (default off; DEC-55: rollout only) |
| Spec | SPEC-349 AC-31 to AC-44, AC-48; G-02 §3.10 to §3.12, §4.2 to §4.4 |
| ADRs | ADR-186 (P-49, versions and Auto mode), ADR-187 (P-08, dormant policy principal), ADR-157 (per-firm pause), ADR-139 (P-36 envelope, error codes), ADR-031 (classification); DEC-50, DEC-53, DEC-87, DEC-532 |

## 1. Purpose
The firm's written, versioned AI policy ("BH AI policy vN"): who approves each kind of agent output (twelve gates), the autonomy level, Auto mode per engagement type, the §7216 rule and client-data settings, agent governance; published by the QM owner and approved by a second partner. Beside it, outside versioning, the immediate controls: the client-data opt-in (SPEC-036), each agent's stage (read-only) and "Pause all agents".

**Stub behaviour.** With `ai_policy.v1` off every route answers 404. With it on, every route answers 501 `not_implemented` until G-02-T24. The matrix answers first (security review L1): a client principal gets 404; the agent, the system, a person without the action and a stale second factor get 403, whatever the flag. Fixture mode serves ADM-04 a, b, d, e, g, h, i and j, the immediate-controls band and the Awaiting approval state (`apps/web/src/fixtures/scenarios/ADM-04.ts`); c and f (the dormant policy principal) are fixture-only and arrive with the screen (T25).

## 2. Who may call it
| Operation | Method and path | Matrix action |
|---|---|---|
| The effective policy, pending and scheduled versions, draft summary, gates, locks, immediate controls, sub-processors, model family, the viewer's actions | `GET /v1/firm/ai-policy` | `ai_policy.read` |
| Version history | `GET /v1/firm/ai-policy/versions` | `ai_policy.read` |
| One version with its sections and diff | `GET /v1/firm/ai-policy/versions/{version_no}` | `ai_policy.read` |
| The effective cells for one engagement type at one time | `GET /v1/firm/ai-policy/effective` | `ai_policy.read` |
| The draft | `GET /v1/firm/ai-policy/draft` | `ai_policy.draft` |
| Save the draft (If-Match) | `PUT /v1/firm/ai-policy/draft` | `ai_policy.draft` |
| Discard the draft (If-Match) | `DELETE /v1/firm/ai-policy/draft` | `ai_policy.draft` |
| Request publication ("Publish v4") | `POST /v1/firm/ai-policy/versions` | `ai_policy.publish` (fresh MFA) |
| Approve a version | `POST /v1/firm/ai-policy/versions/{version_no}/approve` | `ai_policy.approve` (fresh MFA) |
| Decline a version | `POST /v1/firm/ai-policy/versions/{version_no}/decline` | `ai_policy.approve` (fresh MFA) |
| Withdraw a version awaiting approval | `POST /v1/firm/ai-policy/versions/{version_no}/withdraw` | `ai_policy.publish` (fresh MFA) |

`ai_policy.read`: every firm membership role. `ai_policy.draft`: `quality_partner`, and `security_admin` for the `client_data` section only (the service, AC-40). `ai_policy.publish`: `quality_partner`. `ai_policy.approve`: partners (`level_in(partner)`), never the requester (the service and a database CHECK, T23). `firm_admin` reads only. The immediate controls keep their own routes: `POST /v1/firm/agents/pause` and `/resume` (`firm_agents.pause`: firm admin, security admin, QM owner) and SPEC-036's opt-in (`firm.ai_client_data`, firm admin, fresh MFA).

## 3. Shapes
Models in `backend/src/abacus/modules/agents/ai_policy_contract.py`; every field carries its classification. Rows carry codes and facts; the SPA composes the words.

- **`AiPolicySections`** (schema_version 1, ADR-186 item 2): `autonomy {level}`, `gates [{action_key, policy_acceptance_on}]` (stricter-only overrides; today only policy acceptance, locked off), `policy_principal {on}` (locked off, ADR-187), `auto_mode_defaults {ebp_audit, fs_audit, review_compilation, preparation, tax_return, monthly_close, notice, advisory}`, `client_data {require_7216_consent (locked on), consent_template_ref, disclosure_in_letters, client_drafts_enabled (locked off)}`, `governance {install_role, publish_approver, override_tolerance_pct, accuracy_sample_n, trace_retention_years (≥ 7)}`. Inputs forbid unknown fields. Bounds are shape only: a loosening is the validator's 422.
- **`AiPolicyVersionOut`**: `version_no`, `state` (`awaiting_approval`, `published`, `declined`, `withdrawn`), `schema_version`, `effective_from`, `requested_by`, `requested_at`, `approver`, `decided_by`, `decided_at`, `carried_over`, `superseded` (derived, never stored). **`AiPolicyVersionDetailOut`** adds `sections` and `diff [{path, before, after}]` against the version before. **`AiPolicyVersionPageOut`**: the P-36 envelope, newest first.
- **`AiPolicyDraftOut`**: `base_version_no`, `sections`, `differs` ("Unsaved changes"), `diff`, `version` (If-Match), `updated_at`, `updated_by`.
- **`GateRowOut`** (fieldset A, the twelve rows of chapter 05 §5.2.13 from the compiled catalogue, AC-32): `row`, `gate_key`, `action_keys`, `approver_rule` (a code the SPA words), `default_approver_roles` (the matrix's roles, as codes), `policy_acceptance_available` (rows 1 and 5), `policy_acceptance_on` (false), `policy_acceptance_locked` (true), `acceptance_policy_ref` ("BH AJE thresholds v2"), `attest` (`never`, `never_held_for_client`, `posting_disabled`), `where_shown` (screen ids: SHL-10, SHL-11, SHL-12, CLS-07, TAX-09), `log_action`.
- **`CellLockOut`**: `path`, `reason` (`policy_principal_dormant`, `platform_floor`, `real_firm_season_1`, `not_a_partner`, `client_data_only`).
- **`ImmediateControlsOut`**: `client_data_opt_in {on, changed_at, changed_by, register_version}`, `agent_stages [{agent_key, stage shadow|live, since}]`, `firm_pause {paused, paused_at, paused_by}`.
- **`SubProcessorOut`**: `name`, `purpose`, `region`, `trains_on_data`, `retention_days`, generated from `docs/operations/provider-terms.yaml` (DF-16); `model_family` is a model, never a processor (DEC-87).
- **`AiPolicyOut`**: `effective`, `sections`, `pending` (awaiting approval), `scheduled` (published, effective later: "v4 · effective Sep 15"), `draft`, `gates`, `locks`, `immediate`, `sub_processors`, `model_family`, `real_firm`, `actions` (the viewer's among `ai_policy.*` and `firm_agents.pause`).
- **`EffectiveAiPolicyOut`** (the effective-policy read): `version_no`, `effective_from`, `engagement_type`, `at`, `autonomy_level`, `auto_mode` (stored), `auto_mode_effective` (false on every real firm, Season 1), `auto_mode_lock`, `policy_principal_on` (false), `client_data`, `firm_paused`.
- **Inputs**: `AiPolicyDraftIn {sections}` with header `If-Match: <draft version>`; `AiPolicyPublishIn {effective_from (date, firm time zone), approver_user_id}`; `AiPolicyDeclineIn {reason_code (needs_changes, wrong_effective_date, other), note (≤ 500, Confidential)}`.

## 4. The effective-policy read (P-10, K-02, P-07, N-02)
`agents.api.effective_ai_policy(tenant, engagement_type, at)` (T24) and `GET /v1/firm/ai-policy/effective?engagement_type=&at=` return the published version whose `effective_from` is the latest at or before `at` on `kernel.clock` (AC-39): before Sep 15, 2026 every read is v3; after, v4. A run reads the version effective when it starts. Consumers read cells, never `firms.autonomy_level` (frozen as the fallback, capped at 1, ADR-186 item 7):
- **P-10** (run planner): `autonomy_level`, `auto_mode_effective` for the engagement's type, `firm_paused`.
- **P-07** (ENG-03 helper): `auto_mode_effective` and `auto_mode_lock` ("Firm policy: Auto mode off for audits").
- **K-02** (KNW-04): `policy_principal_on` (display only; always false while ADR-187 holds).
- **N-02** (ENG-04): `client_data.disclosure_in_letters`.

## 5. Behaviour (T23, T24)
- **Stricter only** (AC-38): a draft that turns policy acceptance or the principal on, §7216 consent off, client drafts on, trace retention under 7 years, the autonomy level to 2 or more, Auto mode on for a real firm, or a gate approver wider than the matrix answers 422 `policy_loosening_refused` with `facts.field` = the cell's path; the UI never offers it.
- **Draft** (AC-36): one per firm; saved against If-Match (409 `stale_version`); Discard returns to the effective version. A security admin's save may change `client_data` only (422 `policy_loosening_refused` with the path of the first other change).
- **Publish** (AC-37): the QM owner, fresh MFA; the approver is a partner other than the requester (409 `approver_must_differ`); the version waits `awaiting_approval` and raises the C13 gate (`ai_policy.approval`) in the approver's queue. The approver approves or declines with fresh MFA; the requester may withdraw while it waits. Nothing leaves `published`.
- **Real firms** (AC-35): every Auto mode cell reads Off with a lock (`real_firm_season_1`).
- **Immediate controls** (AC-41, AC-42): read here, changed through their own routes; the opt-in records the disclosure's register version (SPEC-036 AC-3 unchanged).

## 6. Audit events
`ai_policy.draft_saved`, `ai_policy.draft_discarded`, `ai_policy.publish_requested`, `ai_policy.approved` (actor: the approver; ADM-07 renders "AI policy v4 published by ‹requester› · approved by ‹approver›"), `ai_policy.declined`, `ai_policy.withdrawn`, `ai_policy.carried_over` (system, the migration's back-fill only). References are identifier-only; values resolve at read time from the version rows (T24 registers the `ai_policy` value resolver).

## 7. Errors
404 (flag off; a client principal; an unknown version), 403 (no matrix right; a stale second factor), 409 `approver_must_differ`, `stale_version`, 422 `policy_loosening_refused` and request validation, 501 while stubbed.

## 8. Consumer tests
`backend/tests/contracts/ai_policy/test_ai_policy_contract.py` (this stub); G-02-T22 writes the independent AC suite 3 against these routes. Fixture mode: `apps/web/src/fixtures/handlers/ai-policy.ts`, `apps/web/src/fixtures/scenarios/ADM-04.ts`, checked against the OpenAPI schemas by `apps/web/src/fixtures/contracts/ai-policy.contract.test.ts`.

## 9. Change log
- v1 (2026-10-27, G-02-T15): stub. DEC-532 records the shape choices.
