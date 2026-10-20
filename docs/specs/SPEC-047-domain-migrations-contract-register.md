---
id: SPEC-047
title: "Domain model contracts: register, ADR drafts, status vocabulary and the C1 work-item stub"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-135, ADR-136, ADR-138, ADR-139]
related_specs: []
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition: `docs/plan/AMENDMENT-solo.md` overrides any two-founder process in the epic. No owner, approver, test author, ruleset, reservation issue or merge window applies. Acceptance tests are written first from this spec; a test is never edited to make it pass.

## 1. Summary
This is epic F-03 (plan: `docs/plan/epics/F-03.md`) in its first slice: the contract register, the decision drafts (P-38, P-04, P-05, P-39, P-36, P-44, P-06, P-09, P-10, P-34, P-28), the status vocabulary YAML (contract C2 data) and the C1 stub (501 routes behind `engagements.work_items_api`). Migrations, live C1 and the later contract tests are separate rows (T05 and T07 onward).

## 2. Problem and context
F-03 is the root of the critical path: C1 (work items and lifecycle) and C2 (status registry) must be frozen before consumer epics build on them. The register tells every session what is frozen and who consumes it; the YAML is the single source of status words; the stub lets consumers write contract tests against a stable shape before the implementation exists.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Builder | Authors the register, drafts, YAML and stub. |
| Claude Code session | Reads the register and YAML; consumes the C1 stub. |
| Agent or system principal | Denied the accept, decline and hold actions (INV-1). |

## 4. Goals and non-goals
**Goals**
- A complete C1 to C21 register with a documented frozen-contract rule.
- Drafts of eleven ADRs on time.
- One status vocabulary YAML covering every object and word.
- A C1 stub whose generated client and examples are stable.

**Non-goals**
- Migrations 0056 onward, live C1, per-module registries, status codegen, contract-test CI (F-03-T05, T07 onward).
- Two-founder approvals, CODEOWNERS for `docs/contracts/`, deciders handles (void).

## 5. User stories and acceptance criteria
### Story 10.1: a contract register (F-03-T01)
- **AC-1** Given the plan's contracts C1 to C21, when T01 lands, then `docs/contracts/README.md` lists each with provider epic, consumers, freeze sprint, version and status, and `docs/contracts/_TEMPLATE.md` exists.
- **AC-2** Given C1 v1 frozen, when a provider PR removes or renames a field, then the snapshot diff fails CI unless the PR ships C1 v2 with one sprint of overlap; consumer contract tests run in the provider's CI and must stay green. The register documents this rule (CI enforcement is a later row, F-03-T18).

### Story: the F-03 ADR drafts exist (F-03-T02, F-03-T03)
- **AC-3** Given chapter 03's text, when T02 lands, then nine draft ADR files exist for P-38, P-04, P-05, P-39, P-36 (open by Thu Oct 22) and P-44, P-09, P-10, P-06 (open by Fri Oct 30, M1), numbered as `docs/adr/backlog.md` lists them (next free numbers); the red ones (P-38, P-04, P-44, P-06, P-09, P-10) never default on silence.
- **AC-4** Given the status registry and entitlements decisions, when T03 lands, then P-34 (status registry and codegen) is open by Thu Oct 22 and P-28 (entitlements and agent-minutes) by Fri Oct 30.

### Story 2.1 and 3.1: the status vocabulary (F-03-T04)
- **AC-5** Given blueprint 3.3.1, when `docs/product/status-vocabulary.yaml` is authored, then every object has an entry: engagement 8 states, request 6 plus derived `overdue`, binder 5 (`draft`, `published`, `unpublished`, `complete`, `closed`), and every work-item subtype; each entry has code, context labels, variant, terminal, client_label, derived, and a `RETIRED` map.
- **AC-6** Given the 144 words in the handoff's `lib/status.js`, then each maps to a YAML entry or appears in `RETIRED` with its replacement; the `match` variant never appears on a status.
- **AC-7** Given the request words, then the YAML encodes: repo `received` (upload arrived, unreviewed) reads `uploaded`, displayed "Uploaded – needs review"; repo `accepted` reads `received`, "Received ✓"; `needs_revision` reads `returned` with its reason, including `wrong_document`; `overdue` is derived and never stored.
- **AC-8** Given the YAML, then it is listed in `protected-paths.md` (or its solo equivalent) as AY-authored data that generators read, and parses as YAML.

### Story 1.x, 6.2 and 10.1: the C1 stub (F-03-T06)
- **AC-9** Given the C1 stub PR, when `make generate` runs, then the generated client exposes every C1 operation, each returning 501 behind the flag `engagements.work_items_api` (boolean, default off), with work-item and lifecycle Pydantic models carrying classification tags.
- **AC-10** Given `docs/contracts/work-items.md`, then it carries the Brightwater Hale E0 example payloads for Copperleaf, Northwind, Bluestem and Meridian.
- **AC-11** Given the examples, then they show: Copperleaf's `cas_monthly_close` with 12 `close` work items 2026-01 to 2026-12, each with a `closes` subtype row (`period` 'YYYY-MM'), and a 13th for an existing period answering 409; an `fs_audit` engagement's second `assurance` work item answering 409; Thornbury's `tax_compliance` engagement with four returns, each carrying its own `client_entity_id`.
- **AC-12** Given the examples, then Bluestem (`accepted`, letter not recorded) shows `gates: [{gate:"G3", met:false, blockers:[{type:"engagement_letter"}]}]` and publishing a client request answering `409 {"detail":"gate_unmet","facts":{"gate":"G3"}}`; moving a `prospect` engagement to `active` answers `409 {"detail":"illegal_transition"}`.
- **AC-13** Given the per-type gate policy, then Copperleaf (non-attest, `cas_monthly_close`) with G1 and G3 met opens client data without G2, Northwind (`ebp_audit`) requires G1 to G3, and a firm override looser than the platform default is refused (stricter accepted).
- **AC-14** Given `MeOut` v2, then it carries `capabilities`, role labels, `flags`, `entitlements`, `office_id`, `tz`, `mfa_recent_until`, `server_now` and, for client users, `portal: {shell, scopes}`; record projections carry `allowed_actions` and `read_only_reason` (`archived`, `walled`, `gate_g2`, `role`, `mfa_required`, `flag_off`, `entitlement`).
- **AC-15** Given the matrix actions registered by the stub, then engagement accept, decline and hold are human-only: an agent or system principal is denied at the matrix, `require_live_human` and the database check, and no `accepted` state is written (INV-1); every transition writes one audit event and one `engagement.status_changed` outbox event in one unit of work (INV-5).

