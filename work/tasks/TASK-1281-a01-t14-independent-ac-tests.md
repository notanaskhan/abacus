---
id: TASK-1281
title: ADR-078 independent AC tests for A-01-T05, T08, T09 and T10 (A-01-T14)
spec: SPEC-330
acceptance_criteria: [AC-3, AC-4, AC-9, AC-10, AC-11, AC-12, AC-14, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25, AC-26, AC-27]
risk_zone: amber
status: done
epic: A-01
plan_key: A-01-T14
branch: s9b-independent-suites
test_author: ayushkbhatia
test_session: 2026-10-26, branch s9b-independent-suites (clean session following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Tests cover INV-1 phase refusals, INV-3 walls with no counts, metadata-only tags, tile footing and the PBC and archive-clock rules."

## Plan (amber zone)
- **Files:** `backend/tests/integration/backfill/test_a01t14_audits_independent.py` only (reuses the back-fill `net` and `seed` fixtures). No production change unless a test exposes a small local defect (none did).
- **Boundary:** `create_app()` over HTTP (`/v1/audits`, `/v1/audits/{id}/cockpit|phase|profile|source-documents`, `/v1/binders/{id}/requests`, `/v1/walls`) with `audits.cockpit` and `binders.engine` on, as an engagement partner, manager, staff, reviewer, firm admin (metadata only), a client admin and another firm; `assurance.api` (`record_phase` with an agent context, `register_index_tag`, `register_audit_section`) where the spec promises a later epic extends the cockpit without editing A-01; seeds as the superuser (phases placed on the projection as earlier moves would leave them).
- **Expectations from:** SPEC-330 §5, `docs/contracts/audits-cockpit.md`, A-01 §3.1, §3.5 and §3.7, the matrix (`assurance.yaml`, `engagements.yaml`, `requests.yaml`), `error-codes.yaml`, DEC-261 to DEC-263, DEC-311 to DEC-313. The implementer's tests were not read for expectations (their world fixture only, for the seed shape of binders, fulfilments and inbox files).
- **Rollback:** delete the file.

## Results (30 pass, 0 xfail)
- **T05, AC-9:** `test_ac9_a_person_records_only_the_next_phase` (201 Planning to Fieldwork, `recorded`; the current and an earlier phase 409 `phase_backward`; Released 409 `phase_skip`; then In review). **AC-10:** `test_ac10_a_phase_whose_gate_is_computed_cannot_be_recorded` (In review to Ready to release: 409 `phase_follows_gate`). **AC-11 (INV-1):** `test_ac11_staff_reviewer_client_and_the_firm_admin_may_not_record` (403 each, no event), `test_ac11_an_agent_context_is_refused_by_the_service` (Forbidden even with the action in its task scope), `test_ac11_the_table_refuses_a_recorded_row_without_its_human` (agent, system, human without a user). **AC-12:** `test_ac12_one_recorded_move_writes_its_event_projection_audit_and_outbox` (one event bound to the partner, `phase`, `phase_source`, `phase_changed_at`, `version` + 1, one `assurance.phase_recorded`, one outbox `assurance.phase_changed`), `test_ac12_the_phase_event_is_insert_only`. **AC-3:** `test_ac3_a_retried_phase_record_with_the_same_key_moves_once`. **AC-4:** `test_ac4_with_the_flag_off_the_audits_routes_answer_404`. **INV-3:** `test_inv3_a_walled_partner_and_another_firm_get_404_on_a_record`. **AC-14:** `test_ac14_the_ebp_profile_takes_its_kinds_a_version_and_an_audit` (dc and the §103(a)(3)(C) label; 409 `stale_version`; 422 for a health and welfare kind and a null label; staff 403; one `assurance.profile_updated`).
- **T08, AC-18 (tile footing):** `test_ac18_the_tiles_foot_to_the_total_and_a_pressed_tile_keeps_every_count`, `test_ac18_segments_count_the_base_without_the_segment_and_the_caption_counts_families` (no SOC & IT or Internal audit segment without the entitlement). **AC-19 (INV-3):** `test_ac19_a_walled_audit_is_absent_everywhere_and_nothing_counts_it` (rows, tiles, segments, caption, total; no "hidden" field; cockpit 404 with no name), `test_ac19_the_keyset_cursor_walks_every_row_once`. **AC-20 (PBC and archive clock):** `test_ac20_pbc_counts_asked_client_visible_requests_of_a_published_binder` (1 of 3, Draft and Not applicable left out; null with only a draft binder or none), `test_ac20_report_due_tones_read_kernel_clock` (past due, 3 days, 7 days amber per DEC-263, 20 days, 60 days), `test_ac20_a_released_audit_counts_60_days_to_archive_and_archived_groups_released` (released 47 days ago: `archiving`, 13 days left; an archived work item stays under Released, `archived`). **AC-21 (metadata-only tags):** `test_ac21_a_metadata_only_reader_sees_metadata_tags_and_never_a_content_tag` (firm admin: only `metadata` tags, "EQR · TW" from In review, never a registered content tag that a partner does see), `test_ac21_a_client_principal_is_refused_the_index` (index and cockpit 403).
- **T09, AC-22:** `test_ac22_a_later_epic_registers_a_row_and_unanswered_rows_never_render` (a registered Trial Balance row renders in Planning; a `None`, a raising and a provider-less section never do, the last refused at registration). **AC-23:** `test_ac23_a01s_overview_rows_read_source_documents_and_the_team_in_role_order` ("1 of 2 received", "MO · TW · HL · MD · AC", no Methodology or Standards set, no run start without a C6 provider). **AC-24:** `test_ac24_a_metadata_only_reader_gets_the_bar_and_overview_only`, `test_ac24_an_archived_work_item_is_read_only`.
- **T10, AC-25:** `test_ac25_the_firm_reads_owed_by_latest_upload_match_and_linked` (client contact, third party through an open delegation, none on a received row; the latest upload's label, version and `client` channel; match confidence 94; Linked 1), `test_ac25_a_client_principals_rows_never_carry_the_firm_only_facts`. **AC-26:** `test_ac26_source_documents_group_foot_and_order_missing_first` (binder category order, "n of N" without N/A, totals foot, needs review then requested then received, `q` narrows rows not totals). **AC-27:** `test_ac27_pbc_counts_follow_visibility_and_need_a_published_binder` (1 of 4; null once the binder is a draft again; walled: the row and Source Documents are gone, 404).

## Escaped defects
None found. ED-079 and ED-080 were not used.

## Spec drift (followed the later decision)
| AC | SPEC-330 / epic says | The current contract says | Superseded by |
|---|---|---|---|
| AC-9 | the record-mode sequence includes Completion | Completion is not offered; In review is followed by Ready to release, which (with Released and Archived) follows computed gates (409 `phase_follows_gate`) | DEC-262 |
| AC-20 | archive clock counts from the release | until A-01-T23's release record, the release date is the business date the phase became Released | DEC-311 |
| AC-20 | report due "≤ 7 days" is red | fewer than 7 days left is `within_7_days`; exactly 7 is `within_30_days` | DEC-263 |
| AC-24 | the cockpit route's action is `engagement.read` (stub) | `engagement.read_metadata`; bands, dock and actions also need `engagement.read` | DEC-312 |
| AC-25 | owed by may be an `organisation` | never produced (nothing stores an organisation that answers directly) | DEC-313 |

## Spec gaps
- AC-13 (a derived move from `gate.met`, and its replay) is dormant on main (DEC-262 item 4: only G1 to G3 emit `gate.met` and they open no phase), so it is not driven here.
- A system principal's refusal of `assurance.record_phase` is a matrix deny with no system bearer on HTTP; the agent context and the table CHECK are tested instead.
- AC-23's Methodology row with a pinned version, and the "Processing" badge with a registered C6 provider, are not covered (no pin or provider is registered in this suite; the slot has no unregister, so a test-registered run provider would leak into other suites).
- Slots registered by AC-21 and AC-22's tests stay registered for the session; their keys are unique per test and their providers answer only for that test's work item.
- A conflict's code arrives in `detail` (the platform's `DomainConflict` body); the tests accept `code` or `detail`.

## Progress log
- 2026-10-26: suite written from SPEC-330, the contract, matrix and decisions; 30 pass on the migrated testcontainer (`-n 2`). Seeding notes: a request hidden from the client is Draft by the 0071 trigger, and Not applicable needs its `na_reason` (`request_items_na_whole`). Gates on the file: ruff format, ruff check, pyright clean. No defects.
