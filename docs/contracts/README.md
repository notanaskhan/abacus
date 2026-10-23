# Contract register

The register of the plan's 21 cross-module contracts, C1 to C21. Source: `docs/plan/01-strategy-roadmap.md` §1.3.2 (register) and `docs/plan/epics/F-03.md` §8.1 and §3.10. One file per contract: `docs/contracts/<name>.md`, from `_TEMPLATE.md`. Consumer contract tests live in `backend/tests/contracts/<name>/`.

Sprint dates: Sn starts Mon 2026-10-19 + 14n days (S0 2026-10-19, S1 2026-11-02, S3 2026-11-30 ...). The freeze date is the start of the freeze sprint.

Status values: `planned` (no stub), `stub` (models, 501 routes, matrix actions, flag and contract doc landed, not frozen), `frozen` (version fixed, breaking changes need vN+1), `live` (implemented behind the contract), `superseded`.

## Register

| C | Contract | File | Provider (epic) | Consumers | Freeze sprint | Freeze starts | Version | Status |
|---|---|---|---|---|---|---|---|---|
| C1 | Work item and engagement lifecycle (8 states, G1-G3 facts, per-type gate policy) | `work-items.md` | F-03 | every module | S1 | 2026-11-02 | v1 | frozen (F-03-T19, 2026-10-21) |
| C2 | Status registry: YAML to StrEnum, OpenAPI enums, `status.ts` | `status-registry.md` | F-03 (YAML authored in F-03-T04, codegen F-03-T09) | all | S1 | 2026-11-02 | v1 | frozen (F-03-T19, 2026-10-21) |
| C3 | Review grammar: suggestion and change set, decision, sign_off (content hash, staleness, segregation), issue, checkpoint, field_value_version, human_gate | `review-grammar.md` | P-04 | A-*, T-*, C-*, I-01 | schema S3, services S12 | 2026-11-30, 2027-04-05 | v1 | stub (stubs 1 and 2: P-04-T07, T08, 2026-10-22; consumer tests P-04-T09, 2026-10-22; stub 3: P-04-T11, 2026-10-23, additive to v1, consumer tests P-04-T12, 2026-10-23; schema v1 freeze scheduled Fri 2026-12-11, see below) |
| C4 | Citation v2, viewer manifest, regions, masked PII and logged reveal | `c04-citations-viewer.md` | P-03 | every trace surface | S5 | 2026-12-28 | v1 | stub (contract doc P-03-T01, 2026-10-23; models and fixture routes P-03-T02; freeze S5) |
| C5 | Requests and binders; portal scopes (`client_access_grant`, role union) | `c5-requests-binders.md`; portal half `portal-identity.md` | P-06, P-08 (schema half in F-03-T14, T15, T26); portal read models | A-01, R-01, T-02, C-01 | S3 | 2026-11-30 | v1; portal half v1.1 | stub (binders and requests half, BND/SHL-14 family: P-06-T01, 2026-10-22; portal half v1.1, POR-01/POR-02: P-08-T01, 2026-10-23) |
| C6 | Agent runs: v1 read API; v2 run and step events over SSE | `agent-runs.md` | P-09, P-10 | dock, trace, Workbench, Today | v1 S12, v2 S30 | 2027-04-05, 2027-12-13 | v1 | planned (v0 run list, trace and JSON export live: SPEC-318, TASK-461, 2026-10-22) |
| C7 | Envelope service: record mode, then DocuSign embedded with provider ID Verification; evidence package; gate events | `envelopes.md` | N-02 | ENG-04, SIG-*, POR-06, TAX-12, AUD-21, NOT-03 | record S14, DocuSign S17 | 2027-05-03, 2027-06-14 | v1 | planned |
| C8 | Adjustments: proposed entries (8 states), threshold-policy versions, named-human batch approval | `adjustments.md` | A-06 | EBP-06, T-05, C-02, A-09 eliminations | S24 | 2027-09-20 | v1 | planned |
| C9 | Ledger: TB layers, groupings and FS-line taxonomy, account mapping | `ledger.md` | A-02, A-03 | A-04, A-06, T-05, C-01, A-10 | layers S10, taxonomy S20 | 2027-03-08, 2027-07-26 | v1 | planned |
| C10 | Deliverables and release registry with download audit | `deliverables.md` | R-02 | A-07, T-02 (K-1), C-02, X-01 | S29 | 2027-11-29 | v1 | planned |
| C11 | Deterministic PDF/DOCX renderer; templates in the database | `renderer.md` | P-11 | ENG-04, AUD-20 to AUD-23, TAX-12, NOT-03, CLS-08, FSP-06 | S18 | 2027-06-28 | v1 | planned |
| C12 | TB hand-off into tax | `tb-handoff.md` | T-06 | AUD-38, CLS-12 | S50 | 2028-09-18 | v1 | planned |
| C13 | Human-gate projection registration slot (Home) | `human-gates.md` | I-01 with P-04 | every module | S10 | 2027-03-08 | v1 | planned |
| C14 | Board and program-status read model | `board-status.md` | K-04 | AUD-01/02, TAX-01, CLS-01/02, ATT-04 | S59 | 2029-01-22 | v1 | planned |
| C15 | Search registration | `search.md` | P-02 (slot reserved by F-03-T08) | all modules | slot S1, index S39 | 2026-11-02, 2028-04-17 | v1 | slot reserved (F-03-T08) |
| C16 | Notification kinds and transactional email templates (database) | `notifications.md` | P-01, R-01 | all | S5 | 2026-12-28 | v1 | frozen (P-01-T12, 2026-10-23) |
| C17 | Workbench tool registry (per-module read and compute tools, ADR-049) | `workbench-tools.md` | P-10 | W-02, W-03, I-02 | S32 | 2028-01-10 | v1 | planned |
| C18 | Portal approvals (FS packages, client AJE approval) | `portal-approvals.md` | R-02 | A-06, A-07, C-02 | S30 | 2027-12-13 | v1 | planned |
| C19 | Section 7216 consent gate and TRI data class (gateway condition 6) | `consent-7216.md` | T-01 | T-*, N-04, W-02, I-02 | S17 | 2027-06-14 | v1 | planned |
| C20 | Integration framework and write-capability registry (firm, personal and client connections; W entries) | `integrations.md` | A-02, W-01 | POR-16, TAX-09, CLS-11, ATT-09, ADM-08 | framework S10, catalogue S45 | 2027-03-08, 2028-07-10 | v1 | planned |
| C21 | Effective-dated rules tables (due dates, holidays, form sets and tolerances, thresholds, retention floors) | `rules-tables.md` | K-02 | T-01, T-02, T-03, T-08, C-02, Q-05 | S17 | 2027-06-14 | v1 | planned |

