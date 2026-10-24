---
id: TASK-1178
title: Threat-model refresh for pen test #1, second pass — what S5–S7 added: the gateway TIN refusal, portal sessions and MFA, invitations v2, the incident register, G2 v2, the viewer and the client upload policy (Q-03-T018)
spec: SPEC-051
acceptance_criteria: [AC-4, AC-5]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T018
branch: s7c-pentest-readiness
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The model names every surface in the pen-test scope and N has approved it by Fri Feb 5." Q-03 §D3; ADR-064. This follows TASK-1164's first pass of the same row, which was written before the S7 batch (#393) merged.

## Plan (amber zone, a document)
- `docs/architecture/ai-threat-model.md`:
  - **Scope table:** rows for invitations v2, G2 v2 and the viewer (built behind `evidence.viewer_v1`). Staff session limits and the TIN refusal move from planned to built. The upload row names the policy decided on 2026-10-24 as the **intended** control: another workstream is building it, so ED-018 to ED-021 stay open until it lands.
  - **TRI rows:** TRI-01 and TRI-03 change from planned to tested (ADR-167, TASK-1170). TRI-04's flag is built.
  - **New rows:**
    - IN-01 to IN-04: invitations v2, covering the no-oracle preview, template grants, inviter re-check, terms and single use.
    - G2-01 and G2-02: independence guarding assignment, sign-off and client-facing actions; the stricter-only setting.
    - EV-04 and EV-05: the viewer's masked-only pages and search that never logs its query.
    - EV-06: the upload policy as intended.
    - AU-09 and AU-10: the staff access token outliving sign-out; portal backup codes.
    - CR-05: incident propagation from staff.
  - **Rows revised:** EV-01, EV-03, CR-02 and AU-07.
  - **Gaps and review:** gaps added; review row added; the checklist is unchanged.
- Public-repo rule: no exploit detail, credentials, addresses, firm or person names.
- No code. Rollback: revert the file.

## Progress log
- 2026-10-24: refreshed. Every new test path cited was opened, and each test function named was found by grep. The upload policy is described as intended because its implementation is in flight elsewhere: when it merges, EV-06's coverage moves to Tested, citing the hostile-files cases that stop being xfail. Status `in-review`: N's approval (Fri Feb 5, 2027) is the acceptance. Re-run before the pin if R-01 (portal drop), P-03-T13/T15 (masking), P-08-T25 (portal-scope and host-pinning files) or Q-02-T43 (export) land first.
