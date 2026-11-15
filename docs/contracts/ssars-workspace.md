# SSARS workspace (A-08 epic contract, v1)

| Field | Value |
|---|---|
| Register row | epic contract (A-08 §8.1), not a C-numbered contract |
| Version | v1 |
| Status | stub (A-08-T05) |
| Provider epic | A-08 (AY) |
| Consumers | AUD-26, AUD-23, POR-05, POR-08 |
| Freeze sprint | S47 (A-08 §8.1) |
| Flag | `audits.ssars_workspace` (default off, expires 2027-05-13) |
| Spec | `docs/specs/SPEC-657-a08-audit-fieldwork-depth.md` (F8) |
| ADRs | ADR-050, ADR-160, ADR-161, ADR-166, ADR-340, ADR-400 (proposed) |

## 1. Purpose
One cockpit for review (AR-C 90), compilation (AR-C 80) and preparation (AR-C 70): the mode from the engagement type, the rail per mode, inquiry programs to POR-05, and the preparation legend. Code: `assurance/analytics_contract.py` (SSARS routes); analytics as `audit-analytics.md` with `kind = ssars_review`.

## 2. Who may call it
Every route answers, in order: a client principal 404; the action on the work item's engagement (walls 404, independence 403) or, on a record's own path, the flag first and the service's authorisation on the record's work item; 404 with the flag off; then 501 `not_implemented` naming the task that implements it. Every field is classified (`tests/contracts/a08_fieldwork/test_fieldwork_stubs.py`). Typed fixtures: `backend/src/abacus/modules/assurance/fieldwork_fixtures.py` (computed footings) and `apps/web/src/fixtures/seed/fieldwork.ts` (generated types; `fixtures/contracts/fieldwork-figures.test.ts`).

| Operation | Method and path | Matrix action | Task |
|---|---|---|---|
| Workspace | GET `/v1/work-items/{wid}/ssars` | `ssars.read` | T22 |
| Inquiry program · publish | POST `…/ssars/inquiries` · `…/ssars/publish` | `ssars.inquiry_manage` | T22 |
| Reminder | POST `…/ssars/remind` | `client_question.send` | T22 |

## 3. Models
`SsarsWorkspaceOut` (mode, standard, rail rows, analytics set, `InquirySummaryOut` answered/open, `legend` "No assurance is provided." for AR-C 70, `report_available`, approval label), `InquiryProgramIn`/`Out`, `ReminderIn`. A report for a preparation work item answers 409 `no_report_for_preparation`.

## 4. Status words
Inquiry status words are request vocabulary (Requested · Answered). "Conclusion", never "opinion" (copy lint).

## 5. Human-only actions
Publishing, reminding and accepting are a person's; the agent proposes explanations only.
