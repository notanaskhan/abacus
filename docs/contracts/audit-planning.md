# Audit planning API (internal; v1)

| Field | Value |
|---|---|
| Register row | internal audit planning API (A-04 §8.2) in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub (A-04-T01, 2026-10-31); live per route with A-04-T07 (service-organization inventory), T12 (materiality), T13 (register and linkage), T18 (approval card, G4), T19 (fraud brainstorm), T25 and T31 (internal control, SOC 1) |
| Provider epic | A-04 |
| Consumers | AUD-04 e, f; AUD-05; AUD-07; AUD-08; AUD-09; AUD-10; HOME-02 (decision and gate rows); ENG-02 (G4); A-03 (`materiality.decided` releases AUD-11); A-05, A-06 (findings router), A-08 |
| Flags | `assurance.materiality`, `assurance.risk_register`, `assurance.internal_control`, `assurance.service_orgs`; drafts also `workpapers.drafting` (all default off; DEC-137 override, expires 2027-04-29) |
| Spec | A-04 §3.2–§3.8, §4.3 (SPEC to land with A-04-T02) |
| ADRs | ADR-005, ADR-031, ADR-050, ADR-052, ADR-160, ADR-161 |

## 1. Purpose
Planning materiality and its partner decision, the risk register with code-computed RMM and tally,
linkage to responses, the significant-risk approval card that feeds G4, the fraud brainstorm and
its EP-approved minutes, internal-control processes and the exceptions sheet, and service
organizations with SOC 1 evaluations. Code computes every figure (ADR-050): materiality, PM and CT,
RMM, the tally, coverage and the SOC gap. People decide (INV-1): materiality, the register,
minutes and reliance are a named person's acts through C3.

## 2. Who may call it
All under `/v1/engagements/{eid}`. Every client and third-party principal and `client_service`
answer 404 (INV-4: no portal or API scope admits an A-04 table, and the L7 crawler finds none of
these figures); a walled member 404; an independence failure 403. "Team" is EP, manager, senior
and staff; reads add reviewer, EQR, specialist and an in-scope quality partner, and the agent
holds reads only through a run's task scope. The agent and the system are denied every write.

| Operation | Method and path | Matrix action | Roles allowed | Flag |
|---|---|---|---|---|
| Materiality record | `GET /materiality/current` | `materiality.read` | team + reviewers | `assurance.materiality` |
| Preview thresholds | `POST /materiality/preview` (no write) | `materiality.read` | team + reviewers | `assurance.materiality` |
| Propose | `POST /materiality/proposals` | `materiality.propose` | manager, senior | `assurance.materiality` |
| Reassess at final | `POST /materiality/reassessments` | `materiality.reassess` | manager, senior | `assurance.materiality` |
| Decide, remind, analysis | `POST /v1/decisions/{id}/decide` · `/remind` · `/analysis-requests` (C3) | `decision.decide` (reserved EP, fresh MFA), `decision.remind` | as C3 | C3 |
| Register | `GET /risks/register` | `risk.read` | team + reviewers | `assurance.risk_register` |
| Linkage | `GET /risks/linkage` | `risk.read` | team + reviewers | `assurance.risk_register` |
| Drawer | `GET /risks/{rid}` | `risk.read` | team + reviewers | `assurance.risk_register` |
| Edit a risk | `PATCH /risks/{rid}` | `risk.edit` | EP, manager, senior | `assurance.risk_register` |
| Link, unlink | `POST`, `DELETE /risks/{rid}/responses` | `risk.link` | EP, manager, senior | `assurance.risk_register` |
| Route for approval | `POST /risks/approval-requests` | `risk.route_for_approval` | manager, senior | `assurance.risk_register` |
| Coverage | `POST /risks/coverage` | `risk.read` | team + reviewers | `assurance.risk_register` |
| Draft fields | `POST /risks/{rid}/drafts` (202) | `workpaper.draft` | EP, manager, senior | + `workpapers.drafting` |
| Brainstorm | `GET`, `PUT /fraud-brainstorm` | `fraud_session.read` · `.edit` | team + reviewers · EP, manager, senior | `assurance.risk_register` |
| Minutes | `PUT /fraud-brainstorm/minutes` | `fraud_session.edit` | EP, manager, senior | `assurance.risk_register` |
| Approve minutes | `POST /fraud-brainstorm/minutes/approve` | `fraud_minutes.approve` | engagement partner only | `assurance.risk_register` |
| Inquiries | `GET`, `POST /fraud-inquiries` | `fraud_session.read` · `fraud_inquiry.request` | team + reviewers · manager, senior | `assurance.risk_register` |
| Processes | `GET /internal-control/processes[/{id}]`, `PUT …/{id}` | `control.read` · `control.edit` | team + reviewers · team | `assurance.internal_control` |
| Exceptions sheet | `GET /internal-control/exceptions` | `control.read` | team + reviewers | `assurance.internal_control` |
| Propose severity | `PATCH …/exceptions/{row}/proposed-severity` | `deficiency.propose_severity` | EP, manager, senior | `assurance.internal_control` |
| Route | `POST …/exceptions/{row}/send-to-findings` · `/convert-to-misstatement` | `exception.route` | EP, manager, senior | `assurance.internal_control` |
| Request evidence | `POST …/exceptions/{row}/request-evidence` | `request_item.create` (existing) | as that action | `assurance.internal_control` |
| Service organizations | `GET`, `POST /service-organizations`, `GET`, `PATCH …/{id}` | `service_org.read` · `.edit` | team + reviewers · team | `assurance.service_orgs` or `workpapers.core` |
| SOC report | `GET`, `PATCH /soc-reports/{id}`, `PATCH …/cuecs/{n}` | `service_org.read` · `soc_report.evaluate` | team + reviewers · EP, manager, senior | `assurance.service_orgs` |
| SOC 1 reader | `POST /soc-reports/{id}/drafts` (202) | `workpaper.draft` | EP, manager, senior | + `workpapers.drafting` |
| Request drafts | `POST /soc-reports/{id}/requests` `{kind}` | `request_item.create` | as that action | `assurance.service_orgs` |
| Reliance card | `POST /soc-reports/{id}/reliance-requests` | `soc_report.evaluate` | EP, manager, senior | `assurance.service_orgs` |
| G4 | `GET /v1/engagements/{eid}/gates` (C1) | `engagement.read` (existing) | as C1 | `assurance.risk_register` (off: G4 hidden) |

