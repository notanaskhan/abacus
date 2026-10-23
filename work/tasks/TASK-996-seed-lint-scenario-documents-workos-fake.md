---
id: TASK-996
title: Seed contamination lint and scope registration, E0 scenario documents and fake-model responses, the WorkOS fake (F-04-T09, F-04-T25, F-04-T27)
spec: SPEC-307
acceptance_criteria: [AC-5, AC-6]
risk_zone: amber
status: done
epic: F-04
plan_key: F-04-T09; F-04-T25; F-04-T27
branch: s6-f04-lint-docs-workos
created: 2026-10-23
updated: 2026-10-23
---

## Objective
- T09: "CI fails on kit sample data, variant canonical names or excluded-scope rows in fixtures or the scenario."
- T25: "E0 evidence screens with verified citations, one planted Uncited value renders, and staging is reloaded."
- T27: "Local stack walks SHL-06b/c/e/f/g and POR-01a/b/c/f/g and the WorkOS adapter contract tests pass against the fake."

## Plan (amber: written before the code)
- **T09, lint L10:** `abacus_tools/quality/seed_contamination.py` scans the scenario package, `apps/web/src/fixtures/` and `apps/web/e2e/journeys/` for F-04.13's kit sample data and the gaps.md §4 variant spellings; run from `make check-fast`. **Scope registration (F-04.14):** `scope_guards.SCENARIOS` adds `abacus_tools/synthetic/scenarios` to the guard's Python scan (the old `REPO/scenarios` root never existed).
- **T25:** `brightwater_hale/documents.py` builds three deterministic Northwind A1 documents from blueprint §9.4 with a fixed region per citeable value; five `responses/*.json` files; `responses.PLANTED_UNSUPPORTED`. `abacus_tools.synthetic.documents.positioned_pdf` writes text at fixed places.
- **T27:** `abacus_tools/fakes/workos.py`: `FakeWorkOsPortalIdp` (the `PortalIdp` port) and `StaffSignIn` (AuthKit's hosted email code, second factor and lockout). `oidc_server.py` serves the staff pages and two harness readers. The portal contract suite gains the fake as a provider. The fullstack persona adapter signs scenario staff in by email code. `identity/api.py` re-exports the port's names, so the fake reaches the port through the module's public surface (BOUND-001).
- **Migrations, flags, matrix:** none. **Dependencies:** none (pdfplumber and openpyxl are already runtime dependencies).
- **Tests first:** `tests/unit/quality/test_seed_contamination.py`, `tests/unit/scenarios/test_scope_registration.py`, `tests/unit/scenarios/test_scenario_documents.py`, `tests/unit/fakes/test_workos_fake.py`, and the contract suite's new parameter.
- **Rollback:** revert the commit. Nothing reads the documents or responses outside tests yet, and the chooser on the local sign-in page is unchanged.

## What changed
- **T09.** The lint catches Elena Ruiz, "Ridgeview Partners", the Whitcombes' Schedule E, the kit inbox address, "17% (4 / 24)", "86 of the 119 returns", 21 integrations, the Austin office, 126 engagements and the 13-task close run. It also catches "Claire & Jonah Feld" and the legal names with the comma or full stop dropped. Thomas Whitcombe and the short forms in running text pass. The repository is clean. The scenario's Python and data are now scanned by the D1–D10 guard. A data test builds E0 and the Sep 24 snapshot and finds no single audit, Yellow Book, ESG, FFIEC, NYDFS or OFAC row.
- **T25.** Three documents:
  - Harborline's summary of net trust assets (PDF);
  - Keystone's annual loan balance roll-forward (PDF);
  - the plan's trust-basis trial balance in the platform's rendered layout (XLSX).

  Each answers a request on the Northwind PBC list, or the Trial Balance workpaper. Every figure is blueprint §9.4's, on the trust basis E0 has: net assets 16,812,400.00. Regions are computed from where the writer puts the text (page rectangles in the C4 `Rect` form, or cells), and a test reads every one back from the bytes.

  Five response files: the screener for the trial balance, the upload reviewer and the matcher for each PDF. Every citation resolves to a region and verifies through the product's own verifiers (`agents.citations.verify`, `agents.document_citations.verify`). The one exception is the planted value: contributions 1,366,900.00 cited at D11, which holds 1,318,300.00, so `value_mismatch` makes it "Uncited".
- **T27.** The staff walk, as the tests drive it on the local sign-in server:
  - b: the work email gets a code at the sink-routed address, and `mail().latest()` and `/_harness/code` read it;
  - c: "Two-step verification" and "Trust this device for 30 days";
  - g: a 303 to the BFF callback with a single-use code; the token's subject is `scenario-hannah-leclerc`, with the person's email and `amr` mfa;
  - e: "That code didn't match. 4 attempts left.";
  - f: the fifth wrong code reads "Account locked", "Try again at 9:54 AM, or ask Felix Andersen (IT / Security) to unlock your account."

  Wrong authenticator codes count toward the same lock. An unknown email gets the same page and no mail.

  The portal fake passes the full `PortalIdp` contract suite: 4 more cases, 15 in the suite. It uses WorkOS-shaped ids, has readers for the harness, and seeds the scenario's portal people on the sink, with a TOTP factor for owners. It has no email method.

## Not done, and why
- **T25 staging reload:** there is no staging environment. Reloading it needs R0 staging (Q-01) and `make seed-staging` as an ECS one-off task.
- **T25 "renders":** SHL-09 (field provenance popover) and SHL-10 (approve agent output) are not built. The data, and the planted Uncited value, are ready for the epic that builds them.
- **T25, a wiring gap:** the screener's, reviewer's and matcher's contexts do not name the document's SHA-256 today. So a recorded response keyed by document hash answers only a request that carries it (`FakeModel._recorded_for`). Threading the hash into `ContextBuilder.sources` is the agents module's change.
- **T27 portal walk POR-01a/b/c/f/g on the local stack:** the portal BFF (`/v1/portal/auth/*`, P-08-T10) and portal MFA (P-08-T17) are not built. The portal's own code attempts (3, then POR-01g) and the MFA lock live there, not in the provider (DEC-155), so the fake rightly has none. POR-01 walks in fixture mode only.
- **T27 staging and canary sign-in:** these use real WorkOS. `registerHostedSignIn` is not registered, because AuthKit's hosted pages have not been seen yet. Doing it needs staging WorkOS persona users on the sink domain.
- **T27 fullstack browser walk:** the adapter's email-code path was not run in a browser. It needs `make dev` and `make seed-demo`; the flow is proven at the HTTP level by `test_workos_fake.py`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-205 | The WorkOS fake's shape: lock, delivery, unknown emails, the portal half's limits | no |
| DEC-206 | Scenario documents on the trust basis; the planted value; matcher refs | no |

## Progress log
- 2026-10-23: built in one PR (PR A of the S6 F-04 batch). The new suites (35 + 15 + 53 test cases across lint, documents, scope, contract and fakes) pass. Ruff and pyright are clean.
