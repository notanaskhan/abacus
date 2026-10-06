---
id: TASK-003
title: Synthetic client generator, phase 1
spec: SPEC-001
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17]
risk_zone: amber
status: in-progress
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
- [x] Plan approved by human (founder, 2026-10-06: "create the file, proceed")
- [x] Approval file `work/approvals/TASK-003.yaml` written by the agent at the founder's explicit instruction (2026-10-06)
- Approved by founder: paths under *Approval file text*, expires 2026-10-20

Steps:
1. [x] **Protect the taxonomy** (before any code relies on it): add `docs/product/failure-taxonomy.md` to `.claude/hooks/_protected.py`, `.github/CODEOWNERS`, `docs/architecture/protected-paths.md` (policy files bullet); extend `backend/tests/unit/quality/test_hooks.py`'s blocked-path cases with it — **that test file is protected; listed in the approval**.
2. [x] **Model** `synthetic/model.py`: frozen dataclasses per the contract; `Decimal` amounts quantised to `0.01`.
3. [x] **Randomness** `synthetic/rng.py`: `stream(seed, name) -> random.Random` seeded from `sha256(f"{seed}:{name}")` — independent sub-streams (SPEC-001 §6.2); no global `random`, clock, env, locale or filesystem reads.
4. [x] **Names** `synthetic/names.py`: built-in word lists for client, vendor, customer, bank and employee names; addresses on fictitious streets; reserved identifiers (AC-13); `" (Synthetic)"` suffix (AC-14).
5. [x] **Ledger** `synthetic/ledger.py`: chart of accounts (~60 accounts, five types, standard code ranges), opening balances, monthly activity (sales, purchases, receipts, payments, payroll, depreciation, accruals), month-end and year-end close; every entry balanced by construction (AC-4, AC-5).
6. [x] **Derived artefacts** `synthetic/artefacts.py`: month-end trial balances, monthly bank statements with labelled reconciling items, AR/AP agings at period end (AC-6, AC-7).
7. [x] **Request list** `synthetic/requests.py` (AC-16).
8. [x] **Flaws** `synthetic/flaws.py` and **adversarial** `synthetic/adversarial.py`: applied to copies of derived artefacts, recorded in the manifest (AC-8 to AC-12).
9. [x] **Exports** `synthetic/export.py`: CSV, JSON, and XLSX written **without openpyxl** — a minimal SpreadsheetML writer over `zipfile` with fixed timestamps and inline strings, so output is byte-identical (AC-1, AC-15). Reason: openpyxl stamps creation times and zip entry times, and has no type stubs under pyright strict (`types-openpyxl` is not approved).
10. [x] **Golden hash** fixture for the default client (AC-1, AC-3) and a 5-second budget test (AC-17).
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

