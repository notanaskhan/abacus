---
id: SPEC-323
title: "Portal PBC core (R-01, C5 section portal-pbc): documents, the request sheet, drops and the third-party room - outline"
status: draft
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-005, ADR-031, ADR-139, ADR-146, ADR-162, ADR-163]
related_specs: [SPEC-319, SPEC-320]
created: 2026-10-24
updated: 2026-10-24
---

> **Outline.** Written with R-01's first six rows (S7). The epic is the source until this spec is
> final: `docs/plan/epics/R-01.md` §3 (stories), §4 (backend), §5 (frontend), §8 (contracts). The
> contract is `docs/contracts/portal-pbc.md`; the screen contracts are `docs/screens/POR-03.md`,
> `POR-04.md`, `POR-14.md`, `POR-20.md` and `ADM-10.md`. AC-1 to AC-6 hold for the rows built
> here; the read models, writes and later screens (R-01-T07 onward) add theirs.

## 1. Summary
A client sees the binder the firm published in client words, drops files anywhere for a code-rule
sort that a named person confirms, ignores a request with a reason, withdraws an unaccepted upload
and marks the binder done, each with Undo until the firm acts. A third party sees only the requests
delegated to them. Nothing in the portal names the product, the agent, a confidence or a firm
status.

## 2. Problem and context
The legacy client engagement page (`ClientEngagement.tsx`) predates C5's binders and the portal
read models. POR-03, POR-04 and POR-14 replace it before Tue Mar 16, 2027 (P-08-T28).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Client person (taxpayer, owner, plan administrator, contributor) | Reads the binder, uploads, drops, ignores, withdraws, marks done |
| Third party (recordkeeper, custodian) | Reads and uploads to delegated requests only (R-01-T13) |
| Firm staff | Accept, return, void a rule fulfilment (human only) |
| Agent, system | Denied every client action; the code-rule sort runs as `system` on the dropper's behalf |

## 4. Goals and non-goals
**Goals:** the screen contracts, glossary rows, the C5 section `portal-pbc` stub, its consumer
tests, the fixtures, and POR-03 part 1 in fixture mode.

**Non-goals:** the live read models and writes (R-01-T07 to T09, T13); POR-04 and POR-14 screens
(T12, T14); templates, settings and sender domains (T16 onward).

## 5. User stories and acceptance criteria
### Story 1: contracts and words (R-01-T03, T04)
- **AC-1** Every artboard of POR-03, POR-04, POR-14, POR-20 and ADM-10 maps to a data condition,
  persona, clock and parity tier, and the link-contract test knows every outbound target of the
  five screens.
- **AC-2** The glossary carries R-01's tables, compounds and UI terms and the portal copy ban, and
  `banned_patterns` accepts every new identifier.

### Story 2: the portal-pbc contract (R-01-T01, T02)
- **AC-3** Every route of the section exists with exactly one matrix action, answers 404 with its
  flag off and 501 with it on; every field is classified; `portal_documents.read` grants client
  roles only, `scope_only`, and denies the agent and system; the three flags are boolean and off;
  the contract doc names every human-only action and audit event.
- **AC-4** The consumer suite fails if any portal answer carries a firm status code, an amount, a
  confidence or an agent reference, and pins the client words, receipt kinds, `allowed_actions`
  vocabulary and the room's delegated-only shape.

### Story 3: fixtures and POR-03 part 1 (R-01-T05, T06)
- **AC-5** Every POR-03, POR-04 and POR-14 artboard has a scenario whose read is valid against the
  OpenAPI document, and the footings hold: 21 = 19 + 2 = Intake 2, 37 sorted, Keystone 4 of 9 then
  5 of 9.
- **AC-6** POR-03 a, c, e, f, g and h pass their scenario tests with axe clean and no firm status
  word, agent name or bell in the DOM.

## 6. Open questions
Recorded in DEC-240 and the screen contracts' Open gaps.