C1 milestones: stub F-03-T06 (S0), freeze F-03-T19 (by Fri 2026-11-13, M2), live F-03-T31 (S3). C2: the YAML is authored by F-03-T04, the codegen is F-03-T09, and the `status.ts` runtime is F-05.

C3 schema v1 (2026-10-22, P-04-T09): the three review migrations (0093 to 0095) and stubs 1 and 2 (`review/contract.py`, `agents/contract.py`) are **scheduled to be recorded frozen on Fri Dec 11, 2026** (the end of S3). They are not frozen yet. The gate is the consumer suites, green in `make check` stage 2: `backend/tests/contracts/review_grammar/` (SHL-10 a-g, SHL-11 a-h, SHL-12 a-h, the stub gates, the matrix and the migrations) and `apps/web/src/fixtures/contracts/review-grammar.test.ts` (one typed frame per artboard). Before the freeze, clear the strict xfail for finding #285 (decision-card figures and agent reasons are not Restricted), then write `backend/tests/contracts/review_grammar/v1.json` with `python -m abacus_tools.contracts --freeze review_grammar v1` and set the row to `frozen`.

C3 stub 3 (2026-10-23, P-04-T11 and P-04-T12) is **an additive extension of the C3 v1 schema** (handshake rule 5). It adds issues and fix instructions (SHL-15), checkpoints (SHL-16) and field provenance (SHL-09) as new models and operations in `review/contract.py`, beside stubs 1 and 2, under the same flag (`review.grammar_api`). No stub 1 or 2 field, operation, enum member or status code changed: the OpenAPI diff only adds. So it stays v1, and it is part of the Fri Dec 11, 2026 freeze. Its consumer suites are `test_c3_stub3.py`, `test_c3_shl09_field_provenance.py`, `test_c3_shl15_issues.py` and `test_c3_shl16_checkpoints.py`, plus the stub 3 frames in `review-grammar.test.ts`. They join the freeze gate, and they fail if a field the SHL-09 a-f, SHL-15 a-e or SHL-16 a-f artboards need is removed or retagged.

File names above are the planned names; a contract's file is created by its stub task, and the register row is updated in the same commit.

## Platform interfaces (unnumbered)

Interfaces that Q-01 provides to the product modules but that are not among the 21 cross-module contracts above. Same file rules, same frozen-contract rule. Source: `docs/plan/epics/Q-01.md` section 8 and SPEC-050 AC-21.

| Interface set | File | Provider (epic) | Consumers | Freeze sprint | Freeze starts | Version | Status |
|---|---|---|---|---|---|---|---|
| Platform operations: WorkOS adapter port, `runtime-config.json` schema, public routes and readiness, deploy lock, ops-task commands, `TenantProvisioningWorkflow`, `platform.api.control_active` and the kill-switch rule, SES identity port, the live AWS adapters | `platform-ops.md` | Q-01 (Q-01-T13) | P-01, P-08, F-04, G-04, R-01, F-01 `db_guard`, Q-04 | S5 (Q-01-T57) | 2026-12-28 | v1 | frozen (Q-01-T57, 2026-10-23) |

## Screen-family contracts (unnumbered)

