---
id: TASK-1189
title: Walls v2 and offshore fail-closed — migration 0151 walls_v2, reason and named partner approver, preview, approve, partner-only lift, wall.created consumer, wall log, notification kinds; offshore in authorise and visible(), assert_assignable, TIN masking hook (G-01-T09)
spec: SPEC-002
acceptance_criteria: [AC-9, AC-10, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20]
risk_zone: red
status: in-review
epic: G-01
plan_key: G-01-T09
branch: s8a-org-walls-v2
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Lena Park is walled from Ashford with 404 and no count, Neil Ashcroft answers 409, only Margaret can approve, and Remy Vidal sees 0 clients."

## Plan (red zone)
- **Migration `0151_walls_v2.py`** (down_revision 0150): `ethical_walls` + `reason_code` (default `other`, CHECK the five codes), `reason_text` (≤ 500, Confidential), `approver_user_id`, `approved_by`, `approved_at`, `removed_reason`; CHECK `(approved_at IS NULL) = (approved_by IS NULL)`; insert grant on the new insert columns, UPDATE grant extended to `approved_by, approved_at, removed_reason`; `ethical_walls_forward_only` replaced so an active wall may be approved once (only the approval columns change) or removed, approval is never set after removal and never changes. Existing rows read `reason_code='other'`. Rollback: `alembic downgrade 0150` restores 0012's trigger.
- **Walls service (`identity/walls.py`, moved out of `service.py`):** create with reason, text and a named approver (an active partner-level member other than the walled person: 422 `approver_not_partner`); 409 `relationship_partner` (organisations registers the client's relationship partner through a slot), `wall_exists`; preview (blockers and the assignments it would end); approve (named approver only, 403 `not_named_approver`, 409 `already_approved`, fresh MFA); lift (`wall.remove` narrowed to partners, 409 `own_wall`, a reason). Every change emits `access.changed` for the walled person; `wall.created` and `wall.approved` are outbox events.
- **Consumer:** identity subscribes to `wall.created`: ends the walled person's engagement memberships on the client's engagements and, through an engagements slot, their work-item assignments; one audit row each as the system on behalf of the wall's creator; idempotent.
- **Wall log:** `audit_trail.api.events_for_target` registered into an identity slot; `GET /v1/walls/{id}/events`.
- **Notifications:** catalogue `wall.created` → `wall_approval_requested` (to the named approver, emailed by default), `wall.approved` → `wall_approved` (to the creator).
- **Offshore (DEC-52):** `authorise` denies an offshore person (or an agent or system run acting for one) every client-named resource without a consent (`register_consent_check('offshore_disclosure')`, fail closed), at the wall layer, so every route answers 404 as for a wall; `visible()`, `visible_scope`, `visible_clients` and `visible_items` exclude the same clients through a SQL consent column slot (unregistered: none). `identity.api.assert_assignable` (409 `offshore_consent_required`) wired into `work_item.assign`. `identity.api.mask_tins_for` for responses carrying `pii_kind=tin` fields. `GET /v1/firm/offshore` live.
- **Matrix:** `wall.create` + `firm_partner`; `wall.remove` → `firm_partner` only; `wall.list` + `security_admin`, `firm_partner`; agent and system denied on all. Regenerate.
- **Gate kind:** deferred (C13's `register_gate_kind` checks an engagement; a wall approval is firm-level) until I-01.
- **Tests:** `tests/integration/test_walls_v2.py` (AC8.x, Lena, Neil, Margaret named), `tests/integration/test_offshore.py` (AC9.x, Remy), `tests/security/test_tri_and_offshore.py` (I-OFFSHORE), the walls sweep extended (`test_walls_and_need_to_know.py`: an offshore member over the same surfaces and route sweep; v2 routes on the walled client), SPEC-002 v1 suite updated where the amended spec moves the lift to partners (DEC-169).

## Progress log
- 2026-10-25: plan written; building after T08.
- 2026-10-25: built. Migration 0151 (down_revision 0150). `identity/walls.py` (create with reason and approver, preview, approve, partner-only lift, list with the partner view, log, `wall.created` consumer), `identity/offshore.py` (ADM-03d read, `assert_assignable`, `hidden_clients`, `mask_tins_for`), offshore in `authorise` and every `visible*` at the wall layer, consent column/count slot. Slots: client partner (organisations), wall assignments (engagements), target events (audit_trail). Notifications `wall_approval_requested`, `wall_approved`. SPEC-002 amended (AC-9, AC-10 amended; AC-12 to AC-20). SPEC-002's v1 suite moved its lifts to partners (the amendment requires it) and pins the v2 keys. The extended sweep found `/v1/firm/clients/search` (and five other `walled_from` callers) blind to offshore: fixed with `hidden_clients`. ED-038: `functions_on` never honoured removal rows (latent; fixed). Gate kind deferred (C13 is engagement-scoped).
- 2026-10-25: a mistake to avoid: replacing "from an anchor to the end of the file" in a scripted edit dropped a function appended after the anchor (`wall_actions`), caught only by a 500 in the integration test. Edit between two named anchors instead.
- 2026-10-25: security review fixes: the wall client picker drops hidden clients (swept now); wall readers (register, log, approve, lift, drawer, audit rows) use `hidden_clients` so offshore readers learn nothing; the approver can't be the creator or someone the client is hidden from; the consumer reads the wall `FOR UPDATE`; an approval losing to a lift is 404; nobody clears their own offshore flag (403 `own_offshore`). Tests first: `test_review_*` in `test_walls_v2.py` and `test_offshore.py`, the picker test and the list sweep in `test_walls_and_need_to_know.py` (failed, then pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-318 | Walls v2 as built (approver optional for the legacy screen, lift reason, list shape) | No |
| DEC-319 | Offshore fail-closed as built (the wall layer, the consent column slot, masking hook, gate kind deferred) | No |
