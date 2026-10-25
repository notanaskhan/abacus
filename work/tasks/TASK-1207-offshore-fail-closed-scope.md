---
id: TASK-1207
title: Offshore fail-closed scope - restricted records only (F-03 4.4) or every client (DEC-319)
spec: SPEC-002
acceptance_criteria: [AC-12, AC-18, AC-19, AC-20]
risk_zone: red
status: done
epic: G-01
plan_key: G-01-T09
branch: s8-offshore-narrow
created: 2026-10-25
updated: 2026-10-25
---

## Context

G-01-T09 (walls v2) implemented offshore fail-closed as a wall: until T-01 registers an offshore
consent provider, an offshore member reaches no client at all (DEC-319). F-03 section 4.4 and
P-07 AC-9 say offshore narrows only the conditioned `tin.reveal` (and other restricted records),
so an offshore manager keeps ordinary work. Four spec tests state the narrower rule and are strict
xfails citing this task:

- `tests/acceptance/test_f03_personas.py::test_an_offshore_manager_cannot_reveal_a_tin`
- `tests/acceptance/test_f03_personas.py::test_an_offshore_manager_keeps_ordinary_work`
- `tests/integration/test_f03_personas_db.py::test_offshore_membership_decides_tin_reveal[True-condition]`
- `tests/integration/test_tin_reveal.py::test_ac9_an_offshore_member_gets_403_and_nothing_is_logged`

## Decision (Ayush, 2026-10-25): option 1, narrow

Offshore without consent is refused restricted records only: the actions whose matrix entry
carries `not_offshore`; ordinary work continues. The four tests pass again.

## Plan (red zone)

- **The `not_offshore` actions** (`docs/architecture/permission-matrix/*.yaml`): `tin.reveal`
  (organisations.yaml) and `pii.reveal` (evidence.yaml). No other entry carries it (requests.yaml
  only mentions it in a comment, for binder kinds not yet live).
- **Remove the offshore wall** (`identity/authz/__init__.py`): the layer 2a' check
  (`_offshore_refused`), `_is_offshore` and its per-request cache, and `_offshore_clear` in
  `_not_walled` / `_not_walled_client` (so `visible`, `visible_scope`, `visible_clients`,
  `visible_items`). The `membership_offshore` table in `identity/repository.py` had no other reader:
  removed.
- **`hidden_clients`** (`identity/offshore.py`) becomes walls only; `offshore_hidden` removed. Callers
  keep `hidden_clients` (engagements service and drafts, platform capabilities, notifications
  catalogue, service and email, identity people, audit targets, walls); `walls._hidden` gives the
  register roles the whole register again; docstrings updated.
