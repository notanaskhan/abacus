---
id: TASK-1122
title: G2 v2 in identity authz - independence guards assignment, sign-off and client-facing actions on attest clients; g2_blocks_view; independence_cleared (P-07-T24)
spec: SPEC-332
acceptance_criteria: [AC-13, AC-14, AC-15, AC-16]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T24
branch: s7-p07-contacts
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Ana Cruz can open the Northwind engagement but cannot be assigned or sign off until Ana confirms, and a non-attest close is not gated" (P-07-T24), bound by ADR-164 (P-13) items 2 to 4.

## Plan (red zone)
- **Authorisation (`identity/authz/__init__.py`, protected):** layer 3b keeps its shape (a staff engagement role, an engagement resource, a person, not support) and denies only when the person is not cleared **and** G2 applies: the engagement's client is an attest client (`LOOKUPS.attest`; unknown or unregistered counts as attest, fail closed) **and** the action is not a read, or it is a read and the firm has `g2_blocks_view` on (read from the per-request `FirmPolicy.settings_on`). The cleared lookup runs first (cached per request), so the attest lookup is read only for an uncleared person. `visible()` for a marked read: staff reach = membership AND (confirmed OR NOT (g2_blocks_view AND attest)), with the setting as an EXISTS on identity's `firm_setting_values` and the attest flag through a new registered column builder (`register_attest_client_column`; unregistered = attest, fail closed). Unregistered independence lookup keeps today's fail-closed answer (no staff reach).
- **Settings:** `authz.matrix.STRICTER_SETTING_KEYS = {"g2_blocks_view"}`; stored keys = `FIRM_SETTING_KEYS | STRICTER_SETTING_KEYS`. Matrix cells may never name a stricter key (a `firm_setting(g2_blocks_view)` cell is refused at import), so the setting can never grant. `firm_settings.set_firm_setting` accepts it.
- **Migration `0138_g2_blocks_view.py`** (down_revision 0133): widens `firm_setting_values.key`'s CHECK with `g2_blocks_view`. Downgrade deletes any `g2_blocks_view` row and restores 0081's CHECK.
- **Matrix (protected):** `client_access.grant` and `message.send` gain `independence: required` (ADR-164 item 2, client-facing for the acting member); new `work_item.assign` `{engagement_partner: allow, manager: allow, agent: deny, system: deny}` (engagements.yaml). `make regenerate`.
- **Engagements:** `api.independence_cleared(tenant, engagement_id, user_id)` (the one answer, ADR-164 item 4); `api.g2_blocks(tenant, engagement_id, user_id)` (attest and not cleared); `attest_column(engagement_id)` registered for `visible()` over `organisations.api.attest_client_ids()` (new: the attest clients' ids as a subquery, organisations owning its table); `work_items.assign_work_item(ctx, work_item_id, user_id, function)`: authorises `work_item.assign`, refuses 409 `gate_unmet` `{gate: G2, user_id}` when G2 blocks the target, inserts the insert-only `work_item_assignments` row and audits `work_item.assigned` in one unit of work (no route yet: P-07-T30 adds ENG-05's routes).
- **Tests:** `tests/unit/identity/test_independence.py`: TASK-045's cases keep running in the strict configuration (attest client, `g2_blocks_view` on: the fixture's defaults), plus G2 v2 cases: every marked (read, staff role) allowed for a pending member by default, every marked non-read refused on attest and allowed on non-attest, reads refused with the setting on attest only, unknown attest fails closed, firm roles, client roles, agents (through the initiator), system runs, break-glass support, walls before independence, `visible()` shapes; the closed list gains `client_access.grant` and `message.send`; the setting cannot be named by a cell. `tests/integration/test_g2_v2.py`: Ana on Northwind-like attest engagement reads, is refused `assign_work_item` (409 G2) and a sign-off action, `independence_cleared` false then true; a non-attest close is not gated; `g2_blocks_view` restores the read gate through `authorise` and `visible()`.
- **Rollback:** revert the commit; `alembic downgrade 0133`. Until reverted nothing is looser than ADR-164 allows: with the setting on, behaviour equals TASK-045 on attest clients.

## Progress log
- 2026-10-24: built as planned. DEC-270 records the one reading the ADR left open (marked writes other than assignment, sign-off and client-facing stay gated on attest clients). `tests/integration/test_follow_ups_v2.py::test_review5_an_unconfirmed_staff_member_may_read_but_not_send` encoded TASK-045's every-engagement send gate; its engagement is now made an attest client's (the assertion is unchanged; AC-14's non-attest side is in the unit suite). Unit: `tests/unit/identity tests/unit/engagements tests/security/test_permission_matrix_generated.py tests/unit/quality` 19,699 passed. Integration: `test_g2_v2.py` 5 passed; 15 identity/engagements files 715 passed, 2 xfailed; follow-ups, retrieval, request lifecycle, model journey 245 passed after the fix.
- 2026-10-24: final checks on the branch: `uv run pytest tests/unit tests/contracts tests/security` 27,444 passed, 4 xfailed; `make check-fast` green (the 0138 downgrade's DELETE was rewritten for SECRET-003).
