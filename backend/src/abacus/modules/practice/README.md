# practice

Zone: amber. Pre-registered by F-03-T08 (ADR-140).

Owns HOME-01's read model (`home.py`, `home_contract.py`; I-01-T02, T10) and its client activity projection `home_activity_items` (`activity.py`; I-01-T12, migration 0320, DEC-900): an outbox consumer over allowlisted events, a daily 90-day prune (`home_activity_prune:platform`) and a rebuild (`python -m abacus_tools.reproject_home_activity <tenant>`).

Will own (docs/plan/03-backend-architecture.md §2.2): Due-date rules and filing deadlines, budgets, staffing, time suggestions, WIP, invoice references, fee proposals, insight snapshots, quality management.
