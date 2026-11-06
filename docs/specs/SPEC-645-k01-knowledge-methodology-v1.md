---
id: SPEC-645
title: Knowledge library and methodology v1
status: done
owner: founder
risk_zone: amber
related_adrs: [ADR-005, ADR-052, ADR-112]
related_specs: [SPEC-008, SPEC-009, SPEC-019]
created: 2026-11-06
updated: 2026-11-06
---

## 1. Summary
A record of what K-01 built: the firm's methodology as database content with a lifecycle, and the
three screens later audit, engine and agent epics cite. The behaviour and its acceptance criteria are
K-01's own (`docs/plan/epics/K-01.md` §3); this spec names the result and does not restate them.

## 2. Problem and context
A methodology held in Word and spreadsheets can't be pinned to an engagement, cited by a workpaper or
diffed between versions. K-01 makes it content a firm loads and approves, never a commit.

## 3. Actors
The QM owner approves versions and changes mandatory locks. Audit staff read. The Accrued Agent's
Methodology importer proposes steps from a document and decides nothing.

## 4. Goals and non-goals
**Goals.** One catalog over a provider slot (KNW-01). Programs and steps with stable anchors
(KNW-03). Versions with effective dates, diff, standards mapping and import review (KNW-02).

**Non-goals.** The agent approving, locking, unlocking or publishing anything. Updating an
engagement's pinned version (K-03, ADR P-41). Licensed publisher text. Tax return information.

## 5. User stories and acceptance criteria
K-01 §3, as built by K-01-T01 to T25. Independent tests: K-01-T24 and the `k01_knowledge` contracts.

## 6. Behaviour and flows
**Happy path.** A person uploads a document or a workbook, reviews flagged steps, submits, and the QM
owner approves with an effective date. An engagement pins the version in force.

**Alternate paths.** The workbook path needs no model. A refusal or a failed import writes no version
(RB-49).

## 7. Domain and data changes
Owned by `methodology`; see `backend/src/abacus/modules/methodology/README.md`.

## 8. Interfaces
`docs/contracts/knowledge-catalog.md` and `docs/contracts/methodology-programs.md`.

## 9. Authorisation and tenancy
`docs/architecture/permission-matrix/methodology.yaml`; every list applies `visible()`; a client
principal gets 404.

## 10. AI behaviour
The Methodology importer only: registered prompt, gateway budget, pages delimited as untrusted
(ADR-052), code verifies every quote, and a person approves (ADR-005). See RB-49.

## 11. Integrations
None beyond the model gateway.

## 12. Edge cases and failure modes
RB-49. A PII hold fails the import before any model call.

## 13. Security and privacy
An unmasked SSN, ITIN or EIN fails the import. Source files are write-once and scanned before parse.

## 14. Audit trail and evidence integrity
Every state change goes through the unit of work and writes an audit event; approved versions are
never edited.

## 15. Observability
RB-49 and the module's run records.

## Rollout
`docs/operations/k01-flag-plan.md`. Its per-firm flip isn't approved and waits on K-02-T20.
