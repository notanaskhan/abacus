---
id: TASK-9019
title: "T-06-T56: Independent AC tests (ADR-078) for AY's S53-S54 entity services"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-t06-t56-independent-ac
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-06-T56
---

## Objective
Backlog row acceptance: "Each acceptance criterion in section 3 for F5, F7 and F8 has a named test that fails when the guarded line is removed." Written as notanaskhan's black-box suite (ac-test-author: notanaskhan) over HTTP on the migrated Postgres, plus the AC map below to the service, golden and web suites that guard the figure-level criteria.

## Done
- tests/integration/backfill/test_t06t56_s53_s54_services_ac.py (11 on Postgres): F5 a locked return 409 return_locked on every write and writes nothing (filed, accepted); F5 b2 Explain opens the issue with no gateway call and leaves the item unclassified; F5 client principal writes nothing; F7 another firm 404, client principal refused, draft download refused without fresh MFA with no event, page list 409 before an approved checkpoint; F8 graph 404 for a client principal (INV-4), walled reader refused (DEC-43), agent refused on create and end (INV-1)
- Mutation spot-check: removing explain's _writable and the relationships _human guard each fails its tests (2 and 1 failed); source restored
- AC map: F5 a test_t06t24 test_ac_bluestem_aaa_splits_70_30, test_t06t42 test_the_m2_columns_roll_by_line, lock test_t06t56 test_f5a_*; F5 b test_t06t25 test_ac_ashford_provision_and_etr; F5 b2 test_t06t25 test_ac_the_b2_variant_reports_1200_unclassified + test_t06t56 test_f5b2_*; F5 c test_t06t18 test_lakeshore_part_ix_foots_to_4_014_000_with_an_80_0_program_ratio, test_a_time_study_line_crossfoots_by_largest_remainder; F5 c3 test_t06t42 test_lakeshores_allocation_lands_only_as_a_proposal; F5 vocabulary web TXP-13.test.tsx
- AC map: F7 a test_t06t44 test_item_f_reads_17914500_bound_to_the_tb_total_assets_line, test_the_tin_is_masked_before_it_reaches_a_page, golden test_t06t44_form_face_render (watermark), test_t06t49 placeholders; F7 diagnostics test_t06t50 test_t06t50_acceptance_a_matching_txp10_issue_is_linked_never_duplicated; F7 b/c test_t06t44 test_k1_box_2_sums_against_schedule_k_line_2; F7 trace test_t06t44 test_fields_of_a_page_and_unknown_keys; F7 blocking test_t06t37 test_ac_post_answers_409_blocking_diagnostics; F7 download test_t06t56 test_f7_the_draft_download_* (the one form_preview.downloaded event needs WeasyPrint: image-bound, end pass)
- AC map: F8 a and DEC-88 test_t06t51 test_t06t51_acceptance_a_hidden_engagement_hides_its_edge_and_its_count, test_t06t51_the_banner_is_codes_text; DEC-43 and INV-4 and INV-1 test_t06t56 test_f8_*; not built (no guarded line yet): Add relationship writes, external parties and layouts answer 501 until T-06-T21; List toggle, f's SSE refresh, c/d/e renders wait on CLI-03's board (T-06-T68) and screen

## Progress log
- `2026-11-27` — Built; 11 pass on Postgres, two guards mutation-checked.
