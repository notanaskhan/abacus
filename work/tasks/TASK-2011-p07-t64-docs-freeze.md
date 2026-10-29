---
id: TASK-2011
title: P-07-T64 Docs freeze, onboarding runbook and hand-off
spec: SPEC-321
acceptance_criteria: [AC-31]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T64
branch: s15n-p07-t64
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Freeze P-07's five contract docs at v1, publish the client-import onboarding runbook with the
hand-off notes, and point the module READMEs and the two build skills at the frozen contracts.

Acceptance: "A fresh session can onboard a firm's client list using only the runbook and the
contract docs."

## Built
- `abacus_tools/contracts.py` MODELS: `p07_clients`, `p07_engagements_v2`, `p07_contacts_access`,
  `p07_acceptance_independence`, `p07_intake_import`; snapshots `backend/tests/contracts/p07_*/v1.json`
  (`--freeze`); `--check` passes; `test_frozen_snapshots.py` ran once, 11 passed.
- The five contract docs' Status rows read frozen v1 (DEC-1054).
- `docs/runbooks/RB-41-client-import-onboarding.md` (written from the contracts only) with hand-off
  notes.
- organisations, engagements and identity READMEs; `backend-module` and `frontend-feature` skills.
- Data inventory: generated from classifications (WISP (c)(2)); nothing typed (DEC-1054).

## Progress log
- 2026-10-29: done.
