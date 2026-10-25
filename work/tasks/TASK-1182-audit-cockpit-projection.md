---
id: TASK-1182
title: Cockpit projection and A-01's providers - Overview links, Source Documents, Team, Letter sent, EQR, No report, guarded C6 v1 run summary (A-01-T09)
spec: SPEC-330
acceptance_criteria: [AC-22, AC-23, AC-24]
risk_zone: amber
status: done
epic: A-01
plan_key: A-01-T09
branch: s8a-audits-read
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"A-02 can register Trial Balance without editing A-01 and an unregistered section never renders."

## Plan (amber zone)
- **assurance:** `cockpit.py` (the projection: audit bar, overview, bands from `registered_sections()` with each provider asked per work item, a `None` answer or a raising provider leaving the row out; dock tabs; `allowed_actions`; archived read-only), `providers.py` (A-01's six Overview rows and three index tags, registered in `api.py`), `sections.register_run_summary` (the guarded C6 v1 slot P-10 fills; unregistered means no run).
- **Route action:** the cockpit route declares `engagement.read_metadata`: the bar and overview are metadata (the contract's "metadata-only roles get the bar and overview only"), and the bands, dock and actions need `engagement.read` as well, probed with `allowed_actions`. `make regenerate`.
- **Tests:** `tests/integration/test_audit_cockpit.py` (AC-22 to AC-24), `tests/unit/assurance/test_audit_providers.py`.
- **Rollback:** revert and `make regenerate`.

## Progress log
- 2026-10-25: built. The cockpit route now declares `engagement.read_metadata` (routing guard: a route checks its declared action, so `engagement.read` could not give metadata roles their bar and card); `make regenerate` run. A-01's six Overview rows and three tags register through the slots (`providers.py`); `register_audit_section` gained additive `title`/`link`; `register_run_summary` is the guarded C6 v1 slot (none registered). Northwind at E0: "11 of 24 received", "MO · TW · HL · MD · AC"; Methodology and Standards set hidden (nothing pinned or named). A test-registered Trial Balance renders, a `None` or raising provider hides its row.
- 2026-10-25: security review fixes (failing tests first): `advance_by_gate` internal, person's own context, gate computed (409 `phase_gate_unmet`); cockpit refuses client, agent and system itself; sections declare a required action (Methodology: `methodology.read` on the firm); archived work item read-only; G2 pending-member behaviour pinned with `g2_blocks_view` on and off (DEC-312). The existing release test now seeds its release (G8 met) instead of asserting the gate.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-312 | Cockpit action, provider rules, tag rules, guarded run summary | No |