**Live routes kept (DEC-1757).** Fieldwork's SPEC-300 operations stay on their paths, unflagged:
`GET` and `PUT /materiality`, `GET /materiality/versions`, `POST /materiality/decide`, `GET` and
`POST /risks`, `POST /risks/{id}/versions`, `POST /risks/{id}/approve`. The plan's A-04 reads on
`GET /materiality` and `GET /risks` take `GET /materiality/current` and `GET /risks/register`, and
creating a risk keeps the live `POST /risks` until A-04-T13 widens it additively (an `area_key` and
the SAS 145 fields); nothing is renamed in place. A-04-T12 and T13 move AUD-07 and AUD-08 onto
these; the SPEC-300 routes retire with their last consumer.

## 3. Models
`backend/src/abacus/modules/assurance/planning_contract.py`; every field classified (ADR-031).
Amounts, benchmark figures, rationales, minutes, matters and names are `confidential`; ids,
counts, codes, hashes and states `internal`. Amounts are decimal strings from code with an
`EngineStamp {engine_name, engine_version, inputs_hash, computed_at}`.

- Materiality: `MaterialityRecordOut` (current, versions, `BenchmarkOut[]` with
  `PriorYearOut[]` and growth, `QualitativeFactorOut[]`, policy version, pending card,
  `allowed_actions`), `PlanningMaterialityVersionOut` (status, current, superseded,
  `ThresholdsOut`, card and decision ids, `ReassessmentOut`, `ImpactOut[]`, `created_by_name`),
  `ThresholdsOut`, `OptionOut` (`recommended` is the agent's tag, never a choice),
  `MaterialityPreviewIn`, `MaterialityProposalIn` / `MaterialityProposalOut`, `ReassessmentIn` /
  `ReassessmentRaisedOut`.
- Register: `RegisterOut` (`TallyOut`, `RegisterRiskOut[]`, `register_hash`, approved card),
  `RegisterRiskOut` (code, level, area, assertions, IR, CR, RMM with its policy version,
  significance, fraud, presumption kind, SAS 145 `InherentFactorOut[]`, status, unaddressed,
  version, hash), `RiskDrawerOut` (rationale, suggestion id, citations, `RiskVersionOut[]`, routed
  to), `RiskEditIn`, `LinkageOut` (`LinkTargetOut[]` with `registered`, `LinkCellOut[]`),
  `ResponseIn`, `ApprovalRequestOut`, `CoverageOut`, `RiskDraftIn`, `RunStartedOut`.
- Brainstorm: `FraudSessionOut` (held at, medium, leader, attendees, `ExclusionOut[]` with
  reason, discussion, minutes text, hash, status and source, approver), `FraudSessionIn`,
  `MinutesIn`, `MinutesApproveIn {minutes_hash}`, `FraudInquiryOut`, `FraudInquiryIn`.
- Internal control: `ProcessOut`, `ProcessIn`, `ControlExceptionOut` (row, "Exceptions!D2"
  address, matter, proposed severity, the concluded severity **read** from A-06, disposition, COSO
  component, candidate amount, routing, citations), `ProposedSeverityIn`, `RoutedOut`,
  `RequestDraftOut`.
- Service organizations: `ServiceOrganizationOut`, `ServiceOrganizationIn`,
  `ServiceOrganizationPatchIn`, `SocReportOut` (`SocGapOut`, `SocExceptionOut[]`, `CuecOut[]`,
  reliance state and card), `SocReportPatchIn`, `CuecPatchIn`, `SocRequestsIn`,
  `RelianceRequestOut`.

## 4. Status words
`materiality_version` (proposed, decided, reassessed, revised; superseded derived),
`risk_register_row`, `risk_significance`, `risk_fraud`, `risk_linkage`, `fraud_minutes`,
`fraud_inquiry` (computed), `service_organization`, `soc_reliance`, `cuec`, `control_design`,
`control_exception_disposition`, generated from `docs/product/status-vocabulary.yaml`; severities
use the existing `deficiency_severity` words.

## 5. Errors
409: `version_conflict`, `outside_policy`, `nothing_pending`, `already_linked`,
`minutes_changed`, `gap_open`, `cuec_evidence_missing`, `drafting_not_enabled`, `no_amount`,
`duplicate_name`. 422: `rationale_required`, `presumption_not_rebuttable`, `reason_required`.
503: `route_not_available` until A-06 registers the exception router. 403: a decide by anyone but
the reserved person (C3). Each lands with the task that raises it; the stub raises only 404 and
501 `not_implemented`.

## 6. Human-only actions and audit events
Human only: deciding the `planning_materiality`, `significant_risk` and `service_org_reliance`
cards (reserved to the EP, through C3), approving the minutes (five layers: matrix,
`require_live_human`, DB CHECK, FRAUD-MINUTES-001, audit), proposing severity, routing, and every
write. The agent may propose a rebuttal of revenue recognition only as a suggestion and never on
management override. Audit: `materiality_version.proposed/decided/reassessed/revised`,
`risk.created/updated/linked/unlinked`, `risk.significance_proposed`, `risk.rebuttal_proposed`,
`risk.approval_requested`, `risk_register.approved`, `fraud_session.recorded`,
`fraud_minutes.approved`, `fraud_minutes.refused_non_human`, `fraud_inquiry.requested`,
`control_activity.recorded`, `control_exception.recorded/severity_proposed/routed`,
`service_org.recorded`, `soc_report.evaluated`, `cuec.evidenced`. Outbox: `materiality.decided`,
`materiality.reassessed`, `risk_register.approved`, `fraud_minutes.approved`,
`control_exception.recorded`, `service_org.reliance_concluded`.

## 7. Stub behaviour (A-04-T01)
Client principal 404 → the route's action on the engagement → 404 with the route's flag off (the
inventory answers with `assurance.service_orgs` or `workpapers.core`; drafts need
`workpapers.drafting` as well) → 501 `not_implemented`.

## 8. Examples that foot (Brightwater Hale, Northwind Robotics 401(k) Plan, PY2025)
- `ThresholdsOut` (OpenAPI example): unadjusted net assets 16,812,400 × 1.5% = 252,186, rounded to
  the nearest 100 half up = **252,200**; PM 75% = **189,150**; CT 5% = **12,610**; policy 1.0%–2.0%.
  The 1.0% option is 168,100 (PM 126,075, CT 8,405); the 2.0% bound 336,200.
- `ReassessmentOut` (AUD-07 d): final 16,861,000 × 1.5% = 252,900; difference 700 (0.3%); No change.
- `TallyOut` (AUD-08 a): 10 risks · 2 significant (+1 proposed) · 2 fraud · 3 high RMM ·
  1 unaddressed (R8) · EP approval pending.
- `SocGapOut` (AUD-10 a): SOC 1 Type 2 period ending Sep 30, 2025 against a calendar plan year:
  Oct 1 to Dec 31, 2025 = **92** days.
- Granite Peak (FS policy, pre-tax income 3%–7%): 3,100,000 × 5% = 155,000 / 116,250 / 7,750.
