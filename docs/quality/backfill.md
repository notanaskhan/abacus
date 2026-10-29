# ADR-078 back-fill tracker

The 55 tasks that merged without an independent acceptance-test suite, and how each one gets one (chapter 10 §10.3.1; Q-03 §3.2; Q-03-T002). Fifty-three carry the deferral note, plus TASK-019 and TASK-029. **34 red, 21 amber.** Updated by every back-fill PR; the weekly quality report (`abacus_tools.quality.report`) counts the statuses below.

**Statuses.** `tranche 0`: kept as built and covered before Q-03 (QD-2), re-run at S12 by Q-03-T059. `scheduled`: a Q-03 row owns the suite. `back-filled`: the suite is on `main` and every AC has a named `test_ac<N>` test that passes or is `xfail(strict=True)` with a recorded defect. `superseded`: QD-3, closed by the replacing epic's AC suite (named in the last column), never by deletion. There is no "superseded-pending" status (Q-03 §3.2 B3).

**Test author.** Solo edition: the builder (ayushkbhatia) writes every suite, in a session that loads the spec, the contract and the ADRs, never the implementation (`.claude/skills/ac-test-author/SKILL.md`). The two-person split of ADR-078 is void (`AMENDMENT-solo.md` item 3); the clean-session rule stays.

**Defects.** A failing AC is triaged as a defect or as spec drift in the back-fill PR's task file, and every defect is logged in `docs/quality/escaped-defects.md` with the layer that should have caught it (Q-03-T009).

## The 55

