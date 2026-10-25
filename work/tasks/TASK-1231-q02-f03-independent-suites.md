---
id: TASK-1231
title: Independent AC suites for classification flags and the gateway PII refusal, the provider-terms register, and binders and the request enum (Q-02-T52; F-03-T21)
spec: SPEC-047
acceptance_criteria: [AC-5, AC-7]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T52; F-03-T21
branch: s8b-accept-tests
test_author: ayushkbhatia
test_session: 2026-10-25, branch s8b-accept-tests (one clean session per suite, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-25
updated: 2026-10-25
---

## Objective
- **Q-02-T52:** "The suite fails against seeded violations (a tri, phi or pii_kind flag on a non-restricted field, an unmasked TIN in a log line, Sentry event and metric attribute, an unmasked SSN in model context reaching the network stub, a register entry compiling without counsel's approval) and passes unedited on T32 and T18."
- **F-03-T21:** "Each 9.5.6 bridge row is a test case and the screening suite stays at its protected thresholds."

## Plan (red zone)
- **Files (tests only):** `backend/tests/security/test_classification_scrubbing.py` and `backend/tests/unit/tools/test_q02t52_provider_terms_register.py` (Q-02-T52); `backend/tests/unit/requests/test_f03t21_request_enum_rules.py` and `backend/tests/integration/backfill/test_f03t21_binders_request_enum.py` (F-03-T21). The tranche-0 tests stay as they are.
- **Production:** none. **Decision:** DEC-355 (derived overdue).
- **Rollback:** revert the commit.

## Results
- **Q-02-T52, T32 part (49 pass):** AC-19 (a `tri`, `phi` or `pii_kind` flag below Restricted fails at import, 3 levels x 3 flags; a hand-set flag is caught; the schema carries `cls` and `x-pii-kind`; nested and list paths found); AC-20 and AC-21 (a log line, a Sentry event and a metric attribute from a tagged model are masked); AC-22 (SSN, ITIN, EIN and bare digits in each of 5 context parts are refused before the network stub, audited once without the value, never retried; masked forms reach the stub).
- **Q-02-T52, T18 part (6 pass, 2 strict xfail):** the drift check and `review_by` pass. The two counsel-approval tests are held: **Q-02-T18 is not built on main** (a founder-only entry validates and compiles, `abacus_tools/codegen/provider_terms.py`). Not an escaped defect: the row is unbuilt. When T18 lands, `tests/unit/tools/test_client_data_clearance.py::test_adr114_a_complete_entry_is_accepted` will need its fixture to carry counsel's approval.
- **F-03-T21 (unit 18 pass; integration 34 pass):** the §9.5.6 bridge parametrised, one case per row (6), on its own database (head, down to 0070, seeded with the old codes, up one step); the six codes store and the old codes and `overdue` are refused; binders 1:n (a duplicate is the next part) and the five binder statuses; a draft is never in a client's list; overdue derived and never stored (DEC-355); follow-up tables, routes and actions, REQ-002 and L12 planted-literal checks; the screening thresholds and prompt `evidence.screen@v0` unchanged.

## Spec drift and gaps
- **Overdue (DEC-355):** F-03 Story 3.1 makes every status but `received` and `not_applicable` overdue once past due; AUD-03 g, SPEC-027 AC-3, C5's follow-ups and portal-pbc (`uploaded` reads "Done") make it what the client still owes. Decided for the latter; the test follows DEC-355. Main reports `uploaded` past due as not overdue, consistent with it.
- F-03-T16 says no route is named reminder; the later P-07 contract adds `POST /v1/engagements/{engagement_id}/independence/reminders`, allowed by name.
- L12 does not flag compounds such as `send_reminder` (the glossary itself uses `max_reminders`); the tests plant the bare word and the legacy table names.
- §9.5.6 keeps `ready_for_review_at`, but no such column exists before the bridge; whether a past-due `draft` is overdue is not said, so it is untested.

## Progress log
- 2026-10-25: suites written; no escaped defect; DEC-355 recorded; T18's two tests held for the unbuilt row.
