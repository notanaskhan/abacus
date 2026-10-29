---
id: SPEC-501
title: "Tax compliance rails, S16 contract window: C19 consent gate, tax-engine bridge and e-file record stubs, consents migration, protected bundle, glossary, screen contracts and fixtures (T-01-T01 to T09)"
status: in-progress
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-231, ADR-300]
related_specs: [SPEC-500]
created: 2026-10-29
updated: 2026-10-29
---

> **Instructions for coding agents**
> - Implement only what this spec describes. `docs/plan/epics/T-01.md` is the plan of record (§3, §4, §5); where they differ, the epic wins and this spec is corrected.
> - Accrued is never an ERO or a transmitter (R-04): no MeF, A2A, ETIN, EFIN or IRIS TCC identifier and no IRS or state host anywhere.
> - TRI never reaches a model without both consents (condition 6). Every test names the acceptance criterion it proves.

## 1. Summary
T-01 gives Accrued the §7216 consent registry and the gate that keeps tax return information (TRI) away from a model without the taxpayer's signed `use` and `ai_disclosure` consents, a file bridge to CCH Axcess Tax with a person approving every import, final approval and export after approval, and a record (never a transmission) of e-file. S16 opens the window with contracts and the data model.

## 2. Acceptance criteria
**C19 stub (T-01-T01).**
- **AC-1** Every C19 route of T-01 §4.3 (consents, summary, detail, evidence, requests, renewals, records, declines, revocations, exports, per-entity consents, template import and publish, tax profile, elections, authorizations, transcripts, comparisons) declares its matrix action and answers 404 for a client principal, 404 with its flag off and 501 with it on.
- **AC-2** Every C19 write and read denies the agent, the system and every client principal; recording, exporting and the template actions need a fresh second factor.
- **AC-3** Every field is classified; figures from returns and transcripts are TRI; no field is a plaintext TIN.
- **AC-4** Flags `consents.registry` and `clients.tax_profile` default off; `organisations.api.consent_state` and `tri_consent_verdict` exist and raise until T-01-T10.

**Tax-engine bridge and e-file record stub (T-01-T02).**
- **AC-5** Every route of the TAX-09, TAX-12 and ADM-08 family (engine sync, exports, imports, final approval eligibility and POST, delivery, packets, e-file envelope, ERO notice, transmissions, acks, deliverables, integration settings, mappings, test, ERO designation) declares its action and is a stub behind `tax.engine_bridge` or `tax.delivery_efile`.
- **AC-6** `tax_return.approve`, `tax_return.export`, `engine_import.create`, `engine_import.approve`, `delivery_packet.prepare`, `delivery_packet.approve`, `transmission.record`, `efile_ack.record`, `deliverable.publish`, `integration.configure`, `integration.test` and `member.set_ero` deny the agent and the system; none is holdable by an agent's task scope.
- **AC-7** No route, model or field names a transmission to the IRS: transmissions are a human's record of what the ERO did in the engine.
- **AC-8** `docs/contracts/tax-engine-bridge.md` and `docs/contracts/efile-record.md` exist; the tax module's seam note names the red files `approval.py`, `export.py`, `filing.py` and `tri.py`.

**Consumer contract tests (T-01-T03, T-01-T04).**
- **AC-9** Consumer suites in `backend/tests/contracts/c19/` and `backend/tests/contracts/tax_engine/` assert TRI tags, no TIN or bank plaintext, one purpose per consent document and no agent-holdable export, import approval or transmission action.
- **AC-10** `backend/tests/contracts/c21_t01/` asserts `form_8879_for` and `pub1345_tolerances` (both tolerance keys) and that a version id comes with every result; `backend/tests/contracts/c7_t01/` asserts the envelope-source registration T-01 needs.

**Screen contracts and fixtures (T-01-T05, T-01-T09).**
- **AC-11** `docs/screens/CLI-05.md`, `ADM-05.md`, `ADM-08.md`, `TAX-09.md` and `TAX-12.md` list states, personas, clocks, parity tiers, copy keys, links and deviations.
- **AC-17** Fixture seed rows and handlers for the five screens foot (218 = 212 + 2 + 1 + 1 + 1 + 1; 141,634 + 96,989 + 69,277 = 307,900).

