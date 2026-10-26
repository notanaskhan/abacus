---
id: TASK-1284
title: Back-fill TASK-064, TASK-065 and TASK-066 (content rules, the matcher agent, the matcher in the product and Suggest with AI) from SPEC-033, fake model only (Q-03-T033)
spec: SPEC-033
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T033
branch: s9b-independent-suites
test_author: ayushkbhatia
test_session: 2026-10-26, branch s9b-independent-suites (clean session following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"A match proposal never files a document without a named person's decision and the code rules keep their reasons."

## Plan (red zone)
- **Files:** `backend/tests/integration/backfill/test_q03t033_matcher.py` only. No production change unless a test exposes a small local defect (none did).
- **Boundary:** `create_app()` over HTTP (inbox, assign, `inbox-matches`, `inbox/{file}/match`) as partner, manager, senior, staff, reviewer, firm admin, a client admin, a walled member and another firm; the compose S3 image; the `upload_processing` stages run on the stored inbox file (extraction, word layer, PII scan, so the matcher's material exists whether or not masking waits for the scan); the matcher's two activities (`inbox_match.create_run`, `inbox_match.match`) in a Temporal `ActivityEnvironment`, with a stub provider on the real `bedrock` route. Never a real model, never `make evals` (ADR-076).
- **Expectations from:** SPEC-033 §4, §5, §9 (Q1, Q3, Q5); the agent spec `evidence.matcher` (confidence floor 0.5); the matrix rows `inbox_match.read`, `inbox_match.request`, `inbox_match.run`; `error-codes.yaml` (`ai_match_unavailable` 409); DEC-267; DEC-43; ADR-164.
- **Rollback:** delete the file.

## Results (19 pass, 0 xfail)
- **AC-1 (TASK-064):** `test_ac1_an_extracted_statement_is_suggested_by_its_contents_with_fixed_reasons` (a statement named "scan0042.pdf" goes to the 4471 request first, source `content`, reasons `kind`, `date`, `account` from the fixed set, account value carries 4471, at most three); `test_ac1_the_content_rules_run_for_a_firm_that_is_not_synthetic`; `test_ac1_a_file_without_content_facts_keeps_its_file_name_suggestion` (a loan agreement named "debt agreements.pdf": source `file_name`, only the `file_name` reason); `test_ac1_the_code_rules_keep_their_reasons_beside_a_matcher_pick` (the pick first with no reasons, the content suggestion keeps its reasons, one list of at most three, each request once). Pass.
- **AC-2 (TASK-064):** `test_ac2_the_needed_account_digits_decide_between_two_statement_requests` (both directions, 4471 and 2290). Pass.
- **AC-3 (TASK-065, TASK-066):** `test_ac3_only_verified_in_list_proposals_above_the_floor_are_shown` (of a verified in-list proposal, an in-list proposal whose quote is not in the document, and `R60` outside the list, only the first is shown, with its rationale and verified quote; the unverified one is kept hidden in `inbox_match_proposals`; nothing is stored for `R60`); `test_ac3_a_verified_proposal_under_half_confidence_is_not_shown`; `test_ac3_none_fit_is_shown_with_its_rationale_and_no_proposal`; `test_ac3_suggest_with_ai_is_for_partner_manager_senior_and_staff` (202 and one dispatch each; reviewer, client admin and firm admin 403); `test_ac3_suggest_with_ai_without_a_real_route_is_ai_match_unavailable` (409). Pass.
- **AC-4 (TASK-065):** `test_ac4_a_real_firm_is_refused_at_the_boundary_and_keeps_its_content_suggestions` (the run fails `data_boundary`, the stub receives no call, the content suggestion stays). Pass.
- **AC-5 (TASK-066):** `test_ac5_a_client_gets_the_pick_without_rationale_or_quotes_and_no_firm_read` (the client's inbox carries the pick as `source: matcher` by request ID with no reasons; neither the rationale nor the quote appears anywhere in the client's response; `GET …/inbox-matches` 403); `test_ac5_the_firm_reads_are_for_firm_roles_and_g2_blocks_view_gates_a_pending_member`; `test_ac5_a_walled_member_and_another_firm_get_404`. Pass.
- **AC-6 (TASK-064, TASK-066; INV-1):** `test_ac6_a_proposal_files_nothing_until_a_named_person_assigns_it` (after a completed run: no new evidence version, no fulfilment, the file still waits; the manager's assignment then fulfils the request and its audit row is human, names the manager, `suggestion_source` 3 and `suggestion_rank` 1); `test_ac6_the_audit_records_a_followed_content_or_file_name_suggestion` (2 and 1); `test_ac6_the_matchers_agent_context_may_not_assign_a_file` (`authorise(agent, "evidence.upload")` is Forbidden). Pass.

## Escaped defects
None found. ED-079 and ED-080 (reserved for this wave's T033/T14 work) were not used.

## Spec drift (followed the later decision or contract)
| AC | SPEC-033 says | The current contract says | Superseded by |
|---|---|---|---|
| AC-5 | `inbox_match.read` for firm roles with independence (matrix `independence: required`) | a pending member reads by default; `g2_blocks_view` restores the gate on an attest client's engagement | ADR-164 items 2 and 3 (P-07-T24) |
| §6 | firm reads at `GET …/inbox/matches` | `GET …/inbox-matches` | TASK-066 decision table |
| §4.2 | prompt `evidence.inbox_match@v1` | agent spec `evidence.matcher` v2, prompt `@v2` | TASK-067 (cell references) |
| AC-6 | "the audit records which suggestion source and rank" | integers: `file_name` 1, `content` 2, `matcher` 3 | TASK-064 D5, TASK-066 §7 |

## Spec gaps (recorded, not filled from the code)
- "A request ID not in the candidate list is discarded and recorded": where the discard is recorded is unsaid; the test asserts only that nothing is stored or shown for it.
- "Suggest with AI" is "audited" (TASK-066 D5) with no action name in the spec; not asserted.
- The 409 body carries the code as `{"detail": "ai_match_unavailable"}` (the platform's `DomainConflict` shape), not a separate `code` key.
- Not back-filled here: AC-7 and AC-8 (evaluation thresholds and injection cases) are eval-level and `make evals` is never run by an agent; AC-9 (screen states, the AI tag) stays with the Inbox panel's vitest; the Q3 skip rule and the P-7 policy decisions are reached only through the outbox event path and stay with `tests/unit/agents/test_match_policy.py`.

## Masking branch (`s9a-pii-masking`, unmerged)
Written against main. Every matcher test runs the word layer and the PII scan on the inbox file before the run, so the branch's rule that a PDF with page text has no agent material until its scan is met. Quotes are taken from text without PII (the loan agreement's dated sentence, the statement's bank name), so a masked projection reads them the same. The content-rule tests read extraction columns, which the branch does not change. Expected conflicts: none; the most exposed test is `test_ac1_the_code_rules_keep_their_reasons_beside_a_matcher_pick` (a bank statement page, whose account number the branch masks; the quote avoids it).

## Progress log
- 2026-10-26: suite written from SPEC-033, the agent spec, matrix and error codes; 19 pass on the migrated testcontainer (`-n 2`, together with TASK-1281's suite: 49 pass). Gates on the file: ruff format, ruff check, pyright clean. No defects. `docs/quality/backfill.md` rows 064, 065, 066 to be set `back-filled` by the integrating session.
