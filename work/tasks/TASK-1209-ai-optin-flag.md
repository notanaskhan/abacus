---
id: TASK-1209
title: AI opt-in flag agents.client_data_optin (Q-02-T06 remainder; SPEC-036)
spec: SPEC-036
acceptance_criteria: [AC-3]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T06
branch: s8b-core
created: 2026-10-25
updated: 2026-10-25
---

## Objective
Q-02-T06's bundle is mostly on main or moot under the solo edition (no CODEOWNERS or approval files; glossary rows for agent stage, AI opt-in, AI exclusion, access event and audit checkpoint exist; `firm.read_settings` already includes `security_admin`; `firm.ai_client_data` and `engagement.ai_exclude` are in the matrix). What was missing is the flag `agents.client_data_optin`.

## Plan
- Flag in `docs/architecture/feature-flags/identity.yaml` (boolean, default off, expires 2027-04-21 with DEC-137), `make regenerate`.
- `identity/firm_settings.py`: the read and write answer 404 with the flag off (before authorise, as the holds routes do); `ai_client_data_opted_in` returns false with it off (fail-closed).
- Engagement exclusion is not flagged; no `platform.agent_stage.set` row (DEC-336).
- Web: the opt-in panel renders nothing on 404; vitest case added.
- Local seed and the Brightwater Hale loader turn the flag on.
- Rollback: revert; the flag off is the same as today's refusal for real firms.

## Progress log
- 2026-10-25: built. Targeted: `tests/unit/ai_gateway`, `unit/tools`, `unit/quality`, kernel client-data settings, agent stages, security route introspection and fresh-MFA, integration `agent_tests/test_gateway_boundary.py` and `test_q02_attribution_access_acceptance.py`: 6110 passed (`-n 4`).
