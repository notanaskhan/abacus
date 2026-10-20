# Contract register

The register of the plan's 21 cross-module contracts, C1 to C21. Source: `docs/plan/01-strategy-roadmap.md` §1.3.2 (register) and `docs/plan/epics/F-03.md` §8.1 and §3.10. One file per contract: `docs/contracts/<name>.md`, from `_TEMPLATE.md`. Consumer contract tests live in `backend/tests/contracts/<name>/`.

Sprint dates: Sn starts Mon 2026-10-19 + 14n days (S0 2026-10-19, S1 2026-11-02, S3 2026-11-30 ...). The freeze date is the start of the freeze sprint.

Status values: `planned` (no stub), `stub` (models, 501 routes, matrix actions, flag and contract doc landed, not frozen), `frozen` (version fixed, breaking changes need vN+1), `live` (implemented behind the contract), `superseded`.

## Register

| C | Contract | File | Provider (epic) | Consumers | Freeze sprint | Freeze starts | Version | Status |
|---|---|---|---|---|---|---|---|---|
| C1 | Work item and engagement lifecycle (8 states, G1-G3 facts, per-type gate policy) | `work-items.md` | F-03 | every module | S1 | 2026-11-02 | v1 | frozen (F-03-T19, 2026-10-21) |
| C2 | Status registry: YAML to StrEnum, OpenAPI enums, `status.ts` | `status-registry.md` | F-03 (YAML authored in F-03-T04, codegen F-03-T09) | all | S1 | 2026-11-02 | v1 | frozen (F-03-T19, 2026-10-21) |
| C3 | Review grammar: suggestion and change set, decision, sign_off (content hash, staleness, segregation), issue, checkpoint, field_value_version, human_gate | `review-grammar.md` | P-04 | A-*, T-*, C-*, I-01 | schema S3, services S12 | 2026-11-30, 2027-04-05 | v1 | planned |
| C4 | Citation v2, viewer manifest, regions, masked PII and logged reveal | `citation-v2.md` | P-03 | every trace surface | S5 | 2026-12-28 | v1 | planned |
| C5 | Requests and binders; portal scopes (`client_access_grant`, role union) | `requests-binders.md` | P-06, P-08 (schema half in F-03-T14, T15, T26); portal read models | A-01, R-01, T-02, C-01 | S3 | 2026-11-30 | v1 | planned |
| C6 | Agent runs: v1 read API; v2 run and step events over SSE | `agent-runs.md` | P-09, P-10 | dock, trace, Workbench, Today | v1 S12, v2 S30 | 2027-04-05, 2027-12-13 | v1 | planned |
| C7 | Envelope service: record mode, then DocuSign embedded with provider ID Verification; evidence package; gate events | `envelopes.md` | N-02 | ENG-04, SIG-*, POR-06, TAX-12, AUD-21, NOT-03 | record S14, DocuSign S17 | 2027-05-03, 2027-06-14 | v1 | planned |
| C8 | Adjustments: proposed entries (8 states), threshold-policy versions, named-human batch approval | `adjustments.md` | A-06 | EBP-06, T-05, C-02, A-09 eliminations | S24 | 2027-09-20 | v1 | planned |
| C9 | Ledger: TB layers, groupings and FS-line taxonomy, account mapping | `ledger.md` | A-02, A-03 | A-04, A-06, T-05, C-01, A-10 | layers S10, taxonomy S20 | 2027-03-08, 2027-07-26 | v1 | planned |
| C10 | Deliverables and release registry with download audit | `deliverables.md` | R-02 | A-07, T-02 (K-1), C-02, X-01 | S29 | 2027-11-29 | v1 | planned |
| C11 | Deterministic PDF/DOCX renderer; templates in the database | `renderer.md` | P-11 | ENG-04, AUD-20 to AUD-23, TAX-12, NOT-03, CLS-08, FSP-06 | S18 | 2027-06-28 | v1 | planned |
| C12 | TB hand-off into tax | `tb-handoff.md` | T-06 | AUD-38, CLS-12 | S50 | 2028-09-18 | v1 | planned |
| C13 | Human-gate projection registration slot (Home) | `human-gates.md` | I-01 with P-04 | every module | S10 | 2027-03-08 | v1 | planned |
| C14 | Board and program-status read model | `board-status.md` | K-04 | AUD-01/02, TAX-01, CLS-01/02, ATT-04 | S59 | 2029-01-22 | v1 | planned |
| C15 | Search registration | `search.md` | P-02 (slot reserved by F-03-T08) | all modules | slot S1, index S39 | 2026-11-02, 2028-04-17 | v1 | slot reserved (F-03-T08) |
| C16 | Notification kinds and transactional email templates (database) | `notifications.md` | P-01, R-01 | all | S5 | 2026-12-28 | v1 | planned |
| C17 | Workbench tool registry (per-module read and compute tools, ADR-049) | `workbench-tools.md` | P-10 | W-02, W-03, I-02 | S32 | 2028-01-10 | v1 | planned |
| C18 | Portal approvals (FS packages, client AJE approval) | `portal-approvals.md` | R-02 | A-06, A-07, C-02 | S30 | 2027-12-13 | v1 | planned |
| C19 | Section 7216 consent gate and TRI data class (gateway condition 6) | `consent-7216.md` | T-01 | T-*, N-04, W-02, I-02 | S17 | 2027-06-14 | v1 | planned |
| C20 | Integration framework and write-capability registry (firm, personal and client connections; W entries) | `integrations.md` | A-02, W-01 | POR-16, TAX-09, CLS-11, ATT-09, ADM-08 | framework S10, catalogue S45 | 2027-03-08, 2028-07-10 | v1 | planned |
| C21 | Effective-dated rules tables (due dates, holidays, form sets and tolerances, thresholds, retention floors) | `rules-tables.md` | K-02 | T-01, T-02, T-03, T-08, C-02, Q-05 | S17 | 2027-06-14 | v1 | planned |

C1 milestones: stub F-03-T06 (S0), freeze F-03-T19 (by Fri 2026-11-13, M2), live F-03-T31 (S3). C2: the YAML is authored by F-03-T04, the codegen is F-03-T09, and the `status.ts` runtime is F-05.

File names above are the planned names; a contract's file is created by its stub task, and the register row is updated in the same commit.

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

## Adding or changing a row

Copy `_TEMPLATE.md` to `docs/contracts/<name>.md`, fill it, and update the row here (file, version, status). Then run `cd backend && uv run python -m abacus_tools.quality.validate_docs`.
