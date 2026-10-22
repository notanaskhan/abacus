---
id: TASK-420
title: C5 consumer contract tests (pytest + TS fixture assertions) for A-01, R-01, T-02, C-01 (P-06-T02)
spec: SPEC-319
acceptance_criteria: [AC-2, AC-3, AC-7, AC-12]
risk_zone: amber
status: done
epic: P-06
plan_key: P-06-T02
branch: p06-t02-c5-consumer-tests
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Run in N's CI; assert shapes, draft invisibility to client principals, client words and the 9.5.6 codes; C5 freezes Dec 11." The consumers' half of C5 v1, on top of the provider stub test (`test_c5_stub.py`, P-06-T01), so the freeze on Fri 2026-12-11 has the four consumers' expectations written down.

## Plan (amber zone)
- **Files:** four pytest modules, one per consumer, in `backend/tests/contracts/c5_requests_binders/` (`test_c5_consumer_a01.py`, `_r01.py`, `_t02.py`, `_c01.py`); one vitest file `apps/web/src/fixtures/contracts/c5.test.ts` next to the existing fixture contracts. No product code, no generated file, no registry, flag or migration change.
- **Approach:** the routes are 501 stubs, so the tests read the published contract: the OpenAPI document (`abacus.api.export_openapi.document`), the compiled permission matrix (`RULES`), the status registry (`docs/product/status-vocabulary.yaml`), the error-code catalogue, the client read filter (`visible_items`, compiled to SQL) and the request-status trigger of migration 0071. The TS half types fixtures with the generated client (a breaking change fails `tsc`) and checks them against `openapi.json` at run time (`validateSchema`).
- **Not duplicated:** route-to-action, 404/501, Idempotency-Key, C2 `$ref`s and the action-level human-only denies are the stub test's. These tests go by operation and by consumer.
- **Defects:** where a test shows the contract disagrees with itself, it stays and is `xfail(strict=True)` with this task and an issue-style reference in the reason (SKIP-001).
- **Not here:** freezing the snapshot (`backend/tests/contracts/c5_requests_binders/v1.json` is written by the freeze on Dec 11, `abacus_tools.contracts.freeze`).
- **Rollback:** delete the five test files.

## What changed
Tests per consumer (pytest; the parametrised cases in brackets):

| Consumer | Module | Tests | Covers |
|---|---|---|---|
| A-01 (AUD-03, BND-02, SHL-14) | `test_c5_consumer_a01.py` | 16 (61 cases, 1 xfail) | BND-02 record, rows, SHL-14 record and composer bodies (required vs optional, closed bodies, enums), live poll and activity (identifiers only), classification of every field (contract §3), the §9.5.6 bridge row by row, overdue derived, the uploaded screening sub-states, per-operation documented statuses for the §6 codes, catalogue status agreement, the kernel's `idempotency_key_reused`, 16 human-only operations deny the agent, the agent reads only in task scope |
| R-01 (POR-03/04/14/20) | `test_c5_consumer_r01.py` | 20 (38 cases, 2 xfail) | each client route answers its portal shape; no client shape carries a draft-only or firm-only field (walked through nested models); the preview item; draft invisibility (a draft has no client word, client roles read only `client_visible_only` / `assigned_only`, no client role on activity or edits, every client reach of the compiled request filter needs `client_visible`, migration 0071 keeps every draft off the client); the client words To do · Done · Returned · Ignored; ignore takes SPEC-042's reasons and keeps the status; mark-done, upload intents, withdrawal, follow-up cadence bounds; the agent never acts for the client; §6 codes |
| T-02 (tax) | `test_c5_consumer_t02.py` | 11 (18 cases) | `firm_provided` items, `linked_ref` to a K-1 package (In and Out agree, closed), the prior-year binder and tag, the close rule as a code, binder statuses are the registry's, part n, the BND-01 season filters and envelope, human-only operations deny the agent and every client role |
| C-01 (close, CLS-03) | `test_c5_consumer_c01.py` | 8 (12 cases) | `close_intake` binders, incorporation states are the `request_close` registry codes, terminal flags, who incorporated and when, periods, the CLS-03 glyph, the incorporate route and its matrix row |
| all four (TS) | `apps/web/src/fixtures/contracts/c5.test.ts` | 12 | typed fixtures from the contract's §8 examples (BND-01 page, BND-02 record, an agent-drafted request, the client preview, the portal answers, a K-1 item, a close-intake item) validated against `openapi.json`; tiles foot to the total; `EnumCovered` for binder, request and screening; the 9.5.6 firm words and the client words; `ClientSafe<T>` type-level proof that no client shape has a firm-only key (and that the firm record does); IgnoreIn's reasons equal SPEC-042's |

