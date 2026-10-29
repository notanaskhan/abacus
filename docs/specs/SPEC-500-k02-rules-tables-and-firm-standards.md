---
id: SPEC-500
title: "Rules tables and firm standards: C21 reference sets, due dates, firm standards and threshold policies, KNW-04 (K-02)"
status: in-progress
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-300]
related_specs: []
created: 2026-10-29
updated: 2026-10-29
---

> **Instructions for coding agents**
> - Implement only what this spec describes. `docs/plan/epics/K-02.md` is the plan of record (§3 user stories, §4 backend, §5 frontend); where they differ, the epic wins and this spec is corrected.
> - No rule or standard content in code, migrations or seed: rules are database rows loaded through the operator CLI or the import endpoints (AGENTS.md 16).
> - Nothing in K-02 calls a model (INV-1). Every test names the acceptance criterion it proves.

## 1. Summary
Two kinds of versioned, effective-dated rules (K-02 short version): **platform reference sets** (C21 part A: due-date rules, legal holidays, disaster postponements, the 8879 form set with Pub 1345 tolerances, information-return thresholds, retention minimums and standards sets), global and published under a two-person rule; and **firm standards and threshold policies** (C21 part B; KNW-04), per tenant, owned by a named partner who alone publishes them.

## 2. Actors
| Actor | Role |
|---|---|
| Owner partner (Priya Raman, Daniel Reyes) | Drafts, imports and publishes the standards they own |
| QM owner / practice leader (Margaret Okonkwo) | Creates standards, assigns owners, bulk-imports onboarding workbooks |
| Every firm role | Reads published versions; partners also see drafts |
| Operator and approver (the two founders) | Draft and publish reference sets through the CLI (K-02-T06) |
| Accrued Agent | Reads at task scope only; never drafts, imports or publishes |
| Portal principals | Denied every K-02 route |

## 3. Acceptance criteria
**Protected bundle (K-02-T01).**
- **AC-1** Every K-02 write (`firm_standard.create`, `.assign_owner`, `.draft`, `.import`, `.publish`) denies the agent, the system and every client principal; `firm_standard.read`, `reference_set.read` and `due_date.read` allow every firm role and the agent at task scope only (US-3.3, US-3.7).
- **AC-2** Drafting and publishing are the named owner's, a partner member now (`owner_of_target`); a non-owner partner, a former partner and an actor without owner facts are refused; agents, system runs and support sessions never meet the condition (US-3.3).
- **AC-3** Flags `knowledge.firm_standards` and `rules.reference_sets` exist, default off, expire within 90 days; `firm_standard.create` and `.publish` require fresh MFA.

**C21 v1 contract stub (K-02-T02).**
- **AC-4** Pydantic models for the seven reference-set kinds, the eight firm-standard kinds and the due-date result, discriminated by kind, `payload_schema_version` 1, every field classification-tagged (reference payloads `public`, standard payloads `internal`, example rows and BH-TAX-02 applies-to `confidential`); no TRI.
- **AC-5** Every route of K-02 §4.4 is registered with its matrix action and returns 404 with its flag off and 501 `not_implemented` with it on, until its build task; the generated client carries the models (`make generate`).
- **AC-6** The module-API signatures of K-02 §4.5 exist and raise `NotImplementedError` until built; T-01's and T-02's consumer contract tests import them and the models and run green against the stub.
- **AC-7** `docs/contracts/rules-tables.md` lists callers, status words, human-only actions, audit events and the `as_of` rule per consumer; `docs/screens/KNW-04.md` lists states a–i and j.

**Global reference-set tables (K-02-T03).**
- **AC-8** `reference_sets`, `reference_set_versions` and `reference_set_publications` have no tenant and no `abacus_app` privilege; the app reads published versions only through `reference_set_resolve` and `reference_set_list` and never sees a draft (US-1.2).
- **AC-9** A version cannot be published unless its approver differs from its drafter; once published its payload, effective date and handles are frozen and `withdrawn` is the only later status; publications are insert-only (US-1.1).
- **AC-10** `reference_set_draft`, `_publish`, `_withdraw`, `active_tenant_ids` and `standards_sets_apply` are owner-only; publishing a `standards_sets` version inserts new codes into `standards_sets` and updates label and refs of existing ones, never deleting one, and refuses an issuer or PCAOB family (US-1.4). schema_check passes up/down/up.

