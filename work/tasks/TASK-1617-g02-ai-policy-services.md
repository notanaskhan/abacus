---
id: TASK-1617
title: AI policy services and routes (G-02-T24)
spec: SPEC-349
acceptance_criteria: [AC-31, AC-34, AC-36, AC-37, AC-38, AC-39, AC-40, AC-44]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T24
branch: s13-g02-t24
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Make ADM-04's API live: policy read, versions, diff, effective policy, draft with If-Match, publish request with fresh MFA, second-partner approve or decline, withdraw; the legacy autonomy route refuses for flag-on firms.

## Plan
- `agents/ai_policy_service.py`; the stub routes in `agents/ai_policy_contract.py` now call it.
- `agents.api.effective_ai_policy`; notification kind `ai_policy_approval_requested`; identity `SupersededByAiPolicy` on `PUT /v1/firm/autonomy`.
- Tests: G-02-T22's suite 3 now runs every behaviour test against live routes (`LIVE = ROUTES`); the G-02-T15 contract test's gate checks move to the service's `_open`.
- DEC-712. Rollback: revert; the flag stays off.

## Progress log
- 2026-10-28: built. Regeneration also refreshed `integrations/_capabilities.py` (A-02-T26's writer key) and the tenant-isolation list (0272's tables). Not run: suite 3 (batch pass).
