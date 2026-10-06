---
id: SPEC-001
title: Synthetic client generator, phase 1
status: approved
owner: Founder
risk_zone: amber
related_adrs: [ADR-031, ADR-042, ADR-044, ADR-050, ADR-052, ADR-064, ADR-075, ADR-081, ADR-085, ADR-087, ADR-101]
related_specs: [SPEC-000]
created: 2026-10-06
updated: 2026-10-06
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
A seeded, deterministic generator in `abacus_tools.synthetic` that produces a realistic synthetic client: client entities, a balanced general ledger, trial balances, bank statements, AR/AP agings and a request list. It can inject flaws from a defined failure taxonomy and adversarial content. The same seed always gives byte-identical output. Phase 1 covers what SPEC-000 and the connector tests need; documents (invoices, contracts as PDFs) come in phase 2.

## 2. Problem and context
ADR-085 forbids real client data in the repository and makes the generator the only source of fixtures, evaluation cases, staging data and load-test data. The build plan (§5.1 step 4) builds it before the walking skeleton because SPEC-000's fake connector (AC-9 to AC-11) needs a trial balance — balanced and unbalanced — and every later test layer needs realistic ledgers. Without it, agents invent ad-hoc fixtures that drift apart and miss the failure cases that matter.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Coding agent / developer | Calls the generator in tests and fixtures with a seed |
| Fake connector (SPEC-000) | Serves generator output through the connector contract (ADR-037) |
| Evaluation suites (ADR-081) | Use flawed and adversarial cases with known labels |
| `make seed-staging` / `make loadtest` | Phase 2 consumers (out of scope here) |

## 4. Goals and non-goals
**Goals**
- Deterministic: `(seed, parameters, GENERATOR_VERSION)` → identical output, byte for byte, on every platform
- Accounting-correct by construction: every journal entry balances; trial balance = sum of the general ledger; bank statements reconcile to the cash accounts except for labelled reconciling items
- Every injected flaw and adversarial payload is **labelled** in a manifest, so tests and evaluations know the expected answer
- No value can be mistaken for a real identifier (passes `secrets_scan` by construction)
- Exports to CSV, JSON and XLSX

**Non-goals**
- PDFs, scanned images, emails, contracts, invoices as documents (phase 2; needs a PDF dependency — Q4)
- Seeding staging through the API, load-test orchestration (`make seed-staging`, `make loadtest`) — phase 2, after SPEC-000 provides the API
- Multi-currency consolidation, intercompany eliminations beyond a flag (Q5)
- Tax, payroll registers, fixed-asset registers beyond the GL entries they produce
- Realism tuning against real industry data

## 5. User stories and acceptance criteria

### Story 1: Generate a client deterministically
- **AC-1** Given the same seed and parameters, when `generate(...)` runs twice — including in separate processes and on Linux and macOS — then every export is byte-identical, and a golden SHA-256 of the default client's exports is pinned in a test.
- **AC-2** Given different seeds, when generated, then client names, amounts and transaction counts differ.
- **AC-3** Given `GENERATOR_VERSION` changes, when the golden test runs, then it fails until the golden hash is updated in the same change — output never changes silently.

### Story 2: The ledger is accounting-correct
- **AC-4** Given any seed in a property test (Hypothesis), then every journal entry's debits equal its credits, the trial balance at every month end balances, and each trial balance line equals the sum of its account's GL lines up to that date.
- **AC-5** Given a client with `months=12`, then it has a chart of accounts with assets, liabilities, equity, revenue and expenses; opening balances; and entries from sales, purchases, cash receipts, payments, payroll, depreciation, accruals and a year-end close.
- **AC-6** Given generated bank statements, then each statement's closing balance equals the cash GL account balance at the same date after the labelled reconciling items (outstanding cheques, deposits in transit).
- **AC-7** Given AR and AP agings at period end, then their totals equal the AR and AP control accounts.

