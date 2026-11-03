---
id: TASK-3223
title: P-04-T62 Flag housekeeping and close-out
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T62
branch: s26-p04-t62
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3223 · P-04-T62 · Flag housekeeping and close-out

**Epic:** P-04 · **Sprint:** S26 · **Type:** OPS · **Zone:** green · **Depends on:** P-04-T61 (TASK-3222 on this stack) · **Status:** in-review

## Plan
- Retire `review.grammar_api`: delete the YAML entry, regenerate `kernel/_flags.py`; remove `_stub`, `_live`, `_gate_flag` and the direct checks in `review/contract.py` and `_live` in `agents/contract.py`; unwrap the five FeatureGates in `apps/web/src/routes/firm/sheets-host.tsx`; drop it from the dev seed and the synthetic loader's FLAGS_ON.
- Renew `review.approve_agent_output` and `review.checkpoints` (created 2026-11-03, expires 2027-05-01, DEC-137).
- `review.sign_offs`, `review.issues`: never created; recorded.
- Tests: the C3 off-path tests become "no handler reads a flag; stubs answer 501"; P-04-T46's flag test drops the C3 flag.
- Records: DEC-2221, `docs/plan/status/flag-renewals-2027.md`, `docs/product/capacity-ledger.md` P-04 section.
- Rollback: revert the commit; the flag returns with its 404 branches.

## Acceptance
- [x] No P-04 flag expires inside a freeze window (both renewed flags expire 2027-05-01).
- [x] The capacity ledger records P-04 actuals.

## Progress log
- 2026-11-03: built. Integration tests still insert inert `review.grammar_api` override rows; left in place (harmless setup) for the end pass to sweep. Tests not run (end pass). Numbering: this stack moves to TASK-3200+/DEC-2200+ (main took 3031–3043, DEC-2200–2082/2098/2099).
