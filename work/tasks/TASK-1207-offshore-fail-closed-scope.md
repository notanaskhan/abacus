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
- 2026-10-25: checks. `pytest tests/unit tests/contracts tests/security tests/acceptance`: 31489
  passed, 2 failed, 24 xfailed. The two failures (`test_f03_status_vocabulary.py`: the TB label
  isn't sentence case; no YAML entry for `FirmExportOut.status` `awaiting_approval`/`building`) fail
  the same way on the untouched base b4c39ccf: they are #395's, not this task's. Targeted
  integration (walls api/enforcement/runs/schema/v2, offshore, TIN reveal, F-03 personas, people v2,
  offices/teams, team roles, org v2, schema check, and the backfills staff people, team management,
  firm-level reads, contacts access, client invitations, P-07-T14, T26, T30, independence gate,
  F-03-T31, signup, P-01-T14): 778 passed, 6 xfailed (none TASK-1207). `test_tenancy_escape` ran in
  the security suite. ruff, pyright, banned patterns, validate_docs, error_codes (regenerated) and
  `make check-fast` (after `pnpm -C packages/api-client build:types`) pass.
- 2026-10-25: security review of the narrowing (1 high, 1 medium-high, 1 medium, 3 low); all six
  fixed in one commit, each with a test written first and seen failing (item 5's strict
  `refused == NOT_OFFSHORE` already held: `seed.member` confirms independence, so `pii.reveal`
  reaches the condition; it is now pinned).
  1. HIGH, raw evidence: `identity.api.refuse_unmasked_read` (one helper, 403 at the condition,
     after the route's `authorise`) in `download`, `upload_preview(_page)`, `version_preview(_page)`
     and `inbox_preview(_page)`. Masked renditions exist only in the P-03 viewer, which stays open;
     the legacy routes refuse. Test: `backfill/test_offshore_evidence_reads.py` (each of the seven
     routes: onshore 200 with its read logged, offshore 403 with nothing read, walled offshore 404).
  2. MEDIUM-HIGH, agents: `evidence/masked_text.masked_pages` now takes either source;
     `review_material` and `match_material` take `masked=`; the reviewer, matcher and entry
     assessor pass it from the run's initiator (`acts_for_offshore`), and their `create_*_run`
     from `requested_by`. Masking chosen (as the portal drop); no scan, no material, no run. Test:
     `trust_kit/test_offshore_agent_material.py` (both agents; checked failing with masking off).
  3. MEDIUM, assignment: `assert_assignable` in `add_creator_as_partner`,
     `add_rolled_forward_member`, `add_self_joined_admin` (both now take the client) and
     `replace_eqr`, before the candidate check (also moved there in `add_member`) so the answer is
     409; `team_candidate_ids` takes `offshore_consented` and leaves offshore members out without it.
     Tests: `test_offshore.py::test_review3_*` (create by an offshore partner and admin, consented
     create, roll-forward availability and refusal, self-join).
  4. LOW: `set_member_profile` raises `offshore_assignment_conflict`. Test:
     `test_review4_provisioning_cant_turn_offshore_on_over_assignments`.
  5. LOW: `refused == NOT_OFFSHORE == {tin.reveal, pii.reveal}`; the PII reveal route authorises
     `pii.reveal` before its 501 (`viewer.authorise_reveal`), so offshore gets 403 (route test in
     item 1's file).
  6. LOW: `mask_tins` (central; dicts handled) and `tests/contracts/test_offshore_tin_masking.py`
     (every TIN-tagged response calls `mask_tins_for` or is `not_offshore`; the dict case failed
     first).
  DEC-319 updated.
  Checks (targeted only): offshore, TRI and offshore, walls and need-to-know, walls v2/api/
  enforcement/runs, TIN reveal, C4 contract, the TIN-masking contract, clients contract, the new
  evidence-reads file, evidence, evidence storage, trust kit (viewer, PII scan, agent material),
  uploads and processing, detached keys, withdrawal, screening aggregate, portal drops,
  independence gate, the gateway PII and tax-return agent tests, unit agents/evidence/identity/
  engagements, people v2, engagements, team roles, offices and teams, scenario people, the identity
  backfills, `test_schema_check_db`, `test_tenancy_escape`: 16,508 passed, 4 xfailed, 0 failed in
  one session; its 318 setup errors ("fixture 'net' not found", from mixing the trust-kit and
  backfill conftests in one session) were the backfill and gateway files, which rerun on their own
  pass: 319 passed, 4 xfailed. ruff, pyright, banned patterns, validate_docs, error_codes and
  `make check-fast` pass.
- 2026-10-25: re-check of 05352733 (ten items; root cause: agent outputs store verbatim quotes and
  rationales from unmasked runs onshore people started). One commit, failing closed, each with a
  test written first and seen failing. The rule lives in `identity/offshore.py` only
  (`refuse_unmasked_read`, `may_read_unmasked`, `person_reads_unmasked`; `acts_for_offshore` is now
  private). Choices, per route:
  1-3. Upload-reviewer flags (`review_of`), inbox-matcher proposals (`matches_of`), entry-assessor
     assessments (`assessments_of`): refused, 403 condition, after their `authorise`.
  4. Statements: refused in `_authorised_upload`, so the draft, the preview and the approval alike.
  5. Setup files: refused in `download_setup_file` after `stored_file`'s `setup.read`.
  6. Screening results: refused. Review queue (mixed): kept, its proposal without rationale,
     citations and unverified claims (id and action stay, so a decision still names it);
     `proposals_for` reads through an unrefused `_screening_results`.
  7. Run traces: refused in `trace_for`, which the export builds on (all runs, fail closed).
  8. Screener: no run for an offshore requester (`create_screening_run`), and `_screen` fails a
     run whose initiator turned offshore before reading the sheet or calling the model. Masked
     material has no sheets, so there is nothing to send.
  9. `value_text` left out for offshore readers in citation views and viewer regions.
  10. `not_offshore` on `export.create`, `firm_export.download`, `run_trace.export`,
     `trial_balance.export`; `make regenerate` (matrix, its generated tests, OpenAPI: the reveal
     route's docstring from the last commit too).
  Tests: `backfill/test_offshore_agent_outputs.py` (the sweep over every served firm GET route,
  NAMED surfaces non-vacuous; 403 per refused route; the queue's metadata; the citation value;
  the content POSTs; the setup file; a wall still first), `agent_tests/test_offshore_screener.py`,
  `test_tri_and_offshore.py` (the exports are `not_offshore`; `refused == NOT_OFFSHORE` minus the
  firm-level download, which security admins show). The sweep fills only this engagement's ids:
  stored content behind other ids (audits' source documents) isn't reached by it.
  Changed test: `test_walls_and_need_to_know.py::test_i_offshore_every_surface_answers_remy_as_it_does_onshore`
  now expects a run's trace and its export to answer 403 to offshore Remy (item 7); every other
  finding still equals onshore.
  Checks (targeted, five sessions so the conftests don't collide): agent tests (offshore, walls
  v2/api/enforcement/runs, agent runs, board reads, screener, screening, observability, gateway)
  445 passed, 1 failed (`test_observability_audit` relay test: order-dependent, its batch of 500
  outbox rows; the file passes alone, 27 passed); backfills (both offshore files, independence
  letter, gate, human-gate projector, P-06-T18/T19/T20, uploads, portal drops, identity backfills)
  348 passed, 5 xfailed; trust kit 74 passed; evidence, TIN reveal, audits read models, review
  undo and staleness, retrieval, people v2, engagements, team roles, `test_schema_check_db`,
  journey 744 passed, 2 xfailed; security (TRI and offshore, walls sweep, tenancy escape, matrix
  generated, fresh MFA, route introspection), contracts, unit agents/evidence/identity/
  engagements/api 21,889 passed (the 5 surface cases above, fixed and rerun: 21 passed).
  ruff, pyright, banned patterns, validate_docs, error_codes, `make regenerate` and
  `make check-fast` pass.