### Story 3: Flaws are injected and labelled
- **AC-8** Given `flaws=[...]` naming categories from the failure taxonomy (`docs/product/failure-taxonomy.md`), when generated, then exactly the requested flaws are injected into the named artefacts, and `client.manifest` lists each one with category, artefact, location and expected detection.
- **AC-9** Given `flaws=["unbalanced"]` on the trial balance, then debits ≠ credits on that trial balance only, and the GL stays balanced (this is SPEC-000 AC-11's input).
- **AC-10** Given no flaws requested, then the manifest has no flaws and every invariant in AC-4 to AC-7 holds.

### Story 4: Adversarial content is injected and labelled
- **AC-11** Given `adversarial=True`, then free-text fields (memos, descriptions, vendor and customer names) include payloads from each adversarial category (§7), each labelled in the manifest, without breaking AC-4 to AC-7.
- **AC-12** Given CSV or XLSX export of adversarial content, then the file reproduces the payload exactly (it is test input, not sanitised) and the manifest marks it, so downstream code's sanitisation can be tested (ADR-052, ADR-064).

### Story 5: Identifiers are unmistakably synthetic
- **AC-13** Given any generated client, when `secrets_scan` runs over its exports, then there are no findings: SSNs use area 9xx, EINs use an unassigned prefix, routing numbers fail the ABA checksum, card numbers are published test numbers, emails use `example.com`/`example.org` and phone numbers use 555-01xx.
- **AC-14** Given any generated name or address, then it comes from built-in word lists and carries no real-world identifier; every client name and client entity name ends in " (Synthetic)" (Q3).

### Story 6: Exports and requests
- **AC-15** Given a client, then `to_csv(dir)`, `to_json(dir)` and `to_xlsx(path)` write the chart of accounts, GL, trial balances, bank statements, agings, request list and manifest, with `Decimal` amounts rendered without float rounding.
- **AC-16** Given a client, then its request list contains request items across audit areas with a retrievability tier (A–E) each, using glossary terms, and the trial balance request item is tier A.
- **AC-17** Given the default parameters (`entities=1`, `months=12`, ~2,000 entries/month), then generation and all exports finish in under 5 seconds on a CI runner.

## 6. Behaviour and flows
1. `generate(seed, *, entities=1, months=12, start=date(2025, 1, 1), size="small", flaws=(), adversarial=False) -> SyntheticClient`
2. A single `random.Random(seed)` stream per sub-generator, derived from the seed and a fixed sub-generator name, so adding a sub-generator doesn't shift others' output.
3. Order: client and entities → chart of accounts → opening balances → monthly business activity (journal entries) → month-end entries → year-end close → derived artefacts (TB, bank statements, agings) → request list → flaws → adversarial payloads → manifest.
4. Flaws and adversarial payloads are applied to **copies of derived artefacts**, never to the underlying ledger, unless the category is a ledger flaw.

## 7. Domain and data changes
No database tables. In-memory frozen dataclasses in `abacus_tools.synthetic`: `SyntheticClient`, `ClientEntity`, `Account`, `JournalEntry`, `JournalLine`, `TrialBalance`, `TrialBalanceLine`, `BankStatement`, `BankLine`, `Aging`, `AgingLine`, `RequestList`, `RequestItem`, `Manifest`, `Flaw`, `AdversarialPayload`. Amounts are `Decimal` with two places. Names follow the glossary (`client_entity`, `request_item`, `retrievability_tier`, `audit_area`).

**Failure taxonomy** — defined in `docs/product/failure-taxonomy.md` (Q1). Phase 1 artefacts each category can target:
| Category | Phase 1 artefacts |
|---|---|
| `wrong_period` | trial balance, bank statement, aging |
| `wrong_entity` | trial balance, bank statement |
| `incomplete` | general ledger, bank statement |
| `unbalanced` | trial balance |
| `does_not_tie` | aging, bank statement |
| `duplicate` | general ledger, bank statement |
| `stale` | trial balance, aging |
| `wrong_currency` | bank statement |
| `altered` | bank statement, aging |
| `irrelevant` | any (artefact served for a request item of another kind) |
| `unreadable` | any export (CSV, XLSX) |

**Adversarial categories** — same document (Q2): `prompt_injection`, `addressed_instruction`, `formula_injection`, `unicode_deception`, `oversized_field`, `lookalike_name`.

## 8. Interfaces
Python only: `abacus_tools.synthetic.generate`, the dataclasses above, `GENERATOR_VERSION`, writers `to_csv`, `to_json`, `to_xlsx`. No HTTP or CLI interface in phase 1 (the `make seed-staging` entry point `abacus_tools.synthetic.seed` stays unimplemented). `abacus` never imports `abacus_tools` (ADR-101); SPEC-000's fake connector consumes generator **exports** loaded as test fixtures, so production code stays independent.

## 9. Authorisation and tenancy
N/A — offline tooling with no users, tenants or stored data. Generated clients carry no `tenant_id`; tests that load them into the database assign a test firm.

## 10. AI behaviour
N/A — no model calls. Adversarial payloads are static strings authored in the repository.

## 11. Integrations
None. `openpyxl` (already approved, ADR-042) for XLSX.

## 12. Edge cases and failure modes
- `months` 1 to 36; `entities` 1 to 5; anything else raises `ValueError`
- Unknown flaw or adversarial category raises `ValueError` listing valid ones
- Conflicting flaws on one artefact (e.g. `unbalanced` and `unreadable` on the same TB) raise `ValueError`
- Leap years, month-end on weekends, a fiscal year not starting in January
- Generation must not read the clock, environment, locale or filesystem (determinism)

## 13. Security and privacy
- No real data ever: names from built-in word lists; identifiers in reserved or invalid ranges (AC-13); exports pass `secrets_scan`
- Adversarial payloads are inert strings — no executable files, no macros in XLSX, no external links
- Generated output written to the repository (golden fixtures) is small and reviewed like code

## 14. Audit trail and evidence integrity
N/A for the generator itself (no state changes in the product). Generated exports are fixtures; when SPEC-000 ingests them as evidence, the product's provenance and audit rules apply.

## 15. Observability
None beyond exceptions with clear messages.

## 16. Performance and scale
AC-17 for the default size. `size="large"` (~20,000 entries/month) for load-test phase 2 must stay linear; no target in phase 1.

## 17. UX
N/A.

## 18. Test plan
| AC | Type |
|---|---|
| 1–3 | unit (golden hashes, subprocess run) |
| 4–7 | property (Hypothesis over seeds and parameters) |
| 8–12 | unit per category, property for "invariants hold when no flaw targets them" |
| 13–14 | unit; runs `secrets_scan` on exports |
| 15–16 | unit |
| 17 | unit with a time budget |

## 19. Rollout
Merged as tooling; no runtime change. SPEC-000 tasks switch to generator fixtures.

## 20. Open questions
- [x] **Q1 — Failure taxonomy.** ADR-081 and ADR-085 refer to a failure taxonomy that no document defines. Approve the eleven categories in §7 (or edit), and should the taxonomy live in its own doc (`docs/product/failure-taxonomy.md`, protected) since screening, evaluations and the generator all depend on it? **Recommendation:** yes, its own protected doc, created with this spec. **Approved 2026-10-06: eleven categories; own protected doc `docs/product/failure-taxonomy.md`.**
- [x] **Q2 — Adversarial categories.** Approve the six in §7. **Recommendation:** approve; extend with ADR-064's list when the screening agent is specified. **Approved 2026-10-06: six categories, in the same doc.**
- [x] **Q3 — Naming.** ADR-085's example is `synthetic.company(...)`, but the glossary forbids "company" for clients and client entities. **Recommendation:** `abacus_tools.synthetic.generate(...)` returning a `SyntheticClient` with `client_entities`; ADR-101's mapping already reads ADR-085's example loosely. Also: should generated client names carry a visible marker (e.g. suffix "(Synthetic)") so they can never be mistaken for real clients in staging? **Recommendation:** yes. **Approved 2026-10-06: `abacus_tools.synthetic.generate(...)` → `SyntheticClient`; names end in " (Synthetic)".**
- [x] **Q4 — Documents (phase 2).** Invoices, contracts and bank statements as PDFs need a PDF writer (none approved; `pdfplumber` is pending and reads only). **Recommendation:** defer to phase 2 and decide the library then. **Approved 2026-10-06: deferred to phase 2.**
- [x] **Q5 — Multiple entities.** With `entities > 1`, generate intercompany transactions that eliminate on consolidation? **Recommendation:** independent entities in phase 1; intercompany in phase 2. **Approved 2026-10-06: independent entities in phase 1.**
- [x] **Q6 — Risk zone.** Tooling, but it defines the expected answers every evaluation and screening test relies on. **Recommendation:** amber. **Approved 2026-10-06: amber.**

## 21. Future / explicitly deferred
- Phase 2: PDFs and other documents, emails and messages, `make seed-staging` through the API, `size="large"` load profiles, intercompany, multi-currency, connector-specific payload shapes (QuickBooks, Xero …) for recorded responses (ADR-044)
