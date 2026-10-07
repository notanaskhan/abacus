---
id: TASK-023
title: Engagement graph and methodology configuration v1
spec: SPEC-008
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9]
risk_zone: amber
status: done
branch: task-023-engagement-graph
worktree:
created: 2026-10-07
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-008 (approved, Q1–Q5): methodology templates imported from a workbook as immutable versions; applying a version to an engagement, which pins it and seeds its request items; and the engagement graph with account mapping and coverage gaps.

## Scope
All of SPEC-008. Excluded: engagement facts, knowledge retrieval, and any UI.

## Context to load
- Spec: `docs/specs/SPEC-008-engagement-graph-methodology.md`
- ADRs: ADR-053, ADR-050, ADR-004, ADR-106, ADR-052
- Code: the `engagements`, `requests`, `evidence`, `agents` and `ledger` APIs, and `ledger`'s workbook parsing (`SheetLayoutError`)

## Plan
- [x] Plan approved by human (founder, 2026-10-07: D1–D4). Approved by founder: paths listed under *Protected paths*, the SPEC-008 §8 amendment and the BOUND-002 test

### Design (for founder review)
1. **Templates** (`engagements`, Q3):
   - `engagements/methodology.py` parses the workbook with `openpyxl` (read-only, cached values, no formulas evaluated) into typed rows.
   - The limits are settings: 5 MB, 50 areas, 2,000 items and 2,000 rules.
   - Problems carry the sheet, row, column and a fixed code, never cell values.
   - Overlapping account ranges are found by sorting the ranges.
   - `import_template(ctx, name, data)` stores the template and version *n+1* in one unit of work, audited as `methodology.imported`.
   - It also offers `list_templates`, `version_view`, `template_items(version_id)` and `account_rules(version_id)`.
2. **Upload without a new dependency:** `POST /v1/methodology/templates/{name}/versions` takes the raw `.xlsx` request body (`Content-Type` for xlsx, with the size checked before it is read in full). Multipart would need `python-multipart`, which isn't on the allowlist.
3. **Apply** (D2):
   - It lives in `requests`, which already depends on engagements and owns request items.
   - `apply_methodology(ctx, engagement_id, version_id)`, in one unit of work:
     1. `lock_ref`, then `authorise("engagement.apply_methodology")`;
     2. `engagements.api.pin_methodology(tx, engagement_id, version_id)`, which raises `MethodologyAlreadyApplied` (409) unless the engagement's version is null;
     3. creates the request list if missing and inserts one item per template item, with `audit_area` set to the area name and `retrievability_tier`;
     4. audits `methodology.applied`.
   - Route: `POST /v1/engagements/{id}/methodology`.
4. **The graph** (D1):
   - It is assembled in `agents` (`agents/graph.py`, exported as `agents.api.engagement_graph`), not `engagements`. Agents already depends on engagements, requests and evidence, owns screening state, and is the graph's main reader.
   - It needs one new edge, agents → ledger, for the snapshot's accounts.
   - The `engagements` module can't import any of these modules (they all depend on it), so the alternative is four ADR-106 registration slots.
   - Mapping: each account goes to the first rule in rule order whose range `account_from ≤ code ≤ account_to` matches (text comparison), else `unmapped`.
   - Gaps: computed per AC-8, with `unmapped_gap_min_abs_usd` (setting, default 0, meaning any non-zero balance).
   - Route: `GET /v1/engagements/{id}/graph` (`engagement.read`; walls give 404).
   - New read helpers come from their owners' APIs:
     - requests: items with their tier;
     - evidence: the latest version per item and its review state;
     - ledger: `snapshot_accounts(snapshot_id)` (code, name, balance);
     - agents: the latest screening action per version (internal).
5. **Migration 0019:**
   - the five methodology tables (insert-only, forced RLS);
   - `engagements.methodology_version_id` (an UPDATE grant on that column);
   - `request_items.retrievability_tier`.

   Plus the schema-check maps.
6. **Matrix:** `methodology.manage` (firm_admin, practice_leader, `mfa_recent`), `methodology.read` (firm_admin, practice_leader, engagement_partner, manager) and `engagement.apply_methodology` (engagement_partner, manager), then the codegen.
7. **Docs:** the sample workbook layout goes in the engagements README, plus a generated sample `.xlsx` under `docs/product/methodology-sample.xlsx` (Q1).

**Protected paths (approval file):**
- `backend/src/abacus/modules/{engagements,requests,agents,evidence,ledger,identity}/**`;
- `backend/migrations/**`;
- `docs/architecture/permission-matrix.yaml`;
- `backend/src/abacus_tools/quality/{banned_patterns,schema_check}.py` and the BOUND-002 test.

### Questions for approval
- **D1. Assemble the graph in `agents` (adding the agents → ledger edge) instead of in `engagements` with four ADR-106 registrations?** *Recommendation: yes.* It's simpler, with one boundary change. The spec's interface becomes `agents.api.engagement_graph`; I'll amend §8.
- **D2. Put "apply methodology" in `requests` (it owns request items and already depends on engagements), with `engagements` exposing `pin_methodology`?** *Recommendation: yes.*
- **D3. Upload the workbook as the raw request body instead of multipart, so no new dependency is needed?** *Recommendation: yes.*
- **D4. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-07` — Implemented:
  - the workbook parser and template import (engagements);
  - apply methodology (requests);
  - the engagement graph and its route (agents);
  - migration 0019, the matrix actions, the BOUND-002 edge agents → ledger, the schema maps, the sample workbook and the READMEs.

  Gates, the schema check and unit tests pass. Full test runs deferred by the founder.
- `2026-10-07` — SPEC-008 approved and merged (#40). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| `methodology.read` is checked on the firm, so engagement partners and managers (engagement roles) can't list templates yet; they apply a version by ID and see the pinned version in the graph | `authorise` gives engagement roles nothing on firm resources | No; revisit with the UI |
| The import route's body isn't described in OpenAPI (AbacusRouter has no `openapi_extra`), so the generated client has no typed body for it | D3 (raw body) | No |
| Seeding records `request_item.created` per item plus `methodology.applied` | Same trail as items added by hand | No |
| Two concurrent applies to one engagement can deadlock (share lock, then update); Postgres aborts one, which gets 500 rather than 409 | Rare (a double submit); the pin itself stays single | No |
| The graph reads every snapshot of the engagement to pick the latest | Few snapshots per engagement in v1; a ledger metadata query later if slow | No |

## Questions for the human
- Design questions D1–D4 (above).

## Handoff
