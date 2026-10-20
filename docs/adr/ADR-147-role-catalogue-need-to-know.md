---
id: ADR-147
title: Role catalogue and need-to-know - two axes plus work-item functions
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
The repo roles do not cover IT/Security, engagement quality review, tax preparer and reviewer functions, or the Firm Admin's duties around client content (Grace Holloway runs intake, binders and envelopes). Making each job title a matrix role would grow the matrix without bound. Plan decisions DEC-20 and DEC-21 settle this; this ADR is P-10 in the plan's ADR backlog.

## Decision
- **Firm role:** add `security_admin`.
- **Engagement roles:** add `eqr_reviewer`, `specialist` and `client_service`. The repo `reviewer` stays a read-only QC role (Q-06).
- **Membership attributes:** `level` (partner, manager, senior, staff, seasonal, admin), `office_id`, `offshore`, `service_lines`.
- **Work-item functions, not roles:** Tax Preparer and Tax Reviewer, with the other preparer, reviewer and signer functions.
- **`client_service`** covers binders, invitations, envelopes, request status and file names, plus a firm-level intake scope. Under that scope it may read inbound messages and attachments until they are filed. It cannot open filed evidence or workpapers (inferred boundary).
- **Firm overrides are stricter-only.** They may replace `allow` with a narrower value or `deny`; the ADM-02 role templates write them.

## Options considered
### Option A: two axes plus work-item functions — chosen
- Pros: small matrix; seasonal staff are just `level=seasonal`; no change to the admin metadata rule.
- Cons: a function layer and new condition types to build.

### Option B: blueprint job roles as matrix roles
- Pros: names match job titles.
- Cons: the matrix multiplies and drifts from the repo model.
- Why rejected: plan DEC-21 chose two axes.

## Consequences
**Positive**
- Grace can run binders without reading evidence; IT/Security holds no content rights.

**Negative / costs accepted**
- Matrix codegen grows new condition types, each with generated allow and deny tests.

**Follow-up work created**
- Code: offices, teams and membership attributes, new roles (epic F-03, S2; task F-03-T23); matrix codegen and stricter-only `firm_policy_overrides` (F-03-T24, S2); capabilities (F-03-T30, S3).
- Specs: ADM-02 role templates and the admin screens cite roles and levels from the catalogue.
- Glossary: `security_admin`, `eqr_reviewer`, `specialist`, `client_service`, `level`, work-item function.
- Matrix: new roles and conditions `level_in`, `function_in`, `scope_only`, `not_offshore`, `attest_client`, `gates_met`, `in_scope`, `firm_setting` in `docs/architecture/permission-matrix.yaml` (F-03, S2).
- Registry: role and function lists generated from the matrix; `actions.gen.ts`.

## Enforcement
- [x] Test: generated allow and deny tests for every new condition type (F-03-T24).
- [x] Test: `security_admin` is denied every content action; `client_service` is denied evidence content (F-03 stories 4.1, 4.2).
- [x] Test: a property test checks that overrides never widen a decision.
- [ ] Advisory only: none.

## Guidance for agents
Add a function or an attribute before adding a role. Check capabilities through the matrix, never by role name. Overrides can only tighten.

**Do**
```yaml
- action: binder.publish
  allow: [client_service]
```

**Don't**
```python
if membership.job_title == "Tax Reviewer": ...   # a function is not a role
```

## Revisit when
A job needs access that no role, level or function can express, or counsel changes the content boundary for IT/Security.

## Related
- Plan: P-10 (section 9.4.2); DEC-20 (decided); DEC-21 (open in `docs/product/decision-log.md` at time of writing; the plan's proposed option is taken); Q-06, Q-07, C-14.
- Clarifies ADR-024: every clause stands (admins see metadata, not content; joining an engagement grants content and is audited). `client_service` is an engagement role that does not grant content, so ADR-024 is not superseded.
- Amends ADR-027: its clause "Rules are declared in `permission-matrix.yaml` (role x action x condition -> decision)" gains the new condition types and stricter-only firm overrides. The in-house module, generated tests and one-action-per-route clauses stand.
- ADRs: ADR-140 (per-module matrix files).
