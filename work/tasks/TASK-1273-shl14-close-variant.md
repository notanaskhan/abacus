---
id: TASK-1273
title: SHL-14 d close variant on close_intake binders, hosted from BND-02 until CLS-03 (P-06-T24)
spec: SPEC-321
acceptance_criteria: [AC-1]
risk_zone: green
status: done
epic: P-06
plan_key: P-06-T24
branch: s9b-kit-screens
created: 2026-10-26
updated: 2026-10-26
---

## Objective
P-06-T24: "Raj marks the Square payouts upload Incorporated and the pill turns green." SHL-14's
state d (deferred in TASK-989): the request composer opened on an existing request of a
`close_intake` binder reads as the close variant, "Document Request" and "Uploaded Document",
with "Mark incorporated" and "Return…" in the footer.

## Scope
**In**
- `apps/web/src/domain/requests/composer.ts`: `useIncorporate()` over the generated
  `incorporateRequestItemMutation` (`POST …/request-items/{id}/incorporate`), refreshing every read.
- `apps/web/src/screens/SHL-14/index.tsx`, `copy.ts`: the close variant when
  `binder.kind === "close_intake"` and the request is not a draft. Rows: Request, Category,
  Visibility (R2 item 3: Client), Requested by (the `request_item.sent` actor and
  `requested_at`); Status (`RegistryStatus request_close`), File and Uploaded by from the latest
  upload. "Mark incorporated" while `pending_incorporation` and the row allows
  `request_item.update`; "Return…" opens the shared `ReturnDialog` on the upload
  (`decision/send-back`, `evidence.reject`).
- `apps/web/src/fixtures/scenarios/SHL-14.ts`: scenario d (raj-malhotra, Sep 14 9:41 AM CT) on
  Copperleaf's August close binder built from the backend seed's `CLOSE_REQUESTS` (P-06-T08:
  "Requests", 9 requests, 7 received, five categories, the seed's ids); the uploads, incorporate,
  reason-code and send-back handlers.
- Tests in `screens/SHL-14/SHL-14.test.tsx`; `e2e/screens/SHL-14.spec.ts` lists d.
- `docs/screens/SHL-14.md`: d built, DV-T24-1 to 3, G-6.

**Out**
- The document title, Type and Summary (G-6: not in the C5 upload read).
- CLS-03 as the host (C-01).

## Definition of done
- [x] SHL-14 vitest 16 (5 new); BND-02 and gallery suites still pass
- [x] tsc (no new errors), eslint and prettier on touched files
- [ ] Playwright not run locally: v1.63 wants chromium 1243, only 1248 is cached

## Rollback
Revert the commit; no migrations, no generated files, no flags.

## Progress log
- 2026-10-26: built and tested. tsc for `apps/web` reports only the existing errors inside the
  generated `packages/api-client/src/{client,core}` files under exactOptionalPropertyTypes;
  nothing in the touched files.
- 2026-10-26: those errors came from the api-client's unbuilt type output in a fresh worktree;
  after `pnpm -C packages/api-client build:types`, `tsc --noEmit` for `apps/web` exits 0.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-385 | SHL-14 d as built: close_intake host, seed names over the board's, G-6 upload-read gap | no |
