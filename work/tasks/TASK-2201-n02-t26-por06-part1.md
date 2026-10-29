---
id: TASK-2201
title: N-02-T26 POR-06 part 1 on T16 in fixture mode
spec: SPEC-381
acceptance_criteria: [AC-10, AC-11, AC-12]
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T26
branch: s17-n02-t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s17
created: 2026-10-29
updated: 2026-10-29
---

## Objective
POR-06 part 1 on the T16 kit in fixture mode: the portal's `/sign` list and `/sign/$envelopeId`
review (Continue waits for the last page), the ERSD consent handing over to the provider's view
(iframe or redirect), the return route with the pending state and the completion card, decline
with reasons and withdraw, the restricted state and 390.

Acceptance: "Scenario tests for a, b, c and g pass at 1400 and 390, and Completed never renders
from a return parameter alone."

## Scope
**In**
- `apps/web/src/screens/POR-06/` (screen, copy, scenarios, tests); `domain/signing/portal.ts`.
- `fixtures/seed/portal-envelopes.ts`, `fixtures/handlers/portal-envelopes.ts`, `fixtures/scenarios/POR-06.ts`.
- Portal routes `/sign`, `/sign/$envelopeId`, `/sign/$envelopeId/return`; gallery registration.
- Additive T16 kit props (`action`, `onPageSeen`, `onNavigate`), viewer completion, provider view
  at the sign step and on the phone (DEC-1251).

**Out**
- Live C7 routes (N-02-T23), KBA and joint filers (T25, T27), dated letters (T31), the Playwright
  walk and Tier C lock (T43), C7 v1.1 fields (T25).

## Context to load
- `docs/screens/POR-06.md`; handoff `POR-06 Sign - Ridgeline engagement letter/`
- `docs/contracts/c7-envelopes.md` §2, §6; `apps/web/src/domain/signing/envelope-vm.ts`
- Pattern: `apps/web/src/screens/POR-14/`, `fixtures/scenarios/POR-14.ts`

## Plan
1. [x] Seed and stateful handlers for Owen's E13 and the signed band.
2. [x] Scenarios a, b, c, pending, g, restricted, list.
3. [x] Domain hooks: list, view (polls after a return), return, page blobs, writes.
4. [x] Screen over the kit; kit additions; routes; gallery.
5. [x] Tests: `POR-06.test.tsx` (a, b, c, g at 1400 and 390; pending; restricted; list),
       kit tests for the additions.
6. [ ] End review: run the suites, axe in the gallery.

Tests to write (mapped to ACs):
- AC-10 → `test_ac10_a_*` · AC-11 → `test_ac11_b_*` · AC-12 → `test_ac12_c_*`, `test_ac12_a_return_parameter_alone_never_renders_completed`, `test_ac12_g_*`

## Progress log
- `2026-10-29` — Built steps 1–5 on `s17-n02-t26` (build-only; tests run at the S17 end review).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1251 (kit props, review gate, ERSD step, return polling, blob pages, new words) | POR-06 needs a container slot the kit lacked; C7 v1 lacks signer names and evidence | no |

## Gotchas and discoveries
- The kit's phone layout never drew the provider's view; fixed here.
- `<img>` can't send the portal bearer token: page images go through the SDK as blobs.

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review: vitest for the screen and kit, typecheck, lint.
