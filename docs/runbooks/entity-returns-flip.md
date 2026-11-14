---
id: RB-84
title: "Entity returns flip (M18): shadow with CCH reconciliation, rollback by flags, flag renewals"
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-04-30
---
# RB-84 · Entity returns flip (M18)

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (a reconciliation difference on a shadow return) to SEV1 (an entity figure reached a client wrong, or anything transmitted) |
| Source | T-05-T73 (TASK-8027); T-05 §4.9 window landing plan; chapter 01 §1.2.4; DEC-84, DEC-77, DEC-78; RB-83 (workbook operations: `docs/runbooks/entity-return-workbook.md`) |

## What turns on
Three T-05 flags per firm, in order:
1. `tax.entity_workspace` (the 1065 opens TXP-00 and the entity tabs);
2. `tax.workbook_run` (runs and imports);
3. `tax.entity_agents` (model-backed steps, each at its AI-policy stage).

T-04's three flags (`tax.review_workspace`, `tax.individual_workpapers`, `tax_agents.enabled`) are already on for the firm. The `tax_entity_returns` entitlement stays refused for a non-synthetic firm until the CPA review memos are signed (T-05-T70).

## Gate (all must hold; record each in the flip log)
- [ ] **CPA sign-off** of the T-05 goldens (T-05-T70): **open**. T-05-T39's kickoff never ran; it is a vendor row and Ayush's to start.
- [ ] **Delta pen test** (T-05-T72): **deferred** (DEC-1389, no penetration tests). The flip records it as deferred. It is not "met" (pen-tests-deferred rule).
- [ ] **J08 P0 core green on staging** (T-05-T68), INV-1 to INV-5 and axe clean. Waits on T-05-T66's remaining screens.
- [ ] **Shadow** on the pilot's 1065s (plan: Jul 10–28, 2028): staff only; the firm's own tool stays the system of record. On every shadow return:
  - the CCH import is approved;
  - reconciliation reads **0 unexplained differences**, or every difference is explained in a sealed resolution note (RB-83 §6).
  Until a real pilot firm exists, the shadow runs on PF-X1 (Brightwater Hale) and is reported as synthetic (DEC-1530).
- [ ] **Written rollback** (below), rehearsed once on staging.
- [ ] **Both founders' approvals** for the flip window (plan: Tue Aug 1, 2028, 19:00 CT). Recorded by name in the flip log. Never assumed.

## Flip (a Tuesday, 19:00 CT)
1. Check no deploy is in flight and the batch has merged (working agreements).
2. Turn the three flags on for the firm, in the order above, through the admin flag screen. Keep the audit row ids in the flip log.
3. Smoke test as the firm's preparer:
   - open one 1065: TXP-00 renders and Run is offered;
   - with `tax.entity_agents` still at stage shadow, every model-backed control shows "Prepared without agents" (T-05-T66), never a refused action.
4. Watch for 24 h:
   - the run failure rate;
   - `engine_diagnostic` issues raised;
   - any 5xx on `/v1/tax/returns/*/workbook*`.

## Rollback (flags only; nothing is deleted)
- Turn the flags off in reverse order: `tax.entity_agents`, then `tax.workbook_run`, then `tax.entity_workspace`.
- Workbooks, memos, runs, sign-offs and checkpoints **persist**. The 1065 opens TAX-02's coordination view as before (SPEC-651 AC-13.3).
- A return already exported keeps its engine file. The ERO's work in CCH is untouched: Accrued never transmits (R-04).
- If an entity figure reached a client wrong (a released K-1 from a later-changed workbook), raise SEV1. The K-1 change raises an Issue on the return (DEC-84, DEC-88); it never replaces a package silently.

## Flag renewals (none may expire inside Sep 1 – Oct 20)
| Flags | Expires now | Renew to | When | Then |
|---|---|---|---|---|
| T-05: `tax.entity_workspace`, `tax.workbook_run`, `tax.entity_agents` | 2027-05-07 | plan: Mon Oct 23, 2028 | plan: the Tue Jul 25, 2028 train | T-06-T03 renews to Wed Dec 6, 2028; T-06-T69 retires or renews them on Tue Nov 14, 2028 |
| T-04: `tax.review_workspace`, `tax.individual_workpapers`, `tax_agents.enabled` | 2027-05-07 | plan: Mon Oct 23, 2028 | plan: the Tue Jul 25, 2028 train | as above |

The repo's flags expire under DEC-137's solo calendar (2027-05-07), not the plan's 2028 dates. Each renewal is a protected `feature-flags/tax.yaml` edit with Ayush's approval, made before the earlier of the window and the current expiry. The table's 2028 dates are the plan's. Mapping them onto the solo calendar is decided when the flip is scheduled, not here.

## Capacity ledger and hand-offs
- **T-06** inherits:
  - the import-mode steps (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`), which become native engines;
  - the four P1 tabs (Fixed Assets, M-1/M-3, Basis, States);
  - TXP-03/04/08/09/13.
- **T-07** reuses:
  - the workbook formula DAG and re-approval semantics (DEC-84, ADR-237 still proposed);
  - the T6 derivation popover;
  - the K-1 package preparation from computed boxes.
- Open at hand-off:
  - TASK-7942's agreement-reader seed (the LPA word layers);
  - T-05-T66's remaining screens;
  - T-05-T67 part 2.