## Findings (contract defects; tests kept, `xfail(strict=True)`)
1. **409 bodies with facts are untyped.** C5 §6 and ADR-139 answer `{"detail": "binder_gate_unmet", "facts": {"gate": "G3"}}`, but `identity/routing.py` documents every 409 as `ErrorOut {detail}`; the generated client cannot read `facts` (the BND-02 publish bar needs the gate). Test: `test_a01_the_documented_409_body_carries_identifier_facts`. Fix: add `facts: dict[str, str | int] | None` to `ErrorOut` (or a `CodedErrorOut` for 409/403), `make generate`.
2. **Domain 422s do not match their documented schema.** `abacus.api.app._domain_invalid` answers `{"detail": "<code>", "facts": …}` (`due_date_required`, `reason_required`, `idempotency_key_reused`), while every 422 is documented as `ValidationErrorOut` whose `detail` is a list of field errors. Test: `test_r01_the_documented_422_admits_a_domain_code`. Fix: document 422 as `ValidationErrorOut | CodedErrorOut`.
3. **Client-visible drafts would reach clients.** C5 §1, P-06 §4.3 and SPEC-319 AC-6 have publish "send draft client-visible requests", so a draft may be client-visible; but `visible_items` admits a client on `client_visible` alone, and migration 0071's trigger today makes a client-visible request `requested` (no client-visible draft can exist). Draft invisibility holds now only through that trigger. When P-06-T05/T10 allow a client-visible draft, the client filter must also exclude `status = 'draft'`. Test: `test_r01_the_client_filter_excludes_drafts_by_status_too`.

The xfail reasons carry this task's PR number as the issue reference (SKIP-001 wants `#n`; no GitHub issues were opened, per the brief). They pass strictly once fixed and must then become plain assertions.

## Progress log
- 2026-10-22: built on `origin/main` at 5a3bf63 (the C5 stub, PR #279). pytest `tests/contracts/c5_requests_binders/` 174 passed, 3 xfailed (stub 48 + consumers). vitest `src/fixtures/contracts/c5.test.ts` 12 passed. ruff format and check, pyright: clean on the new modules. prettier, eslint: clean on the new file; `tsc --noEmit` reports nothing in it (24 errors elsewhere, in `packages/api-client/src/core/*.gen.ts` and `packages/ui/src/status.ts`, not from this change). `banned_patterns`, `validate_docs`: clean. Full suites not run (S3 batch rule).

## Gotchas and discoveries
- `abacus_tools.quality.error_codes.collect()` builds the app but never imports `kernel/uow/idempotency.py`, so `idempotency_key_reused` (a `DomainInvalid`) is not in `error-codes.yaml` yet. It will be once a route uses the replay store (P-06-T07, T10); the A-01 test checks the class directly meanwhile.
- The legacy web map `STATUS.clientRequest.not_applicable` reads "Doesn't apply" while the registry's client word is "Ignored". R-01 screens must use the registry (`status()`), not the TASK-101 map.
- `ruff format` left the en dash, middle dot and check mark literal in a test string and RUF001 then refused it; the A-01 module keeps them as `\u` escapes, as the C2 test does.