- **Kept:** the condition layer (`conditions_hold`: `not_offshore` refuses an offshore person, 403
  `condition`, consent or not), `assert_assignable`'s 409 `offshore_consent_required`, the
  `offshore_assignment_conflict` toggle guard, `own_offshore`, `mask_tins_for`, the ADM-03d read and
  the consent slot (`register_consent_check` with `column` and `count`, C19's shape).
- **No migration.** No route or matrix change; `error-codes.yaml` regenerated for one docstring.
- **Docs:** SPEC-002 AC-18 and its header amended; G-01 section 3.9 story note, AC9.1, AC9.2, the
  Remy narrative, the agents line and the §7216 row amended; DEC-319 amended (narrowed, open conflict
  removed); identity README.
- **Rollback:** revert the commit; nothing persistent changes.

### Consent and the condition (a note for review)

The brief said the consent provider "still lifts the condition for consented clients". Before
G-01-T09 it never did: `not_offshore` refused every offshore member, and DEC-52 ("SSNs stay masked
for them and cannot be revealed"), P-07 R-02 ("offshore members can never reveal"), G-01 AC9.4 and
SPEC-002 AC-20 say no reveal is ever among an offshore member's allowed actions. Specs win, so the
condition stays unconditional: consent gates assignment (AC9.3) and the ADM-03d count, never a
reveal. `test_tri_and_offshore.py::test_i_offshore_a_consented_client_still_allows_no_reveal` and
`test_offshore.py::test_ac9_2_a_registered_provider_changes_no_list_and_lifts_no_reveal` pin it.

## Tests changed

The four strict xfails: marks removed, assertions unchanged; all pass.

`tests/integration/agent_tests/test_offshore.py` (wide rule -> narrowed):
- `test_ac9_1_remy_vidal_sees_0_clients_and_every_deep_link_answers_404` ->
  `test_ac9_1_remy_vidal_lists_and_opens_his_clients_like_anyone_with_his_role`: both clients
  listed (total 2), client, engagement and team open (200); unknown ids still 404.
- new `test_ac9_1_a_wall_still_binds_remy_vidal`: walled from Ashford, it is 404 and unlisted.
- `test_ac9_2_an_agent_acting_for_remy_is_refused_at_the_wall` ->
  `test_ac9_2_an_agent_acting_for_remy_reads_like_him_and_a_wall_binds_it`: allowed, then refused at
  the wall once Remy is walled.
- `test_ac9_2_a_registered_provider_shows_only_consented_clients` ->
  `test_ac9_2_a_registered_provider_changes_no_list_and_lifts_no_reveal`: both clients listed and
  open; no reveal in `allowed_actions` on either.
- `test_ac9_2_turning_offshore_off_restores_access_by_roles` ->
  `test_ac9_2_offshore_on_or_off_access_follows_roles`: 200 both ways.
- AC9.3, ADM-03d and `own_offshore` tests unchanged.

`tests/security/test_tri_and_offshore.py`:
- `test_i_offshore_every_action_on_a_non_consented_client_is_refused_at_the_wall` ->
  `test_i_offshore_only_the_not_offshore_actions_are_refused_at_the_condition_layer`: over every
  matrix action on a client and an engagement, offshore Remy and an onshore manager with the same
  roles differ only on `not_offshore` actions, refused to Remy at `condition` and allowed to the
  control (non-vacuous); `allowed_actions` equals the control's minus the `not_offshore` set.
- `test_i_offshore_an_agent_and_a_system_run_for_remy_are_refused_too` ->
  `test_i_offshore_an_agent_for_remy_works_like_him_and_is_walled_with_him`.
- `test_i_offshore_a_consented_client_still_allows_no_reveal`: the non-consented client now gives
  the same answers as the consented one (roles apply, no reveal), instead of nothing.

`tests/security/test_walls_and_need_to_know.py`:
- `test_i_offshore_every_surface_hides_a_non_consented_client` (7 surfaces x 3 roles) ->
  `test_i_offshore_every_surface_answers_remy_as_it_does_onshore`: each probe reports Ashford and
  its findings equal those once offshore is turned off.
- `test_i_offshore_a_seeded_bypass_fails_every_surface` ->
  `test_i_offshore_a_wall_binds_remy_and_a_seeded_bypass_fails_every_surface`: offshore Remy walled
  from Ashford finds nothing; lifting the wall in the database makes every probe report it.
- `test_i_offshore_every_record_route_reads_ashford_as_if_it_never_existed` ->
  `test_i_offshore_a_walled_offshore_member_reads_ashford_as_if_it_never_existed` (walled as well).
- `test_i_offshore_with_no_consent_provider_no_client_is_reached` ->
  `test_i_offshore_with_no_consent_provider_both_clients_are_reached`: totals 2, records 200,
  `tin.reveal` refused at `condition` on both.
- `test_d1_the_wall_client_picker_leaves_out_a_client_hidden_from_the_reader`: `offshore_partner`
  now sees Ashford listed; new `walled_offshore_partner` case keeps it out.

`tests/integration/agent_tests/test_walls_v2.py`:
- `test_review_an_offshore_reader_learns_nothing_of_walls_on_non_consented_clients` ->
  `test_review_an_offshore_reader_reads_the_register_like_an_onshore_one`: offshore Daniel and
  offshore admin Ingrid list the wall and read its log, the drawer shows it, the audit rows don't
  hide it, Daniel approves and lifts.
- new `test_review_a_wall_still_hides_walls_from_an_offshore_reader`: the old 404s and hiding,
  caused by a real wall on Daniel.
- `test_review_the_named_approver_is_never_the_creator_nor_hidden_from_the_client`: an offshore
  partner is now a valid approver (201); a walled one stays 422 (unchanged assertion).

## Progress log

- 2026-10-25: opened at the S8 wave A assembly (#395); the wider rule holds meanwhile.
- 2026-10-25: Ayush chose option 1 (narrow). Plan above; built on `s8-offshore-narrow` (from
  `origin/s8a-batch`, b4c39ccf). Offshore wall removed from `authorise`, every `visible*` and
  `hidden_clients`; the condition layer, assignment guard, masking and `own_offshore` kept. Four
  xfails pass unmarked; G-01-T09's offshore tests moved to the narrowed rule (listed above).