Contracts one screen family needs that are not among C1 to C21 (P-07 owns no C-number; P-07 §8.1). Same file rules, same frozen-contract rule. Each freezes at the sprint review after its stub.

| Family | File | Provider (epic) | Consumers | Version | Status |
|---|---|---|---|---|---|
| Clients: CLI-01 index, CLI-02 record, overview, relationships, PATCH, TIN reveal | `clients.md` | P-07 (P-07-T04) | CLI-01, CLI-02, T-01, T-06, P-02 | v1 | live except the TIN reveal (P-07-T08, T09, 2026-10-23) |
| Retention: firm policies, staff floor and default sets | `retention.md` | Q-02 (Q-02-T23) | ADM-06h, FIL-02a, Q-02-T24, Q-05 | v1 | live (Q-02-T23, 2026-10-23) |
| Engagements: ENG-01 index, ENG-02 record and gates, the interim recorded letter, ENG-03 type catalogue, drafts and create (an additive C1 v1.1 note) | `engagements-v2.md` | P-07 (P-07-T05) | ENG-01, ENG-02, ENG-03, CLI-02, A-01, N-02, T-02, C-01 | v2 | stub (P-07-T05, 2026-10-23) |

## The handshake (chapter 01 §1.3.2, solo edition)

1. **Request.** The consumer states the screen IDs and artboard states the contract must serve, the seed figures that must foot and the human-only gates, and writes the contract tests (pytest against the stub, TypeScript fixture assertions). Solo: this is a note in the task file; there is no issue template.
2. **Stub.** Pydantic models with classification tags, route stubs returning 501 (or seed-derived fixtures), permission-matrix actions, a flag, `make generate`, and `docs/contracts/<name>.md` from `_TEMPLATE.md` (who may call it, status words, human-only actions, audit events). One stub per screen family.
3. **Parallel build.** The consumer builds in fixture mode; the provider implements behind the same schema. Consumer contract tests run in the provider's CI and must stay green.
4. **Swap and done.** The consumer flips from fixture to live; the journey passes with INV-1 to INV-5 and axe.
5. **Versioning.** See the rule below.

## The frozen-contract rule

Once a contract is `frozen` at v1:

- **Additive changes** (a new optional field, a new operation, a new enum member that consumers must tolerate) go in place, with the contract doc updated in the same commit.
- **Breaking changes** (removing or renaming a field, an operation or an enum member; changing a type, a status code or a human-only action; tightening validation) ship as **vN+1** with **one sprint of overlap**: vN keeps working and stays in the generated client until the end of the next sprint, then is removed. The contract doc and this register carry both versions during the overlap.
- **CI.** A snapshot diff of the OpenAPI schema and the contract models fails the build when a frozen field is removed or renamed, unless the same change ships vN+1 with overlap. Consumer contract tests run in the provider's CI and must stay green. CI enforcement (F-03-T18): `make ci-contracts` runs `python -m abacus_tools.contracts --check` against each frozen snapshot in `backend/tests/contracts/<contract>/vN.json`; `--freeze <contract> vN` writes a new version and never rewrites one.
- **Approval.** The two-founder approval clause in chapter 01 is void under `docs/plan/AMENDMENT-solo.md`. The builder decides, records the decision in `docs/product/decision-log.md` and bumps the register row.

### Runbook: shipping vN+1

`python -m abacus_tools.contracts --check` compares **every** snapshot on disk (`backend/tests/contracts/<contract>/v*.json`) with today's schemas of the models listed for that contract in `MODELS` (`backend/src/abacus_tools/contracts.py`). So vN keeps passing only while its models are unchanged, and vN+1 is built beside it:

1. **Decide and record.** Write the breaking change and the reason in `docs/product/decision-log.md`; name the consumers (the register row) whose tests must move.
2. **Add, don't change.** New models and operations beside the old ones (for example `WorkItemOutV2` and a `/v2/...` route, or a new operation); vN's models and routes stay as they are. `make generate`; the generated client carries both.
3. **Freeze vN+1.** Add the new model names to `MODELS[<contract>]`, then `cd backend && uv run python -m abacus_tools.contracts --freeze <contract> vN+1`. It refuses to overwrite an existing snapshot.
4. **Document the overlap.** The contract doc describes both versions and the date vN goes; the register row reads `vN, vN+1 (vN until <end of next sprint>)`. Consumer contract tests for vN+1 land in `backend/tests/contracts/<contract>/`; vN's stay green.
5. **Retire vN at the end of the next sprint**, in one commit: remove vN's models and routes, drop them from `MODELS`, delete `vN.json` (it would otherwise report them `removed`), port each vN consumer test to vN+1 (a test is never dropped without its replacement), `make generate`, and set the register row to `vN+1`.
6. **Check:** `make ci-contracts` (schema check, the snapshot check, the contract tests and the generated-client drift).

## Adding or changing a row

Copy `_TEMPLATE.md` to `docs/contracts/<name>.md`, fill it, and update the row here (file, version, status). Then run `cd backend && uv run python -m abacus_tools.quality.validate_docs`.
