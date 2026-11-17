# Audit analytics (A-08 epic contract, v1)

| Field | Value |
|---|---|
| Register row | epic contract (A-08 §8.1), not a C-numbered contract |
| Version | v1 |
| Status | implemented (A-08-T21, DEC-5400) except the expectation route (A-08-T22) |
| Provider epic | A-08 (AY) |
| Consumers | AUD-13, AUD-26 (analytics), C-01/C-02 (shared flux engine), A-10 |
| Freeze sprint | S47 (A-08 §8.1) |
| Flag | `audits.analytics` (default off, expires 2027-05-13) |
| Spec | `docs/specs/SPEC-657-a08-audit-fieldwork-depth.md` (F5) |
| ADRs | ADR-050, ADR-160, ADR-161, ADR-166, ADR-340, ADR-400 (proposed) |

## 1. Purpose
Analytics sets over a TB layer against prior-year figures, with the dual threshold derived from performance materiality, verified explanations, manager acceptance and firm-templated client questions. Code: `assurance/analytics_contract.py`.

## 2. Who may call it
Every route answers, in order: a client principal 404; the action on the work item's engagement (walls 404, independence 403) or, on a record's own path, the flag first and the service's authorisation on the record's work item; 404 with the flag off; then 501 `not_implemented` naming the task that implements it. Every field is classified (`tests/contracts/a08_fieldwork/test_fieldwork_stubs.py`). Typed fixtures: `backend/src/abacus/modules/assurance/fieldwork_fixtures.py` (computed footings) and `apps/web/src/fixtures/seed/fieldwork.ts` (generated types; `fixtures/contracts/fieldwork-figures.test.ts`).

| Operation | Method and path | Matrix action | Task |
|---|---|---|---|
| Run | POST `/v1/work-items/{wid}/analytics-sets` (202) | `analytics.run` | T21 |
| Read · provenance | GET `/v1/analytics-sets/{aid}` · `…/lines/{pos}/provenance` | `analytics.read` (agent task_scope) | T21 |
| Explanation | PUT `…/lines/{pos}/explanation` (422 `explanation_uncited`) | `analytics.explain` | T21 |
| Expectation | PUT `…/lines/{pos}/expectation` | `analytics.configure` | T22 |
| Accept | POST `…/explanations/accept` | `analytics.accept` (`not_preparer_of_target`) | T21 |
| Client questions | POST `…/client-questions` | `client_question.send` | T21 |
| Export | GET `…/export.xlsx` | `analytics.export` | T21 |
| Prior-year figures | PUT `/v1/work-items/{wid}/prior-year-figures` | `analytics.configure` | T21 |

## 3. Models
`AnalyticsSetOut` (kind, stage, version, status, basis label, `ThresholdOut` with materiality, provisional flag and decider, `TalliesOut`, `AnalyticsLineOut[]` with code's change, change %, evaluated, over and derived, its `ExplanationOut` and `ExpectationOut`, `engine_version`, `inputs_hash`), `ProvenanceOut`, `ClientQuestionsIn` (cards from templates a person edited).

## 4. Status words
`analytics_set` (Pending · Current · Out of date · Superseded), `analytics_line` (Within · Unexplained · Explained · Accepted; amber, never red).

## 4a. Implementation (A-08-T21, DEC-5400)
- Service `assurance/analytics.py`, migration `0940_audit_analytics`; `FluxAnalyticsWorkflow` (interactive) computes a set with `workpapers.compute.flux` (dual threshold), supersedes the previous Current version and emits `analytics.computed`.
- Threshold: the firm's 10% **and** PM from the materiality version in force, else the current version (provisional). `materiality.decided` re-thresholds each Current preliminary set as a new version (idempotent on the event); an explanation carries forward, with its acceptance, only where the line's over/within result is unchanged.
- An explanation needs >= 1 citation that `evidence.supported_citations` returns (verified and still valid on the engagement), else 422 `explanation_uncited`; a client answer to an analytics question (`questionnaire.answered`) is a `client_answer` explanation that names its question.
- Accept takes `seen_hash` = `AnalyticsSetOut.review_hash` (409 `content_changed`); the matrix's `not_preparer_of_target` gets the explanations' authors. HOME-02 gate `analytics_explanation_acceptance` (managers) and notification `analytics_explanations_ready` (engagement leads).
- Not yet: `adjustment.approved` marking final-stage sets Out of date (C8 emits no such event on main), the SSE progress stream (A-08-T24).

## 5. Human-only actions
Accepting explanations and sending client questions: the agent is denied; explanations it drafts are suggestions (`suggestion.create`). No model text reaches a client (DV-4).
