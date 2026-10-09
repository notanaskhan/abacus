---
id: TASK-038
title: Classification, automatic retrieval and the evidence board
spec: SPEC-022
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: amber
status: awaiting-plan-approval
branch: task-038-classification-board
worktree:
created: 2026-10-09
updated: 2026-10-09
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-022 (approved, Q1–Q7): tier meanings, rule-based classification with overrides, availability from the live connection, automatic retrieval behind a flag, and the Board's filters and summary.

## Scope
All of SPEC-022.

## Context to load
- Spec: `docs/specs/SPEC-022-classification-and-evidence-board.md`
- Code:
  - `requests` (service, repository, import, methodology application);
  - `connections` (`start_retrieval`, `trigger_retrieval`, `live_connection_for`, `CONNECTORS`, `SUBSCRIPTIONS`);
  - `identity.context` (`AuthContext`), `kernel.flags`, `feature-flags.yaml`, the glossary;
  - `apps/web` `Board`.

## Plan
- [ ] Plan approved by human

### Design (for founder review)
1. **Glossary:** the A to E table from SPEC-022 §4 goes in "Retrievability tier", with "retrievable = A to C".
2. **Rules** (`requests/classification.py`, pure code):
   - `RULES`: ordered `(rule_id, keywords over description and area, tier, dataset)`;
   - the first version is small and conservative (D1): trial balance → A `trial_balance`; general ledger or GL detail → A `general_ledger`; journal listing → A `journals`; aged receivables or payables → A `ar_aging` / `ap_aging`; invoices or bills → C; bank confirmations, contracts, board minutes, legal letters → E; reconciliations, schedules, roll-forwards → D;
   - `classify(description, area, methodology_tier) -> Classification(tier, dataset, source, rule_id)`, with precedence override > methodology > rule > none;
   - only `trial_balance` is a dataset any connector delivers today, so the other A items show "not available".
3. **Data (requests migration 0030):** `request_items` gains `dataset`, `tier_source` and `tier_rule`. The app may update those and `retrievability_tier`.
4. **Classifying:**
   - the requests service classifies inside the creating unit of work (add, import, methodology application) and audits `request_item.classified` (the rule ID as a fingerprint reference);
   - `PUT …/request-items/{item_id}/tier` (`request_item.update`) sets or clears an override, audited `request_item.tier_overridden`;
   - `RequestItemClassified` is emitted when an item becomes A with a dataset.
5. **Availability (D2):**
   - requests can't import connections (connections depends on requests), so connections registers `available_datasets(tenant, client_entity_id) -> frozenset[str]` into requests through an ADR-106 registration slot (the live connection's `capabilities().datasets`);
   - unregistered means nothing is available (fail closed).
   - The items list gains `dataset`, `tier_source` and `available`.
6. **Automatic retrieval (D3, D4):**
   - connections subscribes to `connection.created` (every open A item with an available dataset, on the engagements of that client entity) and to `request_item.classified` (that one item);
   - each runs only when the flag `auto_retrieval` is on for the firm, then calls `trigger_retrieval` with a context for the connection's creator;
   - **that context (D3):** a new identity function `member_context(tenant_id, user_id) -> AuthContext | None` builds an `AuthContext` for a live membership, with no MFA time, for background work started by the platform on a person's standing consent. It returns None when the membership isn't active, and then nothing is retrieved (logged);
   - the existing caps, slots and idempotency apply, and `sync_run.started` records that person.
7. **Flag (D4):** `auto_retrieval` (boolean, default off: the safe behaviour) goes in `feature-flags.yaml`. `make seed` turns it on for "Dev firm", so it's on locally and off elsewhere until you switch it on.
8. **Board summary:** `GET /v1/engagements/{id}/board-summary` (`request_item.read`, filtered by `visible_items`). It returns:
   - counts by status;
   - "retrieved, never asked": items whose first fulfilling version was retrieved and that have no uploaded version created before it;
   - the retrievable share (A to C over classified items).
9. **Web (Board):**
   - a filter bar (status, area, tier including unclassified, source, client assignee, text), kept in the URL search params;
   - a summary strip;
   - tier chips with the meaning as a tooltip;
   - "not available from {provider}" on A items;
   - a tier override menu for those allowed (`request_item.update`; the API decides).

**Protected paths (approval file).** I checked these up front:
- `backend/src/abacus/modules/connections/**` (the subscriber and the registration);
- `backend/src/abacus/modules/identity/**` (`member_context`);
- `backend/tests/unit/**`;
- `docs/architecture/feature-flags.yaml` and `docs/product/glossary.md` (policy files);
- `backend/src/abacus_tools/quality/schema_check.py` (the new update columns);
- `backend/src/abacus_tools/quality/banned_patterns.py` (in case the summary's lookups need LIST-001 handling).

Not needed:
- `api/app.py` (no new routers);
- the permission matrix (no new actions).

### Questions for approval
- **D1. Start with the small, conservative rule set above, and leave everything else unclassified for staff (or the later classifier) to set?** *Recommendation: yes.* Wrong tiers cost more than missing ones.
- **D2. Have connections register dataset availability into requests through a registration slot (ADR-106), with no module-boundary change?** *Recommendation: yes.*
- **D3. Add `identity.member_context` so the platform can act for a person on their standing consent in background work (with no MFA, refusing inactive members)?** *Recommendation: yes.* Only this subscriber uses it now; every use must be on behalf of the person whose consent applies. Any new caller needs its own approval.
- **D4. The flag defaults to off everywhere, and the local seed turns it on for Dev firm?** *Recommendation: yes.* Flags have firm values and one default, not one per environment, so this gives "on locally, off elsewhere".
- **D5. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — SPEC-022 approved and merged (#70). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
