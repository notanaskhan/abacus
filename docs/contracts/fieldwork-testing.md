# Fieldwork testing (A-08 epic contract, v1)

| Field | Value |
|---|---|
| Register row | epic contract (A-08 §8.1), not a C-numbered contract |
| Version | v1 |
| Status | stub (A-08-T05) |
| Provider epic | A-08 (AY) |
| Consumers | AUD-12, AUD-11 (MUS), A-11, X-01, K-04 |
| Freeze sprint | S47 (A-08 §8.1) |
| Flag | `audits.fieldwork_testing`; `sampling.monetary_unit` for MUS (default off, expire 2027-05-13) |
| Spec | `docs/specs/SPEC-657-a08-audit-fieldwork-depth.md` (F1–F4) |
| ADRs | ADR-050, ADR-160, ADR-161, ADR-166, ADR-340, ADR-400 (proposed) |

## 1. Purpose
JE testing over a GL population proved complete by code, the firm's risk criteria, code's scores with reason codes, the selection and its expansion, and the attribute variants on A-05's grid (runs, L1 adoption, exceptions, deviations, export). Code: `sampling/fieldwork_contract.py`, `workpapers/fieldwork_tests_contract.py`.

## 2. Who may call it
Every route answers, in order: a client principal 404; the action on the work item's engagement (walls 404, independence 403) or, on a record's own path, the flag first and the service's authorisation on the record's work item; 404 with the flag off; then 501 `not_implemented` naming the task that implements it. Every field is classified (`tests/contracts/a08_fieldwork/test_fieldwork_stubs.py`). Typed fixtures: `backend/src/abacus/modules/assurance/fieldwork_fixtures.py` (computed footings) and `apps/web/src/fixtures/seed/fieldwork.ts` (generated types; `fixtures/contracts/fieldwork-figures.test.ts`).

| Operation | Method and path | Matrix action | Task |
|---|---|---|---|
| Create JE test | POST `/v1/work-items/{wid}/je-tests` (409 `population_not_tied`) | `je_test.create` | T12 |
| Read | GET `/v1/je-tests/{jid}` · `…/entries?criterion=&selected=&cursor=` | `je_test.read` (agent task_scope) | T12 |
| Criteria · posting-user roles | PUT `…/criteria` · `…/posting-user-roles` | `je_test.configure` | T12 |
| Score | POST `…/score` (202) | `je_test.score` | T12 |
| Selection | POST `…/selection` (`je_score_selection`) | `sample_set.create` | T12 |
| Expansion | POST `/v1/sample-sets/{sid}/expansions` (422 `expansion_rationale_required`, `approver_required`) · `/v1/sample-expansions/{xid}/withdraw` | `sample_expansion.request` | T17 |
| Decide expansion | POST `/v1/sample-expansions/{xid}/decide` (409 `content_changed`) | `sample_expansion.decide` (`is_named_approver`, `not_preparer_of_target`) | T17 |
| Run | POST `/v1/tests/{tid}/runs` (202) | `test.run` | T24 |
| Adopt (L1) | POST `/v1/tests/{tid}/adopt` | `test.adopt` | T14 |
| Exception prefill | POST `/v1/tests/{tid}/items/{iid}/exception` | `finding.create` | T14 |
| Deviation | POST `/v1/tests/{tid}/deviations` | `test.mark` | T14 |
| Export | GET `/v1/tests/{tid}/export.xlsx` | `test.export` | T14 |

## 3. Models
`JeTestOut` (status, entries, lines, `TieOut`, `CriterionOut[]` with availability and missing fields, `unique_flagged`, `SelectionOut` with its pending `ExpansionOut`), `ScoredEntryOut` (score with ≥ 1 reason code; accounts last four), `ExpansionIn`/`ExpansionOut` (`resulting_count` is code's), `DeviationLogOut` (UDL and tolerable rate), `AdoptOut`, `TestRunOut`.

## 4. Status words
`je_test`, `je_criterion` ("Not available from this ledger"), `fieldwork_test_result` (Agent-tested · Needs human · Adopted · Exception), `sample_expansion`.

## 5. Human-only actions
Adopt, decide an expansion, raise an exception, mark and log deviations: the agent is denied at the matrix (I-AGENT-NEVER suite). The agent's per-item values are suggestions (A-08-T23).