#### Contract revision 1 (2026-10-06, from the stage 4 architecture review)
- No journal entry is dated before `period_start` (a mid-month or weekend `start` begins activity on `start`); after each fiscal-year-end close every revenue and expense account balance is zero at that date.
- `TrialBalance.client_entity: str` — the name of the entity whose books it is (a `wrong_entity` TB carries the other entity's name). TB CSVs gain a `client_entity` column after `as_of`.
- `wrong_currency` (bank statement): opening and line amounts converted, running balances and closing recomputed — the statement is internally consistent (opening + Σ = closing, running balances correct); only the tie to the USD cash account fails.
- `"stale:trial_balance"` (or plain `"stale"`) with `months=1` raises `ValueError` (no earlier month end).
- Adversarial content never skips a category: if the usual carrier is empty, another statement (bank) or the AR aging (`unicode_deception`) carries it, and the manifest names the actual artefact.
- XLSX: one sheet per CSV file **plus a `manifest` sheet** (AC-15); amounts are numeric cells only in amount columns; characters XML 1.0 cannot carry are written as OOXML `_xHHHH_`, and a literal `_xHHHH_` as `_x005F_xHHHH_`. Values are never truncated: the `oversized_field` payload exceeds Excel's 32,767-character display limit on purpose.
- Output changed: `GENERATOR_VERSION` = `1.1.0`.

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

- `2026-10-06` — Steps 1–10 done. Taxonomy protected (hook, CODEOWNERS, protected-paths.md; hook test case added — 116 pass). Generator implemented; independent tests (Sonnet, from the contract, implementation unseen) 271 cases: all pass after pinning the golden hash.
  - Contract clarifications sent to the test author (recorded here): export files are named by the period the artefact is meant to cover (a stale TB would otherwise overwrite the previous month's file); TB and aging CSVs carry an `as_of` column; plain `irrelevant`/`unreadable` target `general_ledger`, `irrelevant:trial_balance` is invalid; bank locations read `bank_statement <account> for <YYYY-MM>`; `AgingLine.total` is a stored field; bank flaws hit the first account's last statement (positional).
  - Bugs found in my own smoke run before tests landed: flawed statement lookup broke after `wrong_period`/`wrong_entity` changed its fields (now positional); `irrelevant` looked up its request item after changing it; locations like `4417-2938 2025-02` tripped PII-003 as a card number (now `… for 2025-02`).
  - AC-17 failed under coverage (branch tracing ~4x slower). Fixed in code, not the test: JSON without `indent` (the C encoder), cached dataclass fields, precomputed XLSX column letters — 1.3 s → 0.75 s. Output changed, so `GENERATOR_VERSION` 1.0.0 → 1.0.1 and the golden hash re-pinned in the same change (AC-3 working as designed).
  - Only edits to the independent tests: pinning `GOLDEN_VERSION`/`GOLDEN_SHA256` (the contract's designated step) and annotating both as `str` so pyright doesn't flag the "still pending" guard as always false.
  - **Blocked:** ruff S311 flags `random.Random` in `synthetic/rng.py`. See Q1.

- `2026-10-06` — Q1 applied: S311 exempt for `abacus_tools/synthetic/**`; S101/S314/S603 for `tests/unit/synthetic/**`. Test author reverted to `subprocess.run` and `ET.fromstring`. New banned pattern **SIDESTEP-001** (ADR-083: lints grow when an agent repeats a mistake) flags `create_subprocess_exec`/`_shell` and `XMLPullParser`, which ruff's S rules miss; 43 tests written independently from a one-paragraph contract. `make check` exit 0; suite 68 s (was ~160 s with the asyncio workaround).

- `2026-10-06` — Stage 4 architecture/test review (Sonnet): determinism, ADR-101 and invariants clean across many parameter sets; fixed via *Contract revision 1*:
  - **Blocker:** mid-month `start` posted activity before the opening entry and the year-end close missed it (P&L not zero at FYE for `start=2025-01-15`, `2025-02-15`, `2024-02-29`, `2025-12-31`). Activity now begins on `start`; all counterexamples verified closed.
  - **Blocker:** XLSX could carry XML-illegal characters — now OOXML `_xHHHH_` escaping. Oversized cells (> 32,767 chars) kept exact on purpose (AC-12); documented in `to_xlsx`.
  - Manifest sheet in XLSX (AC-15); `TrialBalance.client_entity` (wrong_entity detectable mechanically); `wrong_currency` internally consistent; `stale` TB at months=1 rejected; adversarial never skips a category; per-flaw RNG streams; numeric XLSX cells only in amount columns (`fullmatch`); `post()` raises on degenerate entries; decimal context pinned.
  - Not changed (nit): `irrelevant:<artefact>` counts against that artefact's one-flaw limit — harmless.
  - Tests extended independently (Hypothesis now reaches year-end closes, mid-month/weekend/Feb-29/July-fiscal starts; flaw tests also at months=1). `GENERATOR_VERSION` 1.1.0, golden re-pinned. `make check` exit 0: 1,187 tests, 87 s, coverage 98 %.

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
- [x] **Q1 — Lint exemptions in `backend/pyproject.toml` (blocking `make check`).** (a) `"src/abacus_tools/synthetic/**" = ["S311"]` — seeded non-cryptographic randomness is the point of the generator (ADR-085). (b) The independent test author avoided S603 and S314 by switching APIs (`asyncio.create_subprocess_exec` instead of `subprocess.run`; `XMLPullParser` instead of `ET.fromstring`). Both are safe here (running this interpreter; parsing our own XLSX), but sidestepping a lint by API choice is what our "exceptions only via protected config" rule forbids. **Recommendation:** add `backend/pyproject.toml` to the approval; add (a), plus `"tests/unit/synthetic/**" = ["S101", "S314", "S603"]`; have the test author switch back to the plain APIs; add a banned pattern for `asyncio.create_subprocess_exec`/`XMLPullParser` outside allowed paths so the sidestep can't recur. **Approved 2026-10-06.** Agent added `backend/pyproject.toml`, `banned_patterns.py` and `test_banned_patterns.py` to the approval file at the founder's instruction.

## Handoff
- **Current state:** Steps 1–10 done; `make check` exit 0. Committed, not pushed.
- **Exact next step:** Cross-model review (stage 4), fix findings, push, PR, confirm CI.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** branch protection off.
