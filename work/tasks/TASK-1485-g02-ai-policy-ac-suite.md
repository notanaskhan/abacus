---
id: TASK-1485
title: Independent AC suite 3 (ADR-078) for the AI policy against the stubs
spec: SPEC-349
acceptance_criteria: [AC-31, AC-32, AC-33, AC-34, AC-35, AC-36, AC-37, AC-38, AC-39, AC-40, AC-41, AC-42, AC-43, AC-44, AC-45, AC-46, AC-47, AC-48]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T22
branch: s12-gov
test_author: ayushkbhatia
test_session: 2026-10-27, s12-gov (clean session, from the spec, the contract and the ADRs)
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The ADM-04 acceptance tests, written before G-02-T23 (tables, compiled defaults, validator) and
T24 (services and routes), from SPEC-349 §5.10 to §5.12, `docs/contracts/ai-policy.md`,
ADR-186, ADR-187, ADR-005 and the permission matrix.

## Plan
- `backend/tests/integration/test_g02t22_ai_policy_ac_suite.py`, headed `# ac-test-author:
  ayushkbhatia`, over HTTP against `create_app()` with the sign-in dependency answering as the
  persona: Margaret (`quality_partner`, partner level), Daniel (partner level), Felix
  (`security_admin`), Grace (`firm_admin`), Hannah (manager level), a client principal, the agent
  (acting for Margaret) and the system. `ai_policy.v1` on per firm; real firm by default, a
  synthetic firm for AC-35's stored Auto mode.
- **Against the stubs** (DEC-530's pattern): `STUBBED` lists the eleven routes; a behaviour test
  asserts 501 and stops. T24 moves routes into `LIVE`; with `STUBBED` empty every behaviour test
  runs in full and fails against the stubs, including the requester approving her own version
  (409 `approver_must_differ`).
- **Run in full now:** matrix rows and the fresh-MFA register; request shapes (no gate approver,
  no unknown cell, If-Match required); wrong-role and stale-factor 403s; flag off 404 after the
  matrix; 501 `not_implemented` for permitted people; client 404 and agent/system 403 on every
  route; the route table (exactly the contract's eleven operations, so nothing promotes a stage
  or touches the opt-in); pause and resume (Grace, Felix, Margaret; others refused; resume needs
  fresh MFA; audited); SPEC-036's opt-in (firm admin with a fresh factor only; who, when; audited);
  the legacy autonomy route unchanged for flag-off firms.
- Decisions on the contract's silences: DEC-552.

## Per AC
| AC | Tests | Now |
|---|---|---|
| AC-31 | `test_ac31_every_firm_reads_one_published_effective_version` | 501 gate |
| AC-32 | `test_ac32_twelve_gate_rows…`, `test_ac32_no_gate_names_an_approver…`, `test_ac32_ac38_a_draft_cannot_carry_a_gate_approver` | gate; schema test passes |
| AC-33 | `test_ac33_every_firm_member_reads…` (5 people), `test_ac33_a_manager_reads_only…` | Hannah strict xfail (ED-181); others 501 gate |
| AC-34 | `test_ac34_history_lists_newest_first…`, `…carries_its_diff…`, `…unknown_version_is_not_found` | gate |
| AC-35 | `test_ac35_on_a_real_firm_every_auto_mode_cell…`, `…synthetic_firm_keeps…`, `test_ac35_ac38_auto_mode_cannot_be_turned_on…` (8 types) | gate |
| AC-36 | stepped tolerance, stale If-Match (idempotency), discard, no fresh MFA on save, If-Match required, unknown cells 422 | gate; shape tests pass |
| AC-37 | request and approve audited, self as approver 409, self-approve 409, fresh MFA on publish/approve/decline/withdraw, decline, withdraw once, retried approve, retried publish | gate; 403s pass |
| AC-38, AC-48 | 8 loosenings 422 with path and no event, 4 stricter changes saved, gate approver 422 | gate; 422 shape passes |
| AC-39 | `…holds_until_sep_15…` (kernel.clock frozen, `at` either side of Sep 15 00:00 CT), `…superseded_is_derived…` | gate |
| AC-40 | matrix rows; firm admin read-only; security admin client data only (saves D, 422 on A to C and E); only QM owner publishes/withdraws; only partners approve/decline | 403s pass; rest gate |
| AC-41 | opt-in roles and fresh MFA; opt-in records who/when/version (branch on `available`); route table; stages read-only | pass; band read gated |
| AC-42 | pause/resume by three roles audited; others refused; resume fresh MFA; agent/system refused | pass |
| AC-43 | sub-processors against `provider-terms.yaml`, no "Anthropic · model inference", model family not a processor | gate |
| AC-44 | §7216 on, client drafts off, principal off, each locked with its reason | gate |
| AC-45 | agent/system 403 on every route (flag on and off), no write held by agent/system/client, DB refuses `ai_policy.approved`/`.declined` as the agent | reads strict xfail (ED-182); DB strict xfail (ED-180) |
| AC-46 | client 404 on every route | pass |
| AC-47 | every write test asserts exactly one event naming the person | with each test |
| Isolation | another firm's partner cannot approve or see the version; an approver from another firm refused | gate |

## Strict xfails
- ED-180: `test_ac45_the_database_refuses_a_policy_decision_written_as_the_agent[ai_policy.approved|declined]`.
  The human-only register lacks both actions; needs the protected register edit and a migration.
- ED-181: `test_ac33_every_firm_member_reads…[hannah]`, `test_ac33_a_manager_reads_only_with_the_partners_lock`.
  `ai_policy.read` names `manager`, not the derived `firm_manager`; protected matrix edit.
- ED-182: `test_ac45_the_agent_and_the_system_are_refused_everywhere` and `…_with_the_flag_off`,
  on the four read routes × agent and system (16). The matrix denies both; the routes let them through.
- Not a defect, pending T24: `test_ac38_the_legacy_autonomy_route_is_closed_for_a_flag_on_firm`
  (ADR-186 item 7: 409 `superseded_by_ai_policy`).

## Spec drift
- AC-42 audit names: G-02 §4.7 says the existing pause events are `firm_agents.paused` /
  `.resumed`; the existing ones are `firm.agents_paused` / `firm.agents_resumed` (SPEC-027 as
  built). The suite asserts the existing names (DEC-552 item 7).

## Files
- New: `backend/tests/integration/test_g02t22_ai_policy_ac_suite.py`, this file.
- Appended: `docs/product/decision-log.md` (DEC-552), `docs/quality/escaped-defects.md`
  (ED-180 to ED-182).

## Rollback
Delete the test file and the rows.

## Progress log
- 2026-10-27: written from the spec and contract only (no service, repository or model bodies
  read; the stub's route declarations and input models for request shapes). First run: 22
  failures, triaged: Hannah's read refused (ED-181, incidental reads moved to Grace), the agent
  and system pass the read routes (ED-182), the opt-in needs `agents.client_data_optin` on (test
  setup), pause audit names (spec drift, DEC-552). Second run of the triaged set green.