**Vocabulary (T-01-T06).**
- **AC-12** The glossary has the T-01 rows (consent set, consent template, TRI, offshore disclosure, transmission record, e-file acknowledgement, engine import, export file, amount binding, delivery packet, ERO); the status registry has `consent`, `tax_authorization`, `engine_sync` and `efile_ack` objects.

**Protected bundle (T-01-T07).**
- **AC-13** `write-capabilities.yaml` has W2 `cch_axcess_tax.export_file` (mode `file`, no egress host); protected paths name `organisations/consent*.py`, `organisations/tax_profile.py` and `tax/{approval,export,filing,tri}.py`.
- **AC-14** Banned patterns NEVER-ERO-001 (MeF, A2A, ETIN, EFIN, IRIS TCC identifiers in code) and TAXAPPROVE-001 (only `tax/approval.py` records a `final_approval` sign-off for a tax return) fail a violating file; no egress allowlist host is an IRS or state revenue host.

**Consents migration (T-01-T08).**
- **AC-15** `consent_sets`, `consents`, `consent_signers` and insert-only `consent_events` are tenant tables with forced RLS; a consent names one purpose and at least one tax year; a second open request for a purpose the taxpayer declined is refused by a partial unique index.
- **AC-16** schema_check passes up/down/up; the app never deletes a consent or updates an event.

**The gate: condition 6 and the TRI rails (T-01-T11).**
- **AC-17** An `AssembledContext` carrying TRI `data_subjects` is refused with `DataBoundaryRefused(reason="consent_7216")` unless every subject holds `use` and `ai_disclosure` in force for its year; on every route (`fake` included) and for every firm, before the synthetic pass; audited (`ai.boundary_refused`, reason index 9: the recorded indices are append-only), counted, never retried or rerouted; unregistered means refused.
- **AC-18** With both consents in force for every subject (both spouses on a joint unit, every required signer signed), the call proceeds to the existing boundary conditions unchanged; every allowed call writes one `tri.agent_read` access event per subject and per covering consent.
- **AC-19** Nothing is cached: a revocation, an expiry (business time) or a year not covered refuses the next call; a consent signed under other material provider terms (the covering Bedrock entry's `material` hash) is refused (re-consent).
- **AC-20** A TRI field whose subject or year could not be resolved is refused (fail closed); `require_tri_consent` raises 409 `consent_required` naming the client entity and purpose, and writes `tri.tool_read` access events when it allows.
- **AC-21** The matrix condition `consent: <purposes>` takes only the six §7216 purposes; it is a resource condition binding every actor, held only when every `TargetFacts.consent_subjects` entity holds every listed purpose now (none: refused); the generated security cases cover it (consented allow; not consented and no subjects deny).
- **AC-22** An agent spec declaring `data_classes: [tri]` loads only while the `use` and `ai_disclosure` consent checks are registered.
- **AC-23** Model text is stored with every unmasked SSN, ITIN or EIN form masked (`•••-••-1234`) and the hit counted (`abacus.ai.tin_masked`); a TIN in the assembled context still refuses the call (`pii_in_context`, ADR-167 §2).

**TRI MFA, offshore and the SSN unlock (T-01-T12).**
- **AC-24** P-08's floor includes `tri_scope` (engagements): a client person with an active grant on a K-1 package, a `tax_return` work item or an engagement holding one must pass the second step (POR-01c) before any TRI-bearing page; other scopes are not TRI-bearing. Unregistered, the floor fails closed.
- **AC-25** The `offshore_disclosure` provider is registered in G-01's slot: a client is covered when it has a taxpayer entity and every entity holds the consent in force (signed by every required signer, unrevoked, unexpired); the check, the SQL predicate (ADM-03d) and the count agree.
- **AC-26** An offshore member is assigned to a client's work only while it is covered (409 `offshore_consent_required` otherwise; offshore is not a wall, DEC-319); every TIN they read is masked or null (`mask_tins_for`), and `tin.reveal` stays `not_offshore`.
- **AC-27** TIN fields carry `tri` beside `pii_kind=tin`; P-07's SSN and ITIN refusal on a real firm lifts once C19's `use`, `ai_disclosure` and `offshore_disclosure` checks are registered (before that it stays 422 `tin_kind_not_allowed`).
