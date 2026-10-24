---
id: TASK-1124
title: Consumer contract tests for the contacts and portal-access stub - shapes, counts header, delegated-requests footer (P-07-T18)
spec: SPEC-321
acceptance_criteria: [AC-26, AC-27, AC-28, AC-29]
risk_zone: amber
status: done
epic: P-07
plan_key: P-07-T18
branch: s7-p07-contacts
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The suite asserts the CLI-04 a counts and the 24-request footer against the stub" (P-07-T18).

## Plan (amber zone)
- SPEC-321 Story 6 (AC-26 to AC-29) for the consumer half of `docs/contracts/contacts-access.md`.
- `backend/tests/contracts/contacts_access/test_contacts_access_consumer.py`: the envelope, header and footer shapes from the OpenAPI document; CLI-04 a's frame (Northwind's six contacts) validated by `ContactsPage`, the header 3 · 1 · 2 summing to the rows and agreeing with `counts`, the footer 10 + 9 + 2 + 2 + 1 = 24 as the non-zero row counts in order, 11 received; grants' role and scope codes equal ADR-146's; expiry fixed at 14; no response of the contacts routes carries a token or link; no wall or Restricted field.
- `apps/web/src/fixtures/contracts/contacts-access.test.ts`: the same frames typed with the generated client (compile-time: no wall key, no token key, 14 days) and checked with `validateSchema`.
- No production code; the suite keeps holding when P-07-T25 makes the routes live.

## Progress log
- 2026-10-24: built; `uv run pytest tests/contracts/contacts_access` 49 passed; `pnpm -C apps/web vitest run src/fixtures/contracts src/status` 165 passed; `tsc --noEmit` clean.