**Methodology tenant tables (K-02-T04).**
- **AC-11** `firm_standards`, `firm_standard_versions`, `threshold_policies` and `threshold_policy_versions` are tenant tables with forced RLS; one draft per parent; versions monotonic per parent; a published version is frozen and never deleted; a draft moves only to `published` or `discarded`; `published_actor_kind = 'human'` is a CHECK (US-3.2, US-3.3).
- **AC-12** The status registry carries `firm_standard_version` (draft, published, superseded computed, discarded hidden) and `reference_set_version` (draft, published, superseded computed, withdrawn).

**KNW-04 read states (K-02-T13).**
- **AC-13** `/knowledge/standards` renders on the T12 SettingsLayout: the section list, the form header (version chip, Published pill, New version…, Apply to returns…), and states a–h with Fieldsets, ValueRows, display-only policy Toggles linking ADM-04, the Timeline, the example panes with the designed empty state, and planned links to CLS-06, AUD-07 and TAX-14; one fixture scenario and one test per state (US-3.1, US-3.5).
- **AC-14** With `knowledge.firm_standards` off, the route renders the T12 frame with the C-20 "not turned on" state.

**Reference-set service (K-02-T05).**
- **AC-15** Resolution on a date is the latest `effective_from` on or before `as_of`, ties to the highest version: a re-published correction with the same effective date wins, and the prior set answers before a later set's effective date; an unknown key or nothing in effect is a `LookupError` (404 on the wire) (US-1.3).
- **AC-16** A draft is never served: not resolved, not listed, not in a set's versions.
- **AC-17** `reference_value`, `form_8879_for`, `pub1345_tolerances`, `information_return_threshold` and `retention_minimum` read the sets in effect and return the id of the version each answer came from; nothing in effect is a `LookupError`, never a default (DEC-71, DEC-85).
- **AC-18** `GET /v1/reference-sets`, `/{key}` (`as_of` defaults to today in business time) and `/{key}/versions` are live: a client principal gets 404 before the matrix, then `reference_set.read`, then 404 with `rules.reference_sets` off; each version names its id, handles and source citations.
- **AC-19** `check_draft` (the operator CLI's pre-draft check) refuses a `standards_sets` payload that holds a PCAOB or issuer set (by code, label or reference), drops a code any version has published or moves one to another family: 422 `standards_set_refused` with `facts.reason` (X-07, DEC-19).
- **AC-20** The kind registry maps each of the seven kinds to its payload model; a payload whose kind is unknown or differs from the set's, or that fails its model, is refused (422 `reference_kind_unknown`, `reference_payload_invalid`).

**Calendar engine (K-02-T07).**
- **AC-21** `practice/compute/calendar.py` is pure (no clock, no database): a due date is the rule's day in the month `months_after_period_end` after the period end (clamped to the month's end); the extension adds its months to the unrolled original, on its own `day` when the rule names one; calendar- and fiscal-year rules come before `any`. Ridgeline's TY2025 1065 is due Mar 16, 2026 and extended to Sep 15, 2026; a June-30 990 is due Nov 16, 2026 and extended to May 17, 2027 (US-2.1).
- **AC-22** IRC §7503: a Saturday, Sunday or legal holiday rolls to the next business day; federal filings count every published holiday, federal and DC (QK-5).
- **AC-23** A disaster postponement moves each date in its window for a covered location (a state with no counties covers the whole state) to its postponed-to date, never earlier, and the result names the notice; no location, no postponement.
- **AC-24** Clocks are calendar days and never roll: AU-C 230 and 265 +60, FTC +30, 8879 retention three years after its start (Feb 29 ends Feb 28); `add_business_days` skips weekends and published holidays (US-2.2).
- **AC-25** `inputs_hash` is sha256 over the canonical inputs and the version ids read: identical inputs and rules give an identical hash and result.
- **AC-26** `due_dates_for` reads due-date rules in effect on the period end (a set naming the return's tax year first) and holidays and postponements in effect on the later of today and a fortnight past the latest unrolled date; every result lists the version ids read. `GET /v1/due-dates` is live behind the client 404, `due_date.read` and `rules.reference_sets`; a form with no rule is 404.

## 4. Out of scope here
The CLI, firm-standards service, import and export, fan-out and KNW-04i/j (K-02-T06 to T12, T14 to T20) build against the same contract in later sprints.
