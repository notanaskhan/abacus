---
id: TASK-003
title: Synthetic client generator, phase 1
spec: SPEC-001
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17]
risk_zone: amber
status: awaiting-plan-approval
branch: spec-001-synthetic-generator
worktree:
created: 2026-10-06
updated: 2026-10-06
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Build `abacus_tools.synthetic` as specified in SPEC-001 (phase 1): a deterministic, accounting-correct synthetic client with labelled flaws and adversarial content, exported to CSV, JSON and XLSX; and protect the new failure taxonomy.

## Scope
**In**
- `backend/src/abacus_tools/synthetic/` package (generator, model, flaws, adversarial payloads, exporters)
- Protect `docs/product/failure-taxonomy.md` (hook list, CODEOWNERS, protected-paths.md)
- Tests from the interface contract below, written independently (ADR-078)

**Out**
- Everything SPEC-001 §21 defers (PDFs, `make seed-staging`, load profiles, intercompany, multi-currency, connector payload shapes)
- Wiring the fake connector — SPEC-000 tasks

## Context to load
- Spec: `docs/specs/SPEC-001-synthetic-generator.md` (all)
- `docs/product/failure-taxonomy.md`, `docs/product/glossary.md` (requests and evidence, connections and ledger)
- ADRs: ADR-085, ADR-042 (deterministic rendering), ADR-050, ADR-052, ADR-064, ADR-078, ADR-101
- Reference pattern: `abacus_tools.quality` modules and tests (frozen dataclasses, exact assertions, pyright strict)

## Plan
- [ ] Plan approved by human (required for amber)
- [ ] Approval file `work/approvals/TASK-003.yaml` with the paths below

Steps:
1. [ ] **Protect the taxonomy** (before any code relies on it): add `docs/product/failure-taxonomy.md` to `.claude/hooks/_protected.py`, `.github/CODEOWNERS`, `docs/architecture/protected-paths.md` (policy files bullet); extend `backend/tests/unit/quality/test_hooks.py`'s blocked-path cases with it — **that test file is protected; listed in the approval**.
2. [ ] **Model** `synthetic/model.py`: frozen dataclasses per the contract; `Decimal` amounts quantised to `0.01`.
3. [ ] **Randomness** `synthetic/rng.py`: `stream(seed, name) -> random.Random` seeded from `sha256(f"{seed}:{name}")` — independent sub-streams (SPEC-001 §6.2); no global `random`, clock, env, locale or filesystem reads.
4. [ ] **Names** `synthetic/names.py`: built-in word lists for client, vendor, customer, bank and employee names; addresses on fictitious streets; reserved identifiers (AC-13); `" (Synthetic)"` suffix (AC-14).
5. [ ] **Ledger** `synthetic/ledger.py`: chart of accounts (~60 accounts, five types, standard code ranges), opening balances, monthly activity (sales, purchases, receipts, payments, payroll, depreciation, accruals), month-end and year-end close; every entry balanced by construction (AC-4, AC-5).
6. [ ] **Derived artefacts** `synthetic/artefacts.py`: month-end trial balances, monthly bank statements with labelled reconciling items, AR/AP agings at period end (AC-6, AC-7).
7. [ ] **Request list** `synthetic/requests.py` (AC-16).
8. [ ] **Flaws** `synthetic/flaws.py` and **adversarial** `synthetic/adversarial.py`: applied to copies of derived artefacts, recorded in the manifest (AC-8 to AC-12).
9. [ ] **Exports** `synthetic/export.py`: CSV, JSON, and XLSX written **without openpyxl** — a minimal SpreadsheetML writer over `zipfile` with fixed timestamps and inline strings, so output is byte-identical (AC-1, AC-15). Reason: openpyxl stamps creation times and zip entry times, and has no type stubs under pyright strict (`types-openpyxl` is not approved).
10. [ ] **Golden hash** fixture for the default client (AC-1, AC-3) and a 5-second budget test (AC-17).
11. [ ] **Verify**: `make check` exit 0; mutation spot-checks on invariants; gate-break (a deliberately unbalanced entry fails AC-4; a clock read breaks AC-1).

Files to create or change:
- `backend/src/abacus_tools/synthetic/{__init__,model,rng,names,ledger,artefacts,requests,flaws,adversarial,export}.py`
- `backend/tests/unit/synthetic/…`, `backend/tests/property/synthetic/…` (independent author)
- `.claude/hooks/_protected.py`, `.github/CODEOWNERS`, `docs/architecture/protected-paths.md`, `backend/tests/unit/quality/test_hooks.py` *(protected)*

### Interface contract (tests are written against this — ADR-078)

Import everything from `abacus_tools.synthetic`.

