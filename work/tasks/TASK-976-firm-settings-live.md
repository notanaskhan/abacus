---
id: TASK-976
title: Typed firm-settings registry and store — migration 0114, owner accessors, overview with At a glance, sections live (G-01-T04)
spec: SPEC-002
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: G-01
plan_key: G-01-T04
branch: s6-settings-live
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"ADM-01 a-f read and write live; a stale version answers 409; Daniel reads and cannot write; Felix gets no Plan & seats."

## Plan (red zone)
- **Migration:** `0114_firm_settings_v2.py`, with tables `firm_settings` and `firm_settings_sections` (forced RLS, column grants). Rollback: `alembic downgrade 0113`.
- **Code:** `identity/settings_registry.py` (`register_firm_setting`, `register_settings_area`, read, save, `active_wall_count`); the portal's accessors in `portal/branding.py`; organisations' Offices & teams row; live routes in `identity/settings_contract.py`.
- **Matrix:** `firm.read_settings` gains `security_admin`.
- **Tests:** `tests/integration/test_firm_settings_live.py` (4), the contract suite's `LIVE` set, and the schema expectations.

## Progress log
- 2026-10-23: built. DEC-170. Seat totals wait for a platform accessor, and the logo key waits for the upload route.
