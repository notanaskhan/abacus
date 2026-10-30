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

**Firm-standards service (K-02-T08).**
- **AC-27** The owner (a partner member, `owner_of_target`) drafts from the version in effect and publishes it with fresh MFA; a version published effective Oct 1, 2026 on the demo clock (Sep 14) leaves the prior one current until then, after which the prior one reads `superseded` (computed, never stored); `…_version.published` names the publisher (INV-5) and `firm_standard.published` or `threshold_policy.published` reaches the outbox. A partner who is not the owner gets 403 `not_standard_owner`, and `allowed_actions` omits draft and publish for them (US-3.2, US-3.3).
- **AC-28** Drafts are partners' only: anyone else gets 404 for a draft version and sees no draft row in a list, a detail or a Timeline; discarded versions are hidden from everyone (US-3.4).
- **AC-29** An agent, the system or support asking to draft, edit, discard or publish is refused (403) and `decision.refused_non_human` is recorded in its own unit of work; the database's `published_actor_kind = 'human'` CHECK and trigger stand behind it (US-3.3).
- **AC-30** One draft per standard (409 `draft_exists`); nothing published to draft from is 409 `no_current_version`; an edit is at the `row_version` read (If-Match; 409 `stale_version`), a draft only (409 `not_draft`), with a payload valid for the standard's kind and, for AJE thresholds, its "review required" and "always held" rows kept (422 `payload_invalid`).
- **AC-31** A publish takes effect today or later in business time (422 `effective_from_backdated`) and after every published version's date (422 `effective_from_not_after_current`); a retried `Idempotency-Key` answers what the first publish did.
- **AC-32** Discard keeps the row as `discarded`; the diff lists changed cells by JSON pointer with before and after strings, against the version a draft came from by default.
- **AC-33** The examples slot (`register_standard_examples`) answers `provider_registered: false` with no rows until a provider registers; a provider's rows are already `visible()`-filtered, and no hidden count is shown (DEC-43, US-3.6).
- **AC-34** `current_version(tenant_id, key, as_of)` names the version in effect (`LookupError` before the first effective date or for an unknown key); a standard's owner must be a partner member (422 `owner_not_partner`), and a key is one standard per firm (409 `standard_key_taken`). KNW-01's `firm_standards` category lists one card per published standard and a change-log entry per published version; the C15 projection `firm_standard` carries the name and kind only.
- **AC-35** (K-02-T06) The operator CLI's publish is refused to the version's drafter (and a withdrawal to one person) before the definer refuses it again.
- **AC-36** (K-02-T06) A draft file is JSON, or a CSV or XLSX whose first sheet's header names the kind's row fields; XLSX cells are read as cached values only (a formula is never evaluated), files are bounded, and problems name sheet, row, column and code, never contents; the rows parse as the kind's payload before any write.
- **AC-37** (K-02-T06) `refdata diff` lists every added, removed and changed row against the version in effect, by each kind's identity fields.
- **AC-38** (K-02-T06) The CLI refuses while `ABACUS_DEPLOY_LOCK_ENV`'s deploy lock is held and, outside the ops task, when a database setting points at a hosted host.
- **AC-39** (K-02-T10) `classify_entry`: an attest client's entry is always held (`attest_client`, the always-held row's approver) whatever the amount; a listed class is within threshold up to its limit inclusive and review required above it (`over_limit`); an unlisted class is review required (`unlisted_class`); every result names its policy version.
- **AC-40** (K-02-T10) `variance_exceeded` is true only when the change is strictly over both the percent and the amount for its context (a zero prior: the amount alone).
- **AC-41** (K-02-T10) `materiality_range_for` and `validate_materiality` answer the firm's range per engagement kind and whether a partner's chosen percentages sit inside it (inclusive), with performance materiality and the clearly-trivial percentage.
- **AC-42** (K-02-T10) `confidence_hold` holds below the floor and never auto-accepts while the payload cannot enable it.
- **AC-43** (K-02-T10) `required_review_levels` and `return_approval_policy` answer a tier's levels and the client's signing partner (None when unassigned, never a default); a missing row is 422 `standard_row_missing`.
- **AC-44** (K-02-T10) `ssars_framework_for` answers CAS by-product for periods ending on or after Dec 15, 2026 (or any period once SSARS 27 is adopted early), AR-C 70 preparation before.
- **AC-45** (K-02-T11) `GET …/versions/{id}/export.xlsx` writes the version in the import format (a `Rows` sheet for the payload's list, a `Settings` sheet of `field`/`value` for the rest), byte-stable for the same payload; importing it again drafts a payload with the same hash (an empty diff).
- **AC-46** (K-02-T11) Imports read the raw XLSX or CSV body: cached values only, bounded, every problem 422 `import_invalid` as sheet, row, column and code, never a cell's content.
- **AC-47** (K-02-T11) `POST /v1/standards/{id}/imports` drafts the owner's next version (409 `draft_exists` with a draft open); an import never publishes or changes a published version.
- **AC-48** (K-02-T11) `POST /v1/standards/imports` (onboarding) reads a `Standards` sheet and one sheet per key, creates each standard with its first draft, and reports an owner who is not a partner member as that row's `owner_not_partner` while the other rows import.
- **AC-49** (K-02-T12) Publishing or withdrawing a reference-set version (`refdata publish|withdraw`) starts ReferenceSetFanOutWorkflow once per version and action (background class, identifiers only); `refdata fanout` restarts it.
- **AC-50** (K-02-T12) Each active tenant gets exactly one `reference_set.published` (or `.withdrawn`) audit event and outbox event naming the version, the set key and the operator and approver handles; a re-run or retry writes nothing twice.
- **AC-51** (K-02-T12) C16's `rules_table_updated` kind notifies firm admins from the outbox event; consumers (tax due dates) recompute from it.
- **AC-52** (K-02-T14) KNW-04 i: the owner's draft shows the version chip and a neutral "Draft vN" pill, the draft's table with every changed value amber-tinted and the prior value struck, and "n changes from vM".
- **AC-53** (K-02-T14) The sticky Save bar reads "Draft vN · n changes from vM · visible to partners only" with the Effective date, Discard draft and Publish vN… (owner only, after a change summary; ConfirmDialog; a 403 opens the step-up); New version… is disabled while a draft is open.
- **AC-54** (K-02-T14) Typed editors per kind edit the draft in place (AJE limits, variance percent and amount, materiality ranges, document confidence, SSARS early adoption); a save sends If-Match and a 409 `stale_version` shows "Changed by … Reload to see the latest draft." instead of overwriting.
- **AC-55** (K-02-T14) Staff never see a draft or Publish; Export downloads the draft's workbook for the owner.
- **AC-56** (K-02-T15) The calendar engine reproduces every golden due date in `backend/tests/golden/calendar/i_clocks.yaml` (TY2025 and TY2026 for 1040, 1065, 1120-S, 1120, 1041, 990/8868, 5500/5558, and 706/4768), including IRC §7503 rolls and extensions run from the unrolled date, and every case cites its source.
- **AC-57** (K-02-T15) The clocks (AU-C 230 assembly and AU-C 265 communication +60, FTC notice +30, 8879 retention three years with Feb 29 ending on Feb 28) match their golden cases and never roll.
- **AC-58** (K-02-T15) A disaster postponement moves only a covered date in a covered place, never earlier.

## 4. Out of scope here
The CLI, import and export, fan-out and KNW-04i/j (K-02-T06 to T12, T14 to T20) build against the same contract in later sprints.
