# Quality management v1 — SQMS No. 1 register, override projection, inspections, findings, evaluation

| Field | Value |
|---|---|
| Owner | practice (Q-05; SPEC-711) |
| Status | skeleton (Q-05-T01, 2026-11-18; DEC-5608); stub Q-05-T05; v1 S53 |
| Code | `backend/src/abacus/modules/practice/quality_contract.py` (Q-05-T05) |
| Flag | `quality.management` (default off; off: 404; on: 501 until each build task) |
| Consumers | ADM-11, ADM-12; I-03 (INS-02 equality with ADM-11), K-05 (DEC-96 projection), W-03 (WB-08) |

Readers: `quality_partner`, `practice_leader` in scope and the Monitoring reviewers group (OQ-4); never `firm_admin` (ADR-024). The agent reads nothing here and decides nothing. Rates and counts are code; the override projection (`agent_output_outcomes`) is the only source for ADM-11 and INS-02 (DEC-96).

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/quality/dashboard?office_id&cycle` | `quality.read` | tiles, register summary, override summary, findings, consultations |
| `GET /v1/quality/register?component` · `PATCH /v1/quality/objectives/{id}` | `quality.read` · `quality.manage` | owner, health flag, note (OQ-11) |
| `POST /v1/quality/imports` · `POST …/{id}/publish` | `quality.manage` | dry run then publish, fresh MFA; content never in commits |
| `POST /v1/quality/risk-assessment/reviews` | `quality.manage` | DV-7 |
| `GET /v1/quality/agent-overrides?window=30d&office_id` · `…/{agent_key}/reasons` · `GET /v1/quality/accuracy` | `quality.read` | 206 of 3,410; 1,320 of 41,260 |
| `GET /v1/quality/cycles` · `GET /v1/quality/inspections` · `GET /v1/quality/inspection-candidates` | `quality.read` · `inspection.plan` | risk score and objectivity per inspector |
| `POST /v1/quality/inspections` · `POST …/{id}/start` · `…/conclude` | `inspection.plan` · `inspection.update` | plan issues grants; conclude revokes them; 409 `inspector_not_objective` |
| `GET /v1/quality/findings` · `POST /v1/quality/findings` · `PATCH …/{id}` | `quality.read` · `qm_finding.record` · `qm_finding.update` | |
| `POST /v1/quality/findings/{id}/evaluations` · `…/remediate` | `qm_finding.evaluate` · `qm_finding.remediate` | evaluation human-only, QM owner |
| `GET /v1/quality/evaluations/{year}` · `POST …/request-conclusion` | `quality.read` · `quality.manage` | raises the `qm_annual_evaluation` card (409 `inspections_open`); decided through `POST /v1/decision-cards/{id}/decide` |

**Examples (foot):** 412 + 318 + 880 + 1,260 + 540 = 3,410; 37 + 29 + 61 + 63 + 16 = 206 (6.0%); Denver 61 of 1,128 (5.4%); 1 − 1,320 ÷ 41,260 = 96.8%; Sep 14 → Dec 15, 2026 = 92 days.
