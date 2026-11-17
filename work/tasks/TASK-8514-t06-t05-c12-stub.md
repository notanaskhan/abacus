---
id: TASK-8514
title: "T-06-T05: C12 v1 contract stub: the TB hand-off into tax"
spec: SPEC-702
acceptance_criteria: [AC-27, AC-28, AC-29, AC-31]
risk_zone: amber
status: in-review
branch: t06-t05-c12-stub
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T05
---

## Objective
Spec section: docs/plan/epics/T-06.md §4.3, §8.1. C12 v1, source-agnostic for audit_release, review_release and close_lock: Pydantic models with classification tags, 501 routes behind tax.tb_handoff, Granite Peak and Copperleaf seed fixtures, docs/contracts/c12-tb-handoff.md, make generate.

## Plan (amber)
1. `ledger/tb_handoff_contract.py`: targets, preview, create (Idempotency-Key, live human), read, mappings, the return's landing; client 404, flag 404, then 501. Mounted as the ledger module's first router (DEC-66: ledger owns tb_handoffs).
2. Preview status is the five tb_handoff words (three derived), so a Literal rather than the stored StrEnum.
3. Fixtures `abacus_tools/synthetic/scenarios/brightwater_hale/tb_handoff_slice.py`: Granite Peak AUD-38 a, b, d typed by the C12 models (121 + 5 + 2 = 128; 3,100,000 − 750,000 = 2,350,000; review accounts 2255 and 6875; passed AJE-3 68,400) and Copperleaf's close_lock landing.
4. `docs/contracts/c12-tb-handoff.md`; register row C12 moved from planned to stub; make generate.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5514). Ruff, pyright and import contracts clean; generate clean. Footing tests are T-06-T06. Gates and tests run once at the S49 end pass (build first, test last).
