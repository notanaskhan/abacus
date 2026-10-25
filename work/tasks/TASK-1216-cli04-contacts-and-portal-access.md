---
id: TASK-1216
title: CLI-04 Contacts and portal access — list, O3 invite and change-scope sheet, O2 drawer, unlock and revoke dialogs (P-07-T33)
spec: SPEC-321
acceptance_criteria: [AC-26, AC-27]
risk_zone: green
status: done
epic: P-07
plan_key: P-07-T33
branch: s8b-eng-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Scenarios a to g pass with axe and the footer sums to 24 delegated requests." (P-07-T33)

## Progress log
- 2026-10-25: contract first: `ContactRowOut.invitation_id` (ED-049: Resend and Revoke took an id no read served); `make regenerate`; one backfill test. Built CLI-04 as CLI-02's "Contacts & access" tab behind `contacts.v2` (route `/clients/$clientId/contacts`): the T1 pane with the header counts, role tags, scope, portal pills and sub-lines, MFA, last seen, row actions (Invite…, Resend, Unlock…) and the ··· menu (Change scope…, Unlock…, Revoke…), the delegated footer and g's non-attest note; the O3 sheet for invite and change scope; the O2 drawer; the revoke and unlock dialogs. Fixtures: `handlers/contacts.ts` (Northwind's six, Copperleaf's two; writes follow the live rules), scenarios a–g, foot test, 21 screen tests, the e2e axe spec (not run here; `visual:ci` is the main session's).
- Deviations and gaps recorded in `docs/screens/CLI-04.md` (T33-*) under this task: no DEC number was left in the reserved range (343–345 went to ED-027, ENG-02 hold and ENG-03). The main session may want one DEC for them at merge.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| CLI-04 deviations T33-roles … T33-preview-btn (screen contract) | Row model and undesigned overlays | No |
