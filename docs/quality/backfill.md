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
| 029 | red | Firm-level reads for engagement roles | SPEC-014 | S0–S3 | T059; T021 (S8) | tranche 0 | `tests/integration/backfill/test_firm_level_reads.py`; extended to the P-06 scope kinds by T021 |
| 027 | red | Break-glass support access | SPEC-012 | S0–S3 | T059 | tranche 0 | re-run at S12 |
| 020 | amber | Evaluation runner, graders and calibration | SPEC-005 | S0–S3 | T059 | tranche 0 | re-run at S12 |
| 041 | red | People and firm roles | SPEC-024 | S6 | T006 | back-filled | `backfill/test_staff_people.py`; AC-8 `apps/web/src/legacy/spec024states.test.tsx` (TASK-992) |
| 045 | red | Per-person independence gate | SPEC-025 | S6 | T006 | back-filled | `backfill/test_independence_gate.py` (TASK-992) |
| 030 | red | Client invitations and client users | SPEC-015 | S6 | T007 | back-filled | `backfill/test_client_invitations.py` (TASK-992) |
| 032 | red | Engagement team management | SPEC-017 | S6 | T007 | back-filled | `backfill/test_team_management.py`; AC-7 `apps/web/src/legacy/spec017people.test.tsx` (TASK-992) |
| 040 | red | Self-serve sign-up and engagement types | SPEC-024 | S6 | T008 | back-filled | `backfill/test_signup_and_engagement_types.py`; AC-8 `legacy/spec024states.test.tsx` (TASK-992) |
| 044 | red | Acceptance, independence, letter and the engagement gate | SPEC-025 | S6 | T008 | back-filled | `backfill/test_acceptance_independence_letter.py`, `test_independence_gate.py`; AC-9 `legacy/spec025states.test.tsx` (TASK-992) |
| 035 | red | Client portal, item visibility and client uploads | SPEC-020 | S7 | T014 | scheduled | |
| 056 | red | Upload processing, part 3: previews | SPEC-029 | S7 | T014 | scheduled | |
| 054 | red | Upload processing, part 1: scanning, workflow, extraction | SPEC-029 | S7 | T015 | scheduled | |
| 055 | red | Upload processing, part 2: kinds and mechanical checks | SPEC-029 | S7 | T015 | scheduled | |
| 036 | red | Client connection flow, health, access log, revoke | SPEC-020 | S8 | T022 | scheduled | |
| 052 | red | Ledger file import, part 1 | SPEC-028 | S8 | T022 | scheduled | |
| 069 | red | GL detail, part 1: isolated parsing, immutable snapshots | SPEC-034 | S8 | T023 | scheduled | |
| 048 | red | Roll forward from last year's engagement | SPEC-025 | S8 | T023 | scheduled | |
| 038 | amber | Classification, automatic retrieval, evidence board | SPEC-022 | S8 | T024 | scheduled | |
| 068 | amber | Ledger file import, part 3: TB exports | SPEC-028 | S8 | T024 | scheduled | |
| 070 | amber | GL detail, part 2: workbooks and upload screens | SPEC-034 | S8 | T024 | scheduled | |
| 071 | amber | GL detail, part 3: GL exports | SPEC-034 | S8 | T024 | scheduled | |
| 050 | red | Engagement agent v1, part 1 | SPEC-027 | S9 | T031 | scheduled | |
| 051 | red | Engagement agent v1, part 2: due dates, reminders, digest | SPEC-027 | S9 | T031 | scheduled | AC-3 to AC-5, AC-8, AC-9 already on `main`: `tests/integration/backfill/test_follow_ups_and_due_dates.py`, `test_due_dates_and_delegation.py` |
| 058 | red | Upload reviewer, part 1 | SPEC-030 | S9 | T032 | scheduled | |
| 059 | red | Upload reviewer, part 2 | SPEC-030 | S9 | T032 | scheduled | |
| 065 | red | Content matching, part 2: the matcher agent | SPEC-033 | S9 | T033 | scheduled | |
| 066 | red | Content matching, part 3: Suggest with AI | SPEC-033 | S9 | T033 | scheduled | |
| 064 | amber | Content matching, part 1: code suggestions | SPEC-033 | S9 | T033 | scheduled | |
| 062 | red | Comments, part 1 (backend) | SPEC-032 | S10 | T039 | scheduled | |
| 072 | red | Drafted guidance, part 1 | SPEC-035 | S10 | T039 | scheduled | |
| 073 | red | Drafted guidance, part 2 | SPEC-035 | S10 | T040 | scheduled | |
| 074 | red | Drafted guidance, part 3 | SPEC-035 | S10 | T040 | scheduled | |
| 033 | amber | Request list import from Excel | SPEC-018 | S11 | T047 | scheduled | |
| 037 | amber | Request item detail | SPEC-021 | S11 | T047 | scheduled | |
| 039 | amber | Uploads on the client's behalf, inbox, matching | SPEC-023 | S11 | T047 | scheduled | |
| 060 | amber | Client hub, part 1 (backend) | SPEC-031 | S11 | T047 | scheduled | |
| 024 | red | Knowledge retrieval infrastructure | SPEC-009 | S11 | T048 | scheduled | |
| 026 | amber | Feature flag registry | SPEC-011 | S11 | T050 | scheduled | |
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
| scheduled | 29 |
| back-filled | 6 |
| superseded | 11 |
| **Total** | **55** |

M8 (Fri May 28, 2027) needs 44 back-filled (tranche 0 included) and 11 superseded, each with an independent AC suite (Q-03 §3.2 B3).

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
| 044 | SPEC-025 Q4 | the letter warns and does not block | G3 is strict (held by ED-010) | DEC-39 (b) |
| 044 | SPEC-025 AC-9 | the roll-forward wizard's states | belongs to TASK-048's suite | Q-03-T023 (S8) |