**Entry point**
`generate(seed: int, *, entities: int = 1, months: int = 12, start: date = date(2025, 1, 1), size: Literal["small"] = "small", flaws: Sequence[str] = (), adversarial: bool = False) -> SyntheticClient`
- `ValueError` if `entities` ∉ 1–5, `months` ∉ 1–36, an unknown flaw or artefact, a flaw on an artefact it can't target (SPEC-001 §7 table), or two flaws on the same artefact. Messages name the valid options.
- A flaw is `"<category>"` (targets the category's first artefact in the SPEC-001 §7 table) or `"<category>:<artefact>"`. Artefacts: `general_ledger`, `trial_balance`, `bank_statement`, `ar_aging`, `ap_aging` (`aging` in the spec table means either; plain category → `ar_aging`).
- Flaws target the **first** client entity, the **period-end** trial balance, the **last month's** statement of the **first** bank account, and the period-end agings.
- `GENERATOR_VERSION: str`; `FAILURE_CATEGORIES: tuple[str, ...]` (the 11 code names, taxonomy order); `ADVERSARIAL_CATEGORIES: tuple[str, ...]` (the 6, taxonomy order).

**Model** (all frozen dataclasses; amounts `Decimal` with exponent `-2`; tuples, not lists)
- `SyntheticClient`: `seed: int`, `generator_version: str`, `name: str`, `client_entities: tuple[ClientEntity, ...]`, `request_list: RequestList`, `manifest: Manifest`.
- `ClientEntity`: `name: str`, `ein: str` (`NN-NNNNNNN`), `currency: str` (`"USD"`), `period_start: date`, `period_end: date`, `accounts: tuple[Account, ...]`, `journal_entries: tuple[JournalEntry, ...]`, `trial_balances: tuple[TrialBalance, ...]` (one per month end, ascending), `bank_accounts: tuple[BankAccount, ...]` (≥ 1), `bank_statements: tuple[BankStatement, ...]`, `ar_aging: Aging`, `ap_aging: Aging`.
- `Account`: `code: str`, `name: str`, `type: Literal["asset","liability","equity","revenue","expense"]`.
- `JournalEntry`: `id: str`, `date: date`, `memo: str`, `lines: tuple[JournalLine, ...]` (≥ 2). `JournalLine`: `account_code: str`, `debit: Decimal`, `credit: Decimal` (one of them zero, neither negative), `description: str`, `counterparty: str | None`.
- `TrialBalance`: `as_of: date`, `lines: tuple[TrialBalanceLine, ...]`; properties `total_debits`, `total_credits`. `TrialBalanceLine`: `account_code`, `account_name`, `debit: Decimal`, `credit: Decimal` (net balance on its natural side; one is zero).
- `BankAccount`: `name: str`, `routing_number: str` (9 digits), `account_number: str`, `gl_account_code: str`.
- `BankStatement`: `account_number: str`, `period_start: date`, `period_end: date`, `currency: str`, `opening_balance`, `closing_balance`, `lines: tuple[BankLine, ...]`, `reconciling_items: tuple[ReconcilingItem, ...]`. `BankLine`: `date`, `description: str`, `amount: Decimal` (signed), `balance: Decimal`. `ReconcilingItem`: `kind: Literal["outstanding_cheque","deposit_in_transit"]`, `description: str`, `amount: Decimal` (positive).
  - Unflawed invariants: opening + Σ amounts = closing; each line's `balance` is the running balance; GL cash balance at `period_end` = closing + Σ deposits in transit − Σ outstanding cheques.
- `Aging`: `kind: Literal["ar","ap"]`, `as_of: date`, `control_account_code: str`, `lines: tuple[AgingLine, ...]`; property `total`. `AgingLine`: `counterparty`, `current`, `days_1_30`, `days_31_60`, `days_61_90`, `over_90`, property `total`.
  - Unflawed invariant: `total` = control account balance at `as_of` (AR as debit balance, AP as credit balance, both positive).
- `RequestList`: `items: tuple[RequestItem, ...]`. `RequestItem`: `id: str`, `description: str`, `audit_area: str`, `retrievability_tier: Literal["A","B","C","D","E"]`, `artefact: str | None` (an artefact name above, or `None`). Exactly one item has `artefact == "trial_balance"`, tier `"A"`.
- `Manifest`: `flaws: tuple[Flaw, ...]`, `adversarial: tuple[AdversarialPayload, ...]`. `Flaw`: `category`, `artefact`, `client_entity: str` (entity name), `location: str` (human-readable, e.g. `"trial_balance 2025-12-31"`), `detection: Literal["mechanical","ai"]` (per the taxonomy doc's first-listed method). `AdversarialPayload`: `category`, `artefact`, `field: str`, `location: str`, `payload: str`.

**Flaw effects** (what tests can check on the flawed artefact; everything else stays unflawed)
- `unbalanced` (TB): `total_debits != total_credits`; journal entries unchanged and balanced.
- `wrong_period` (TB/aging: `as_of` one year earlier; bank statement: `period_start`/`period_end` one year earlier).
- `wrong_entity`: the artefact's identifying fields (bank `account_number`, TB/aging lines) belong to a different synthetic entity than `client_entities[0]`.
- `incomplete` (GL: at least one month has no journal entries; bank statement: at least one line removed, so opening + Σ ≠ closing or dates have a gap).
- `does_not_tie` (aging: `total` ≠ control account balance; bank statement: the GL-cash invariant fails).
- `duplicate` (GL: at least one entry `id` appears twice; bank statement: a line repeated).
- `stale` (TB/aging: `as_of` before `period_end` by ≥ 1 month).
- `wrong_currency` (bank statement): `currency != "USD"` is **not** set — amounts converted while `currency` stays `"USD"` (that is the flaw); detectable because the GL-cash invariant fails.
- `altered` (bank statement: some line's running `balance` is inconsistent; aging: some line's buckets don't sum to its `total`).
- `irrelevant`: the trial-balance request item's `artefact` points at another artefact kind.
- `unreadable`: that artefact's CSV export is empty (0 bytes) and its XLSX sheet is missing.

**Adversarial** (`adversarial=True`): at least one payload per category in `ADVERSARIAL_CATEGORIES`, each findable verbatim in the field and artefact the manifest names; `oversized_field` payload ≥ 65,536 characters; `formula_injection` payload starts with one of `= + - @`; `unicode_deception` contains a character in U+202A–U+202E, U+2066–U+2069 or U+200B–U+200D, or a non-ASCII homoglyph.

**Exports**
- `to_csv(client, directory: Path) -> tuple[Path, ...]`, `to_json(client, directory: Path) -> Path`, `to_xlsx(client, path: Path) -> Path`. Paths returned sorted.
- CSV: one subdirectory per client entity (slug of the name); files `chart_of_accounts.csv`, `general_ledger.csv`, `trial_balance_<YYYY-MM-DD>.csv` per TB, `bank_statement_<account_number>_<YYYY-MM>.csv` per statement, `ar_aging.csv`, `ap_aging.csv`; top level `request_list.csv`, `manifest.json`. UTF-8, `\n` line endings, header row, amounts as plain decimal strings (`"1234.50"`).
- JSON: one file `client.json`, keys sorted, amounts as strings, dates ISO.
- XLSX: one workbook; one sheet per CSV file (sheet names ≤ 31 chars, unique); a valid OOXML zip readable with `zipfile` + `xml.etree`; byte-identical across runs.
- All three byte-identical for identical inputs on Linux and macOS.

**Identifiers** (AC-13): EINs use prefix `00`; routing numbers are 9 digits failing the ABA checksum; emails end `@example.com` or `@example.org`; phone numbers `555-01NN`; no SSNs or card numbers are generated. Every client and client entity name ends with `" (Synthetic)"`. `secrets_scan.scan(dir, files=[…all exported files…]) == []` for any seed, with or without flaws, with or without adversarial content.

### Approval file text
```yaml
task: TASK-003
approved_by: founder
expires: 2026-10-20
paths:
  - .claude/hooks/_protected.py
  - .github/CODEOWNERS
  - docs/architecture/protected-paths.md
  - backend/tests/unit/quality/test_hooks.py
reason: TASK-003 — protect the failure taxonomy (SPEC-001 Q1)
```
`docs/product/failure-taxonomy.md` itself is created on this branch before it becomes protected (step 1), so it needs no approval.

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation — n/a, offline tooling
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals — n/a
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed
- [ ] Both CI jobs pass on the PR

Commands:
```
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| none | | XLSX written with the standard library (step 9) | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-06` — SPEC-001 approved by founder with all recommendations (Q1–Q6); failure taxonomy written to `docs/product/failure-taxonomy.md`. Task plan written. No code.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| XLSX via a minimal standard-library writer, not openpyxl | Byte-identical output (openpyxl stamps times) and no unapproved `types-openpyxl` | no |
| Sub-streams seeded from `sha256(seed:name)` | Adding a sub-generator never shifts another's output | no |
| Flaws applied to copies of derived artefacts | The ledger stays correct, so every unrelated invariant still holds | no |

## Gotchas and discoveries
- `secrets_scan` PII-003 flags 13–19 digit Luhn-valid numbers: entry ids and account numbers must stay short or non-numeric.
- `secrets_scan` PII-002 flags EINs with assigned prefixes only in data files; generated EINs use `00`, which is never assigned.

## Questions for the human
- None blocking. SPEC-001 Q1–Q6 answered.

## Handoff
- **Current state:** Plan written; not approved. No code. Branch `spec-001-synthetic-generator` holds SPEC-001 (approved), the failure taxonomy and this file.
- **Exact next step:** Founder approves the plan and creates (or tells the agent to create) `work/approvals/TASK-003.yaml`. Then step 1, and in parallel an independent session writes tests from the contract.
- **Uncommitted or partial work:** this file, SPEC-001 approval, failure taxonomy.
- **Known failing checks:** none.
- **Open issues:** branch protection off; "Allow GitHub Actions to create and approve pull requests" on.
