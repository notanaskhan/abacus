---
id: TASK-8543
title: "A-09-T39: Harlow & Pike slice, stage 1 (structure, interim TBs, eliminations)"
spec: SPEC-658
acceptance_criteria: [AC-0, AC-1, AC-4]
risk_zone: amber
status: in-review
branch: a09-t39-harlow-pike-slice
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-18
updated: 2026-11-18
plan_key: A-09-T39
---

## Objective
Harlow & Pike slice through service APIs under kernel.clock (E1): five entities and coverage, ten TBs as NetSuite exports, 244 accounts with the FY2025 prior mapping, inventory and forecast evidence, E1a-E5 proposed then approved and posted by Omar, group materiality decided 3:40 PM, Pruett & Lang dates Sep 10 to Mar 19, 2027; letter and POR-20 templates through admin import (DF-40); make fixtures.

## Plan (amber)
1. harlow_pike_slice.py (opt-in --slice harlow_pike): client and five entities (MO), the FY2026 group audit on Holdings with four components and team MO/OH/CD due Mar 19, 2027, G2 confirmations at 10:07, the OneWorld connection (fake_netsuite_oneworld), the consolidation and its 3-tier structure at 100% (OH), five interim TBs at the AUD-33 a captions recorded and attached at 10:38 (OH), E1a to E5 proposed by Caleb at 1:40 PM, approved and posted by Omar at 2:01 PM
2. Loader handlers through assurance.api (group_consolidation, ConsolidationIn, StructureIn, TbAttachIn, group_figures, newly exported), adjustments.api eliminations, ledger.api record_snapshot, organisations and connections APIs; epochs: snapshot 2026-09-14T14:05 (AUD-33 a)
3. Elimination lines on the entity carrying each caption; E1a/E1b split by subsidiary (DEC-5529); per-caption nets equal group_fixtures
4. tests/unit/assurance/test_a09t39_harlow_pike_slice.py (4); make seed-demo SNAPSHOT=2026-09-14T14:05 SLICE=harlow_pike loads (7 events), a second run replays 0
5. Stage 2 (open): AUD-31 account-level mapping (consolidated TB reads mapped TBs), FY2025 prior TBs, evidence files, independence conclusion (SKE designee), group materiality 3:40 PM, Pruett & Lang auditor and dates, templates via admin import, make fixtures

## Progress log
- `2026-11-18` — Stage 1 built and loaded on the local stack 2026-11-18: 5 entities, consolidation, 6 eliminations posted, idempotent rerun. Deviation: the elimination service numbers codes E1 to E6 in order (no code input), so the handoff's E1a/E1b read E1/E2 until codes follow the handoff. Not here: the stage 2 items, all of which need either the AUD-31 mapping or figures/names the handoff does not give (the 230 unnamed accounts, FY2025 prior balances, the SKE designee). Gates and tests run once at the S49 open-rows end pass (build first, test last).
- `2026-11-18` — Templates (DF-40) checked for stage 2: blocked on design. The four portal templates the slice imports through ADM-10 (`component_auditor_invitation`, `component_deliverable_request`, `component_deliverable_follow_up`, `component_deliverable_returned`) have no bodies in the handoff (DF-40 is the open design fix, owner PF, due Fri Jan 15, 2027; POR-23 c quotes one portal message, not the email). Writing them would invent firm content; the import step lands when DF-40 does.
