---
id: TASK-993
title: Independent AC tests for notifications v2 with the C16 notifications-half contract tests, and golden figures for the binder slice (P-01-T14, P-06-T29)
spec: SPEC-013
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10]
risk_zone: amber
status: done
epic: P-01
plan_key: P-01-T14; P-06-T29
branch: s6-p01-p06-independent
test_author: ayushkbhatia
test_session: 2026-10-23, branches s6-p01t14-notifications and s6-p06t29-goldens (one clean session each, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-23
updated: 2026-10-23
---

## Objective
- **P-01-T14:** "The suite proves AC-7 no-text storage, walls at fan-out and read, OWN-only preferences and the email rules, and closes TASK-028." The row also requires that every registered kind code passes the database CHECK and the undotted rule and that no code is registered twice.
- **P-06-T29:** "The suite is green on the loaded tenant and fails under a seeded change to any section 5.4 figure."

SPEC-013 is the frontmatter spec because this task closes TASK-028 (SPEC-013 AC-1 to AC-10). The binder figures are SPEC-319 AC-10 and P-06 §5.4.

## Plan (amber)
- **P-01-T14:** `backend/tests/integration/backfill/test_p01t14_notifications.py` over HTTP and the public `notifications.api` on the migrated testcontainer Postgres; `backend/tests/contracts/c16_notifications/test_c16_kinds.py` for the kind catalogue against the database CHECK.
- **P-06-T29:** `backend/tests/integration/test_p06t29_binder_goldens.py`: E0 plus the `binders` slice loaded once into its own Postgres; each figure family is an observer that reads the database (and `GET /v1/binders`) and returns what it sees; the expected values are literals typed from P-06 §5.4, the BND-01 handoff rows and the screen contracts, never imported from the scenario package.
- **Rollback:** revert the commits; the three notification fixes revert with their tests.

## P-01-T14 results (55 pass, 3 xfail)
| Area | Result |
|---|---|
| AC-7 no-text storage | pass: the only text columns are kind, subject type, category and actor kind; no client or person name reaches a row; the feed returns kinds and references for the SPA to render |
| INV-3 walls at fan-out and read | pass: a walled person gets no row; a wall added later hides rows from every tab, the counts, the unread dot and the v1 list; `/read` answers 404; read-all skips them; someone removed from the team stops seeing rows |
| OWN-only preferences | pass: defaults are email on for `mention` only; a change affects only the caller and is audited once; a body naming a person is refused (422) and no route takes another person's id; an unknown or repeated kind is 422 and saves nothing; a kind turned off in the app is neither shown nor counted |
| Email rules | pass: the kind's default and the person's choice apply; kill switch off gives `suppressed` and sends nothing; one email after a redelivery, on the sink for a synthetic firm; only the fixed sentence, engagement name and opaque link, no file name, item text, surname or address |
| INV-1, INV-5 agent rows | pass after fix ED-013 |
| INV-4 staff-only email | pass after fix ED-014 |
| SPEC-013 AC-2 membership at fan-out | pass after fix ED-012 |
| Kind codes (contract) | pass: every registered code is inserted into the migrated database and passes the CHECK; new codes are undotted; no code is registered twice; inline actions come from the closed set; agent kinds offer none |
| P-01 AC 3.1.2 and 3.1.3 (a client upload waits in Approvals with facts and Accept/Return) | **xfail**: no kind registers a facts or pending resolver yet; TASK-406 defers the wiring to P-01-T16 |
| SPEC-013 AC-10 daily purge | **xfail**: ED-016 |
| C16 `register_kind_source` | **xfail**: ED-015 |

### SPEC-013 to its covering test (TASK-028 closed as superseded)
| SPEC-013 | Test (the integration file unless noted) |
|---|---|
| AC-1 | `test_ac1_one_notification_per_recipient_even_when_relayed_twice` |
| AC-2 | `test_ac2_a_client_upload_reaches_the_staff_team_never_the_client`, `test_ac2_a_self_join_notifies_the_team_but_not_the_joiner`, `test_ac2_a_person_whose_membership_was_revoked_is_not_a_recipient`, `test_ac2_a_person_of_another_firm_is_never_a_recipient` |
| AC-3 | `test_ac3_an_event_outside_the_catalogue_makes_no_notification` |
| AC-4 | `test_ac4_the_feed_lists_only_the_callers_own`, `test_ac4_another_persons_notification_is_not_found_and_stays_unread` |
| AC-5 | `test_inv3_a_wall_added_after_fan_out_hides_rows_from_list_counts_and_dot`, `test_ac5_a_person_removed_from_the_team_no_longer_sees_its_rows` |
| AC-6 | `test_ac6_reading_sets_read_at_once_and_read_all_reads_the_rest`, `test_ac6_rows_are_immutable_except_read_at` |
| AC-7 | `test_ac7_rows_store_identifiers_and_codes_never_text`, `test_ac7_the_feed_returns_kinds_and_references_for_the_spa_to_render`, contract `test_ac7_a_row_carries_identifiers_and_codes_and_only_facts_are_restricted` |
| AC-8 | the fan-out half: `test_ac2_a_self_join_notifies_the_team_but_not_the_joiner`. Emitting the event in the self-join's unit of work is engagements' code, not tested here |
| AC-9 | recipients: `test_ac3_1_2_tabs_filter_by_category_and_counts_are_unread` (a `budget.anomaly` event reaches the partner); support-session kinds by the contract tests' catalogue checks |
| AC-10 | `test_ac10_the_daily_purge_deletes_rows_older_than_180_days` (xfail, ED-016); the 30-day window: `test_ac4_1_4_rows_older_than_30_days_are_neither_shown_nor_counted` |

### Defects (each logged in `docs/quality/escaped-defects.md`)
| ID | Defect | State |
|---|---|---|
| ED-012 | fan-out gave a revoked member a row, and a payload naming another firm's person failed the whole event (`service.py` `_reauthorised`) | fixed |
| ED-013 | agent-originated kinds recorded actor kind `system` (`service.py` `notify`) | fixed |
| ED-014 | a mentioned client user was queued an email (`email.py` `queue_emails`) | fixed |
| ED-015 | `register_kind_source` not exported by `notifications.api` (C16 §3); `SUBSCRIPTIONS` is built at import, so adding it needs a subscription refresh | open, 1 xfail |
| ED-016 | `notifications_purge` deletes nothing (owner without BYPASSRLS, forced RLS); needs a new migration | open, 1 xfail |

The facts and pending resolvers (P-01 AC 3.1.2/3.1.3) are not a defect: TASK-406 defers them to P-01-T16. The xfail turns into a failure the day P-01-T16 lands them, so that task removes the marker.

### Spec drift (the later contract is tested)
| Item | Spec says | Contract says |
|---|---|---|
| SPEC-013 AC-6 | reading is not audited | C16 §7 and TASK-028's decision audit `notification.read` |
| P-01 AC 4.1.1 | audit event `notification_preference.updated` | frozen C16 v1 and the code use `notification_preference.changed` |
| C16 legacy dotted codes | the list omits `materiality.proposed`, `risk.approval_requested`, `finding.severity_proposed` | SPEC-305 (TASK-306) registered them; the contract test lists them as named drift |
| C16 §9 test path | `backend/tests/contracts/notifications/` | the folder is `c16_notifications/` |
| SPEC-013 AC-2 | no client user is ever a recipient | SPEC-032 lets a mentioned client hold an in-app row; tested as in-app yes, email never |

## P-06-T29 results (19 pass, 4 xfail)
| Test | Figure |
|---|---|
| `test_ac10_tiles_foot_to_241` | 1 + 48 + 0 + 40 + 152 = 241 |
| `test_ac10_224_returns_and_17_second_parts` | 224 "2025 Binder" + 17 "pt 2" |
| `test_ac10_224_returns_on_214_engagements_98_64_62_by_office` | 224 returns on 214 engagements; 98 / 64 / 62 by office |
| `test_bnd01d_no_ty2026_binders` | 0 TY2026 binders |
| `test_bnd01a_named_rows_status_work_item_and_last_activity` | the 15 named rows and Osterberg: work item, status, last client activity; the four "Marked done by" people and dates; Whitley closed Apr 10 |
| `test_bnd01b_fenwick_is_34_days_silent_at_e0` | Aug 11 to Sep 14 = 34 days |
| `test_bnd02a_feld_5_of_7_71_percent_nine_categories` | 5 of 7, 71%, 2 open, nine categories in order, published Feb 3 by Kevin Osei |
| `test_shl14d_copperleaf_close_intake_8_recurring_plus_1_ad_hoc` | 8 + 1 = 9, 7 received, Square payouts pending incorporation, 5 categories, due Sep 10, period 2026-08 |
| `test_shl14_keystone_bridge_letter_requested_sep_1_due_sep_25` | Requested Sep 1, due Sep 25 |
| `test_bnd01_grace_reads_the_figures_from_get_binders` | over `GET /v1/binders`: the tiles, "Showing 15 of 241", the part facet 224 / 17, Feld 5 of 7, "None in 30 days" returns only Fenwick, TY2026 empty |
| `test_a_seeded_change_to_a_figure_fails_its_golden` (9 cases) | each one change, in a rolled-back transaction, makes its golden report a different figure: a Closed binder made Complete; a second part renamed; a return moved to TY2026; a return moved office; Whitley reopened; Fenwick's last activity moved; a Feld request back to requested; Square payouts incorporated; the Keystone letter due Sep 30 |

**xfail (strict)**, figures §5.4 names that the loaded tenant does not carry yet. None is a code defect; each is a gap in the scenario slice:
- `test_bnd02d_thornbury_6_of_15_with_3_overdue_14_days_late` and `test_bnd01a_named_rows_n_of_m_foot_from_their_requests`: DEC-146 writes requests only for Feld and the close intake, so the other rows' "n of m" is declared data. Owed with the named rows' requests (DEC-146 names T-02-T11 for the final shape).
- `test_shl20a_granite_peak_surl_draft_with_31_files` and `test_bnd02g_claires_two_files_cover_four_installments`: the slice writes no Granite Peak SURL Draft or files, and no Claire uploads. P-06 §5.4 has them use F-04-T25's scenario documents; F-04-T25 landed on main (TASK-996) without them, so they are owed by a binder-slice follow-up.

**Defects fixed:** none; no slice code changed. `backend/tests/integration/agent_tests/support.py` gains `Seeder.held()`, a superuser connection held across statements.

**Drift:**
- Osterberg (BND-01 c) is asserted as Published, as DEC-146 decided; "Unpublished Sep 2 by Remy Vidal" stays a fixture override.
- Osterberg's "0 of 9": the database carries no requests for it (0 of 0); "0 of 9" stays in the fixture.
- Grace has no `client_service` membership in the loaded tenant, so she sees no binders without one (DEC-20); the route test adds the membership and flag as the P-06-T11 index test does. A gap in the slice, not fixed here.

## Gotchas
- `tests/integration/test_email_templates.py` assumes it is the first in the session to import the platform template `notification.mention`. `backfill/` sorts first, so this suite imports only `notification.client_uploaded`. The ordering dependency in the older test remains.

## Checks
- `uv run pytest tests/integration/backfill/test_p01t14_notifications.py tests/contracts/c16_notifications tests/integration/test_p06t29_binder_goldens.py -q`: 65 passed, 7 xfailed on main as of this PR.
- `make check-fast`; `uv run pytest tests/unit tests/acceptance tests/security tests/contracts -q`; `uv run pytest tests/integration -q` (the whole directory).

## Progress log
- 2026-10-23: both suites written in clean sessions; 3 notification defects fixed with their tests; 7 strict xfails recorded; TASK-028 closed as superseded.
- 2026-10-27 (S10 gap build, Q-03-T009): ED-015 and ED-016 fixed on `s10-gaps2-ed015-016`, and their two strict xfails are removed.
  - ED-015: `notifications.api.register_kind_source(code, event, recipients, subject, *, engagement_key)` adds a producing event to an existing kind and subscribes the relay to it. An unknown kind or an event that already produces a kind fails at startup. Tests: `tests/unit/notifications/test_kind_source.py`.
  - ED-016: `purge_once` runs the existing definer once per firm inside that firm's own session, so forced RLS lets the DELETE through. No migration was needed. The run is audited in each firm that lost rows, and a failing firm is logged without stopping the others.
