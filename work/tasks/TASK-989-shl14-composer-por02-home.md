---
id: TASK-989
title: SHL-14 request composer drawer a, b, e, f with R2 items 1–5, and POR-02 portal home part 1 a, b, c, f (P-06-T13, P-08-T15)
spec: SPEC-321
acceptance_criteria: [AC-1]
risk_zone: green
status: done
epic: P-06
plan_key: P-06-T13; P-08-T15
branch: s6-shl14-por02
created: 2026-10-23
updated: 2026-10-23
---

## Objective
P-06-T13 and P-08-T15 in one change. SHL-14 as the O2 drawer over BND-02, opened through
`?ov=request:…`, on the C5 request lifecycle (create, v2 PATCH, delegate, send with an
Idempotency-Key); POR-02's portal home part 1 on T7 over `GET /v1/portal/home`, white-labelled.

Acceptance (P-06-T13): "A Draft never offers Save & send without a due date and Approve & send
records the person as sender." Acceptance (P-08-T15): "Scenario tests for a, b, c and f pass,
planned targets render only in fixture builds, and no red appears except on a past-due item."

## What changed
- **SHL-14** `apps/web/src/screens/SHL-14/` and `domain/requests/composer.ts`: the drawer (480)
  with the R2 tabs row (Details · Comments · Activity), the Draft pill, the cards "Document
  request" (Request, Category, Description, Due, Wave), "People" (Client assignee, Request from a
  third party with the delegate picker and its help line, Firm owner, Visibility Owners only ·
  Client with "Becomes Client when sent", Reminders), "Links" (Supports, Related rows, Controls,
  Attachments; "Link from another engagement…" hidden, DV-6), the client preview from the
  binder's client projection, and the footer ("Adds 1 request · Source Documents will read 11 of
  25 received", Save draft, Save & send / Save & send to ‹third party› / Approve & send to
  ‹assignee›). Save creates with the live body, patches the v2 fields, delegates, then sends; the
  422 `due_date_required` and 409 `model_text_not_permitted` are said in the footer. The dirty
  guard is the drawer's. Registered as the `request` overlay in `routes/firm/binders.tsx` (its own
  chunk); BND-02's "+ Request" and row "Edit" open it.
- **POR-02** `apps/web/src/screens/POR-02/` and `domain/portal/home.ts`: the rail (household card,
  team rows with their client-facing labels; Recent messages and "Account & people" only in
  fixture builds), the greeting and date on `useNow`, to-do cards from the kind registry (first
  visit cards read the request in full), the work card with its StageTracker (ordered list,
  `aria-current="step"`, disc labels) and note, the Documents binder card, the Earlier list, the
  welcome card whose dismissal PUTs the preference, the all-set card, and its own skeleton and
  error (the kit's ViewState module carries the firm's product words, which the portal bundle
  must not hold). The portal route renders it for Home.
- **Fixtures** `fixtures/scenarios/SHL-14.ts` (a, b, e, f over the seed's own Northwind and
  Granite Peak request lists); the portal handlers answer `PUT /v1/portal/preferences`.
- **Gallery and e2e** both screens registered; `e2e/screens/SHL-14.spec.ts` and `POR-02.spec.ts`
  run every scenario with axe (POR-02 also asserts no product name).
- **Contracts** `docs/screens/SHL-14.md`, `docs/screens/POR-02.md`; decision DEC-196.

## Not built, and why
- SHL-14 c (A-03) and d (P-06-T24), as the contract records.
- POR-02 d, e, g, h and M are P-08-T23's.
- The fields the C5 contract cannot yet read back for one request (period, wave, firm owner,
  linked workpaper, supports, the delegate, the drafted wording source) and the client wording of
  a request that is not yet in the binder's client projection: listed as gaps in
  `docs/screens/SHL-14.md`.

## Progress log
- 2026-10-23: built and tested; vitest, typecheck, lint, Playwright with axe for every scenario,
  the portal build (budget and the no-product-name check), `make check-fast`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-196 | SHL-14's overlay args and the C5 read gaps; POR-02's own skeleton and the preference version | no |
