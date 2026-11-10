# practice

Zone: amber. Pre-registered by F-03-T08 (ADR-140).

Owns HOME-01's read model (`home.py`, `home_contract.py`; I-01-T02, T10) and its client activity projection `home_activity_items` (`activity.py`; I-01-T12, migration 0320, DEC-900): an outbox consumer over allowlisted events, a daily 90-day prune (`home_activity_prune:platform`) and a rebuild (`python -m abacus_tools.reproject_home_activity <tenant>`).

Will own (docs/plan/03-backend-architecture.md §2.2): Due-date rules and filing deadlines, budgets, staffing, time suggestions, WIP, invoice references, fee proposals, insight snapshots, quality management.

## Home (I-01; C13 v1 frozen, `docs/contracts/home-and-gates.md`)

- **Two halves, one count.** The home half here (`GET /v1/home`: tiles, your work, deadlines, client activity, the running count) carries no queue. The gate half is `review`'s `human_gates` projection and `GET /v1/human-gates/counts`, the one count every surface reads: HOME-01's header, summary and badge, HOME-02's bands, SHL-04's Approvals tab and I-02's brief. `apps/web/src/domain/home/countEquality.test.ts` holds them equal for six personas (I-01-T25).
- **A new gate subkind** registers in its owning module (`review.api.register_gate_source`); see the contract's §12. Nothing here changes.
- **A new tile** is a home count its owner registers through `platform.register_home_count`; a count of what waits on a person is a gate, never a tile.
- **Operations:** `docs/runbooks/RB-70-home-counts.md` (a count mismatch, the projector and activity rebuilds, the `home.approvals` rollback).
- **R2 bands** (To-dos, Mentions) are built unwired in `apps/web/src/components/screens/HOME-01` (I-01-T24) and wired after Apr 20, 2028 (P-29 rule 2).

