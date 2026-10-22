---
id: TASK-432
title: C5 v1.1 portal-half consumer contract tests - pytest in backend/tests/contracts/c5_portal/ and TS fixture assertions typed against packages/api-client (P-08-T02)
spec: SPEC-320
acceptance_criteria: [AC-6, AC-7, AC-15, AC-16]
risk_zone: amber
status: done
epic: P-08
plan_key: P-08-T02
branch: p08-t02-c5-portal-tests
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The suite runs in the provider's CI against the stub and fails if any home field carries a firm status code, an amount or an agent reference."

## Plan (amber zone)
- **Files:** `backend/tests/contracts/c5_portal/test_c5_portal_consumers.py` (new); `apps/web/src/fixtures/contracts/portal.contract.test.ts` (new; the plan's path).
- **Shapes covered (contract `docs/contracts/portal-identity.md`):** the no-enumeration shape of start and renew (every field required or constant; nothing says whether an account exists) and preview (no failure reason, one 404); `tries_left`, `locked_until` and `resend_available_at` as identifier-only facts documented beside their codes, the lock for an email that matches no one; codes, tokens and secrets Restricted; the home DTO walked through every schema it reaches: no C2 status enum, no `status` field, no firm status code outside a named list of coincident client stage words, no amount (by name or number type), no agent reference; every to-do target a portal manifest screen; preferences versioned per scope; branding Public only, the same shape for an unknown host, no tenant, same-origin logo; no "Accrued" in any portal-half schema or shape; the shell's landings and no bell; the unlock answer in the `invitation` words; recovery by a named firm person, reset with fresh MFA; `/v1/me.mfa` never the factor.
- **TS:** fixtures for POR-02 a, d, e, preferences, `/v1/me` portal and mfa, unlock and MFA reset, typed with the generated client and checked against `openapi.json`; a type-level deep-key check that no home field is a status, amount or agent field; run-time refusals of the same.
- **Not covered in TS:** the sign-in, renew, preview and branding shapes are not served (DEC-139), so they have no generated type; their pytest half covers them.
- **Migrations, flags, matrix:** none.
- **Rollback:** delete the two test files.

## Progress log
- 2026-10-23: built on `origin/main` at 4ba20fb (after TASK-431). `tests/contracts/c5_portal` 144 passed; `vitest run src/fixtures/contracts` 48 passed; `tsc --noEmit`, eslint, prettier, ruff, pyright clean. Checked the type-level deep-key check catches a nested `*_status` key (scratch file, removed).