## Task map
Plan key to the acceptance criteria it must satisfy. 

| Plan key | Acceptance criteria |
|---|---|
| F-03-T01 | AC-1, AC-2 |
| F-03-T02 | AC-3 |
| F-03-T03 | AC-4 |
| F-03-T04 | AC-5, AC-6, AC-7, AC-8 |
| F-03-T06 | AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15 |

## 6. Behaviour and flows
Documents, one YAML data file, and a stub PR. The stub returns 501; nothing is implemented behind it. Order: T01 and T02/T03 (parallel), then T04, then T06 (depends on T01, T02, F-02-T04).

## 7. Domain and data changes
N/A beyond what the criteria name; this slice changes no product tables unless an AC says so.

## 8. Interfaces
N/A beyond what the criteria name.

## 9. Authorisation and tenancy
N/A: repository, documentation and contract tooling; no tenant data is read or written by the slice. Where an AC names a matrix action, the standard `authorise()` and agent-deny rules apply.

## 10. AI behaviour
N/A: no model calls.

## 11. Integrations
N/A except where an AC names GitHub Actions, `gh` or a hosted database.

## 12. Edge cases and failure modes
- A red ADR slips past its date: red ADRs never default; C1/C2 freeze moves with it (R2).
- ADR numbers on disk differ from the backlog: `backlog.md` wins.
- A status word absent from `status.js` is needed: add it to the YAML with a note.

## 13. Security and privacy
- **Data classification:** internal; example payloads use synthetic Brightwater Hale data only.
- **Threats considered:** an agent principal accepting an engagement (INV-1).
- **Mitigations:** matrix deny, `require_live_human`, database check (AC-15).

## 14. Audit trail and evidence integrity
Every decision is recorded in `docs/product/decision-log.md` or an ADR. Generated files are never hand-edited.

## 15. Observability
N/A.

## 16. Performance and scale
Only the CI time budgets named in the criteria.

## 17. UX
N/A: no screens.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 | review | Register lists C1 to C21 with all columns. |
| AC-2 | review | Rule written in the register. |
| AC-3 | review | Nine ADR files with dates met. |
| AC-4 | review | Two ADR files with dates met. |
| AC-5 | unit | YAML covers every 3.3.1 object (loaded and counted). |
| AC-6 | unit | All 144 status.js words mapped or retired; no `match` variant. |
| AC-7 | unit | Request code mapping and labels asserted. |
| AC-8 | unit | YAML parses; path listed. |
| AC-9 | integration | Generated client exposes every C1 operation returning 501 behind the flag. |
| AC-10 | review | Four E0 payloads present. |
| AC-11 | contract | Example payloads show the 12/13th, second assurance and four returns cases. |
| AC-12 | contract | Bluestem gate projection and 409 shapes. |
| AC-13 | contract | Gate policy cases. |
| AC-14 | contract | MeOut v2 fields and read_only_reason set. |
| AC-15 | integration | Agent/system deny on accept, decline, hold; audit plus outbox shape. |

## 19. Rollout
No feature flag unless an AC names one. Changes land on `main` once `make check` is green; staging is deployed once at sprint close (AMENDMENT-solo section 9).

## 20. Open questions
All answered with the plan's proposed option.
- [x] Binder 1:1 versus 1:n (R3a): follow DEC-31 (1:n).
- [x] Offices owner (R3b): `organisations`; `identity` stores `office_id` as an opaque UUID with a DB foreign key.
- [x] YAML path (R3c): `docs/product/status-vocabulary.yaml`.
- [x] Status codegen split (R3d): the builder does the YAML, the generator and the runtime.
- [x] `/v1/me/capabilities` versus capabilities inside `/v1/me` (R3e): ship both, one implementation.
- [x] Does `contracted -> active` wait for the first binder publish or the first work item (Q1)? First published binder, except `intake` binders, which may publish before G3 (DEC-39).
- [x] Is `prospect` both a client and an engagement status (Q2)? Yes, independent fields.
- [x] Which `firm_setting` keys does the generic condition read in season 1 (Q3)? `seniors_can_create`, `staff_can_accept_evidence`, `seniors_can_publish`, `client_service_can_publish`.
- [x] Is `work_items.status` a projection or written (Q4)? Written by the owner through `engagements.api.project_status()` in the owner's unit of work.
- [x] Entitlements for the Brightwater Hale firm (Q5)? All modules on in the scenario; production canary gets the MVP-1 set.

## 21. Future / explicitly deferred
- Migrations, live C1, registries, status codegen, tolerant reader, router split, contract-test CI, consumer tests (F-03-T05 and T07 to T38): add ACs when their task files are written.
