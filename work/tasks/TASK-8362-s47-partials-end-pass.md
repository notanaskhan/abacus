---
id: TASK-8362
title: "S47-end-pass: End pass for the S47 partials stack: gates, targeted suites, fixes and the security read"
spec: SPEC-655
acceptance_criteria: [AC-50, AC-51]
risk_zone: red
status: in-review
branch: s47-partials-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: S47-end-pass
---

## Objective
Spec section: S47 partials end pass (#2155 to #2177). End pass for the S47 partials stack: gates, targeted suites, fixes and the security read.

## Plan (red)
1. make check-fast; schema_check; targeted pytest (-n 4, the touched modules' unit, contract, security and integration suites); full vitest; the TXT Playwright runs (TASK-8361).
2. Fixes: 501 kept on 25 newly implemented routes (the convention); error-codes.yaml regenerated; `register_work_classes` for IntegrationHealthWorkflow; an empty `detail_copy` equals none in the catalogue import (identical imports wrote); the fieldwork kit leaves the `domain/audits` barrel for `domain/fieldwork` (three audit chunks were over 140 KB); the confirmations stub test passes a Request.
3. Reviewed lists: notification kinds (6), the worker's subscriptions (`confirmation.link_requested`), APP_UPDATE_COLUMNS (`confirmation_authorizations`), TAX-04's review routes (TXT-03, TXT-04); A-06-T17's posting rule names the one exception 0896 allows (eliminations on the consolidation layer) and pins its CHECK; the expansion test asserts named keys (DEC-5327); the client-access test uses a truly unknown scope kind (A-09-T21 registered `component`).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. check-fast green (backend and frontend, bundle budgets 127 met); schema_check green; pytest 64,642 + rerun of the failed set 38,972 passed; vitest 4,280 passed; Playwright fixture 11 passed. Security read of the red diffs: the confirm routes never 401 (no token in a sign-in return_to); attachments only the link's own; respondent text rendered as text; IP sealed; pull-all synthetic only; the OAuth callback's idempotency key is random (never the state); the estate header asks authorise per action. No finding left open. Not run: the full unit and integration suites (targeted only), staging. Gates and
  tests run once at the S47 end pass (build first, test last).
