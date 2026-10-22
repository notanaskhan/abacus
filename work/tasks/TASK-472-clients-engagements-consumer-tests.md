---
id: TASK-472
title: Consumer contract tests for the clients v1 and engagements v2 stubs - pytest suites and TypeScript fixture assertions (P-07-T06)
spec: SPEC-321
acceptance_criteria: [AC-20, AC-21, AC-22, AC-23, AC-24, AC-25]
risk_zone: amber
status: done
epic: P-07
plan_key: P-07-T06
branch: p07-t06-consumer-tests
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The suites run in notanaskhan's CI against the stubs and fail on any hidden_by_wall field or plaintext TIN field."

## Plan (amber zone)
- **Files:** `backend/tests/contracts/clients/test_clients_consumer.py`, `backend/tests/contracts/engagements_v2/test_engagements_v2_consumer.py`, `apps/web/src/fixtures/contracts/clients-engagements.test.ts`; SPEC-321 Story 5; the two contract docs' §9.
- **Migrations, registry, flags:** none. Tests only; no production code.
- **Tests:** AC-20 to AC-22 (clients), AC-23 to AC-25 (engagements). The engagements suite loads F-02-T11's `c1_work_items/test_c1_consumer.py` by path for `EXCLUDED` and its C1 enum check.
- **Rollback:** delete the three test files.

## What changed
- **Clients (pytest):** the P-36 envelope with an exact `total`, CLI-01/CLI-02 fields, a scan of every OpenAPI schema for a hidden/walled field (DEC-43), a scan for TIN-named fields that are not `MaskedTinOut` by reference, the masked shape (four Restricted digits), no Restricted field in the row, the plain value only in `TinRevealOut` on the reveal route, and `ClientStatus`/`InvitationStatus` equal to the vocabulary's codes.
- **Engagements (pytest):** the envelope plus the summary, tiles equal to the `engagement` codes, `letter_record` codes, ENG-01 columns, the record's bands and `read_only_reason`, G1–G9 gates with object-ref blockers, F-02-T11 reused, no `single_audit` in the 18 catalogue codes, a draft `type_code` that is a code string, so the refusal is the catalogue's 422 `unknown_engagement_type`, and create's 409/422.
- **TypeScript:** typed frames for CLI-01 a/c, CLI-02 a (EIN `0287`), the reveal, ENG-01 b, ENG-02 b gates, the 18-card catalogue (8 · 8 · 2) and a `single_audit` draft. Compile-time checks: no TIN key on the row, no wall key on either envelope, no `single_audit` in the catalogue code union. Each frame is validated at run time against the OpenAPI document, and unknown fields (`hidden_by_wall`, a `tin` on the row, a `value` on the masked shape) are rejected.

## Progress log
- 2026-10-23: built on origin/main at ca5e76e. The pytest suites pass (clients and engagements_v2 contracts, 1142 cases with the per-schema scans). vitest 7 passed; tsc, eslint and prettier are clean. `schema-check.ts` does not check `pattern`, so the four-digit rule is held by the pytest half.