| TASK | Zone | Area | Spec | Sprint | Q-03 row | Status | Suite or closing task |
|---|---|---|---|---|---|---|---|
| 075 | red | Data boundary, part 1 | SPEC-036 | S0–S3 | T059 | tranche 0 | `tests/unit/ai_gateway/test_client_data_boundary.py`, `test_client_data_register.py` |
| 049 | red | A real model in evaluation, behind a data boundary | SPEC-026 | S0–S3 | T059 | tranche 0 | `tests/unit/ai_gateway/test_data_boundary.py`, `tests/unit/tools/evals/test_real_mode.py` |
| 025 | red | Model routes, a second route configured | SPEC-010 | S0–S3 | T059 | tranche 0 | `tests/integration/agent_tests/test_gateway_timeout.py` and the SPEC-010 tests |
| 021 | red | Output controls and the outbound scope checker | SPEC-006 | S0–S3 | T059 | tranche 0 | re-run at S12 |
| 022 | red | Budget hierarchy, metering, denial-of-wallet | SPEC-007 | S0–S3 | T059 | tranche 0 | re-run at S12 |
| 019 | red | Review queues and review decisions | SPEC-004 | S0–S3 | T059 | tranche 0 | re-run at S12 |
| 029 | red | Firm-level reads for engagement roles | SPEC-014 | S0–S3 | T059; T021 (S8) | tranche 0 | `tests/integration/backfill/test_firm_level_reads.py`; extended to the P-06 scope kinds by `backfill/test_q03t021_scope_kinds.py` (T021, TASK-1232) |
| 027 | red | Break-glass support access | SPEC-012 | S0–S3 | T059 | tranche 0 | re-run at S12 |
| 020 | amber | Evaluation runner, graders and calibration | SPEC-005 | S0–S3 | T059 | tranche 0 | re-run at S12 |
| 041 | red | People and firm roles | SPEC-024 | S6 | T006 | back-filled | `backfill/test_staff_people.py`; AC-8 `apps/web/src/legacy/spec024states.test.tsx` (TASK-992) |
| 045 | red | Per-person independence gate | SPEC-025 | S6 | T006 | back-filled | `backfill/test_independence_gate.py` (TASK-992) |
| 030 | red | Client invitations and client users | SPEC-015 | S6 | T007 | back-filled | `backfill/test_client_invitations.py` (TASK-992) |
| 032 | red | Engagement team management | SPEC-017 | S6 | T007 | back-filled | `backfill/test_team_management.py`; AC-7 `apps/web/src/legacy/spec017people.test.tsx` (TASK-992) |
| 040 | red | Self-serve sign-up and engagement types | SPEC-024 | S6 | T008 | back-filled | `backfill/test_signup_and_engagement_types.py`; AC-8 `legacy/spec024states.test.tsx` (TASK-992) |
| 044 | red | Acceptance, independence, letter and the engagement gate | SPEC-025 | S6 | T008 | back-filled | `backfill/test_acceptance_independence_letter.py`, `test_independence_gate.py`; AC-9 `legacy/spec025states.test.tsx` (TASK-992) |
| 035 | red | Client portal, item visibility and client uploads | SPEC-020 | S7 | T014 | back-filled | `backfill/test_client_uploads_and_processing.py`; hostile files `tests/security/test_upload_hostile_files.py` (TASK-1140); AC-8 "received" is `uploaded` under DEC-09 |
| 056 | red | Upload processing, part 3: previews | SPEC-029 | S7 | T014 | back-filled | `backfill/test_client_uploads_and_processing.py`; hostile files `tests/security/test_upload_hostile_files.py` (TASK-1140) (AC-12) |
| 054 | red | Upload processing, part 1: scanning, workflow, extraction | SPEC-029 | S7 | T015 | back-filled | `backfill/test_client_uploads_and_processing.py`; hostile files `tests/security/test_upload_hostile_files.py` (TASK-1140); AC-3 follows SPEC-312 (`not_extracted`/`needs_ocr`); ED-018 to ED-021 open |
| 055 | red | Upload processing, part 2: kinds and mechanical checks | SPEC-029 | S7 | T015 | back-filled | `backfill/test_client_uploads_and_processing.py`; hostile files `tests/security/test_upload_hostile_files.py` (TASK-1140) (AC-5, AC-6, AC-8) |
| 036 | red | Client connection flow, health, access log, revoke | SPEC-020 | S8 | T022 | back-filled | `backfill/test_q03t022_connections_and_ledger_import.py` (TASK-1232); CONN-001 spy in every test; routes follow TASK-036 D1, D3 to D5 |
| 052 | red | Ledger file import, part 1 | SPEC-028 | S8 | T022 | back-filled | `backfill/test_q03t022_connections_and_ledger_import.py` (TASK-1232); routes follow TASK-052 and TASK-053 (`…/connection/import`, no period) |
| 069 | red | GL detail, part 1: isolated parsing, immutable snapshots | SPEC-034 | S8 | T023 | back-filled | `backfill/test_gl_detail.py` (TASK-1232); AC-6 same-bytes not reachable over HTTP |
| 048 | red | Roll forward from last year's engagement | SPEC-025 | S8 | T023 | back-filled | `backfill/test_roll_forward.py` (TASK-1232); AC-9 `legacy/spec025states.test.tsx` |
| 038 | amber | Classification, automatic retrieval, evidence board | SPEC-022 | S8 | T024 | back-filled | `backfill/test_classification_board.py` (TASK-1232); two defects fixed (reclassify on a changed description; the retrievable share's denominator) |
| 068 | amber | Ledger file import, part 3: TB exports | SPEC-028 | S8 | T024 | back-filled | `backfill/test_ledger_formats.py` (TASK-1232); five formats round-trip |
| 070 | amber | GL detail, part 2: workbooks and upload screens | SPEC-034 | S8 | T024 | back-filled | `backfill/test_gl_detail.py`; AC-9 `legacy/q03ledgerstates.test.tsx` (TASK-1232); GL error state fixed |
| 071 | amber | GL detail, part 3: GL exports | SPEC-034 | S8 | T024 | back-filled | `backfill/test_gl_detail.py` (TASK-1232); five GL formats round-trip |
| 050 | red | Engagement agent v1, part 1 | SPEC-027 | S9 | T031 | back-filled | `backfill/test_q03t031_engagement_agent.py` (TASK-1282); SPEC-027 §14 actor kind follows TASK-050 D2 |
| 051 | red | Engagement agent v1, part 2: due dates, reminders, digest | SPEC-027 | S9 | T031 | back-filled | `backfill/test_follow_ups_and_due_dates.py`, `test_due_dates_and_delegation.py` (re-run unchanged); INV-1 and DEC-74 in `backfill/test_q03t031_engagement_agent.py` (TASK-1282) |
| 058 | red | Upload reviewer, part 1 | SPEC-030 | S9 | T032 | back-filled | `backfill/test_q03t032_upload_reviewer.py` (TASK-1283), stand-in model; AC-8 stays with `unit/tools/evals/test_upload_review_cases.py` |
| 059 | red | Upload reviewer, part 2 | SPEC-030 | S9 | T032 | back-filled | `backfill/test_q03t032_upload_reviewer.py` (TASK-1283); AC-10 `screens/SHL-20/SHL-20.test.tsx`, `screens/AUD-03/AUD-03.test.tsx` (the legacy `spec030review` suite retired with its screen, its assertions mapped in SPEC-330 §8; DEC-442) |
| 065 | red | Content matching, part 2: the matcher agent | SPEC-033 | S9 | T033 | back-filled | `backfill/test_q03t033_matcher.py` (TASK-1284); fake model on a stubbed real route; AC-7, AC-8 eval-only |
| 066 | red | Content matching, part 3: Suggest with AI | SPEC-033 | S9 | T033 | back-filled | `backfill/test_q03t033_matcher.py` (TASK-1284); `inbox_match.read` independence follows ADR-164 |
| 064 | amber | Content matching, part 1: code suggestions | SPEC-033 | S9 | T033 | back-filled | `backfill/test_q03t033_matcher.py` (TASK-1284); AC-9 stays with the Inbox panel's vitest |
| 062 | red | Comments, part 1 (backend) | SPEC-032 | S10 | T039 | back-filled | `backfill/test_q03t039_comments_and_drafter.py` (TASK-1308); AC-10 stays with TASK-063's vitest |
| 072 | red | Drafted guidance, part 1 | SPEC-035 | S10 | T039 | back-filled | `backfill/test_q03t039_comments_and_drafter.py` (TASK-1308); AC-1, AC-7 need a model and stay with `evals/guidance_drafting` |
| 073 | red | Drafted guidance, part 2 | SPEC-035 | S10 | T040 | back-filled | `backfill/test_q03t040_drafted_guidance.py` (TASK-1309); ADR-111 on a real firm asserted with the setting forced on underneath |
| 074 | red | Drafted guidance, part 3 | SPEC-035 | S10 | T040 | back-filled | `backfill/test_q03t040_drafted_guidance.py` (TASK-1309); template drafting refusals |
| 033 | amber | Request list import from Excel | SPEC-018 | S11 | T047 | back-filled | `backend/tests/integration/backfill/test_q03t047_requests_client_hub.py` |
| 037 | amber | Request item detail | SPEC-021 | S11 | T047 | back-filled | `backend/tests/integration/backfill/test_q03t047_requests_client_hub.py` |
| 039 | amber | Uploads on the client's behalf, inbox, matching | SPEC-023 | S11 | T047 | back-filled | `backend/tests/integration/backfill/test_q03t047_requests_client_hub.py` |
| 060 | amber | Client hub, part 1 (backend) | SPEC-031 | S11 | T047 | back-filled | `backend/tests/integration/backfill/test_q03t047_requests_client_hub.py` |
| 024 | red | Knowledge retrieval infrastructure | SPEC-009 | S11 | T048 | back-filled | `backend/tests/integration/backfill/test_q03t048_knowledge_retrieval.py` |
| 026 | amber | Feature flag registry | SPEC-011 | S11 | T050 | back-filled | `backend/tests/integration/backfill/test_q03t050_feature_flags.py` |
| 023 | amber | Engagement graph and methodology v1 | SPEC-008 | S10–S26 | T065, T525 | superseded | **K-01**'s AC suite; legacy path back-filled by M8 (T525) |
| 028 | amber | In-app notifications | SPEC-013 | S6 | T065 | superseded | **P-01**: P-01-T14, closed: `backfill/test_p01t14_notifications.py`, `contracts/c16_notifications/test_c16_kinds.py` (TASK-993) |
| 034 | amber | Knowledge, budget, support access and walls screens | SPEC-019 | S6–S14 | T065 | superseded | **G-01**, **G-02**, **K-01** AC suites; walls and support backend by T012 and tranche 0 |
| 042 | red | Autonomy policy and the onboarding checklist | SPEC-024 | S9–S14 | T065 | superseded | **G-02** AI policy v1 (ADR P-49) AC suite |
| 043 | amber | Clients you already have; invitations in the firm's name | SPEC-025 | S4–S15 | T065 | superseded | **P-07** CLI-04/06 AC suite |
| 046 | amber | The engagement setup page | SPEC-025 | S4–S15 | T065 | superseded | **P-07** ENG-02/03 AC suite |
| 047 | amber | New engagement offers the template for its type | SPEC-025 | S4–S15 | T065 | superseded | **P-07** ENG-03 AC suite |
| 053 | amber | Ledger file import, part 2 (web) | SPEC-028 | S8–S17 | T065, T524 | superseded | **A-02** AUD-06 AC suite; legacy path back-filled by M8 (T524) |
| 057 | amber | Upload processing, part 4: screens for checks | SPEC-029 | S3–S12 | T065 | superseded | **P-03** SHL-08 and **P-06** BND AC suites (P-06-T17, P-06-T23) |
| 061 | amber | Client hub, part 2 (web) | SPEC-031 | S7–S18 | T065, T524 | superseded | **R-01** POR-02/03 AC suite; legacy path back-filled by M8 (T524) |
| 063 | amber | Comments, part 2 (web) | SPEC-032 | S0–S10; S33–S37 | T065, T525 | superseded | **F-05** restyle (component tests kept), then **P-05** SHL-18; legacy path back-filled by M8 (T525) |

## Totals

| Status | Rows |
|---|---|
| tranche 0 | 9 |
| scheduled | 10 |
| back-filled | 25 |
| superseded | 11 |
| **Total** | **55** |

M8 (Fri May 28, 2027) needs 44 back-filled (tranche 0 included) and 11 superseded, each with an independent AC suite (Q-03 §3.2 B3).

## Q-03-T011: the 2027 Q1 catch-up lane

These are independent suites for amber epic rows that an epic deferred. Each row lists the suite and its first run.

| Row | Spec | Status | Suite |
|---|---|---|---|
| F-04-T16 (TASK-392) | SPEC-307 AC-7 | back-filled | `backfill/test_f04t16_clock_adoption.py` (4 passed, 2026-10-27): independence conclusion in business time; mail sink, signup-code expiry and access review in system time. The static half is CLOCK-001 (F-04-T17). |
| Q-01-T43 (TASK-1212, Q-01-T36/T37) | platform-ops §3.7 | back-filled (repo half) | `backfill/test_q01t43_platform_controls_independent.py` (7 passed, 2026-10-27). Read-only answers 503 on every mutating route in the OpenAPI route table except the exemptions §3.7 names; control history is insert-only for the app and operator roles; each switch adds a history row. Not here: keyops alone holding CreateKey and the replica decrypt (AWS: Terraform, the SCP and KMS in two regions); AI pause before any provider call is the `ai_gateway` boundary's (DEC-338). |

## QD-3: the superseded list

Recorded at the S6 Contract Monday (Mon Jan 11, 2027; pulled forward to 2026-10-23 with Q-03-T002). The eleven tasks above marked `superseded` are not back-filled on their old code paths, because a later epic rebuilds them against the migrated contracts; each closes when that epic's AC suite merges. The four whose replacement lands after M8 (023, 053, 061, 063) get black-box suites on their legacy paths by M8 (T524, T525), retired only when the replacing suite merges.

## Spec drift found by the back-fill

| TASK | AC | The spec says | The current contract says | Superseded by |
|---|---|---|---|---|
| 030 | SPEC-015 §4, §7 | client roles are `engagement_members` rows | a client's role is a `client_access_grants` row; `engagement_members` is staff only | F-03-T26, DEC-129, ADR-146 |
| 030 | SPEC-015 AC-1 | `client_invitation.created` is audited and emitted | audited as `client_invitation.created`, emitted as `client_invitation.issued` | identity README (communications subscribes to it) |
| 030 | SPEC-015 AC-1, AC-9 | partners and managers invite and manage contacts | `client_service` may too (additive; not tested here) | F-03-T30, ADR-147 |
| 040 | SPEC-024 §4, AC-6 | four engagement types (`audit`, `review`, `compilation`, `agreed_upon_procedures`) | C1 v1's 14 types, `fs_audit` for `audit` | DEC-122, F-03 |
| 041 | SPEC-024 AC-3, AC-4 | three firm roles | four: `security_admin` added (ED-009, fixed by TASK-1015) | ADR P-10, DEC-21 |
| 040 | SPEC-024 AC-1 | a second attempt is "refused"; sign-up is "rate-limited" | 409 `signup_code_invalid`, `signup_already_staff`, `signup_rate_limited`; 422 `signup_invalid` | `docs/architecture/error-codes.yaml` |
| 044 | SPEC-025 Q4 | the letter warns and does not block | G3 is strict (ED-010, fixed) | DEC-39 (b) |
| 044 | SPEC-025 AC-9 | the roll-forward wizard's states | belongs to TASK-048's suite | Q-03-T023 (S8) |
| 050 | SPEC-027 §14 | automatic actions audited with actor kind `agent`, policy and version | one `agent.activity` row by the system actor on the engagement; policy and version on the feed row | TASK-050 D2 |
| 051 | SPEC-027 AC-3, §4.6 | Routine sends; feed outcome `drafted` | the agent drafts at every level and a person sends; outcomes done, skipped, failed | DEC-74, DEC-220 |
| Q-01-T37 | platform-ops §3.7 `read_only` | non-GET routes refused except sign-in, support-session and operational routes | also open in read-only mode: ending a person's access and revoking an invitation (`/v1/firm/staff/{user_id}/revoke`, `/v1/firm/staff/invitations/{invitation_id}/revoke`), and reads sent as POST | Resolved 2026-10-27: §3.7 now lists every exemption, with why (DEC-338) |
| 058 | SPEC-030 §6.3 | invalid output ends the run `failed` | the run escalates after its repair attempt; no review is recorded | ADR-048 |
| 059 | SPEC-030 §8 | `…/request-items/{item}/uploads/{version}/review` under `evidence.read` | `…/evidence-versions/{version}/review` under `upload_review.read` | TASK-059 D1 |
| 058 | Q-03-T032 acceptance | an unverified output "reads Uncited" | a flag with no verified quote is never shown; shown flags list verified quotes only | SPEC-030 Q3 |
| 066 | SPEC-033 AC-5 | `inbox_match.read` for firm roles with independence | a pending member reads by default; `g2_blocks_view` restores the gate on an attest client's engagement | ADR-164 items 2 and 3 (P-07-T24) |
| 066 | SPEC-033 §6 | firm reads at `GET …/inbox/matches` | `GET …/inbox-matches` | TASK-066 decision table |
| 065 | SPEC-033 §4.2 | prompt `evidence.inbox_match@v1` | agent spec `evidence.matcher` v2, prompt `@v2` | TASK-067 |
| 064 | SPEC-033 AC-6 | the audit records which suggestion source and rank | integers: `file_name` 1, `content` 2, `matcher` 3 | TASK-064 D5, TASK-066 §7 |
