---
id: SPEC-022
title: Classification and evidence board
status: draft
owner: founder
risk_zone: amber
related_adrs: [ADR-005, ADR-037, ADR-040, ADR-047, ADR-050, ADR-069, ADR-071]
related_specs: [SPEC-000, SPEC-003, SPEC-007, SPEC-008, SPEC-020, SPEC-021]
created: 2026-10-09
updated: 2026-10-09
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
This is Phase 2 increment 5. It has three parts:
- **Classification:** every request item gets a retrievability tier (A to E) and, where it can be retrieved, the dataset it maps to. The classification follows the methodology tier where the firm set one, then rules (Q2). The tier an item can actually reach depends on what the engagement's connection can deliver ("tiers from connection capabilities").
- **Automatic fulfilment:** when an item is retrievable from the live connection, the platform starts the retrieval itself, so nobody has to ask the client (Q4).
- **The evidence board:** the Requests board gains filters (status, area, tier, source, assignee, text), counts by status, and the "retrieved, never asked" count (Q5).

## 2. Problem and context
- **Tier letters have no meaning yet:** they come only from methodology templates (SPEC-008), and nothing defines what each letter means in the product (Q1).
- **Retrieval is manual:** someone presses Retrieve on each item.
- **The Board is an unfiltered list,** with no measure of the platform's core promise: evidence retrieved without asking the client.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engagement team | Sees tiers and filters; may override an item's tier (`request_item.update`) |
| The platform | Classifies items and starts retrievals for retrievable ones |
| Client admin | Their connection's capabilities decide what is retrievable; retrievals run on their consent (Q4) |

## 4. Goals and non-goals
**Goals**
- **Tier meanings (Q1),** fixed in the glossary:

  | Tier | Meaning | How it is fulfilled |
  |---|---|---|
  | A | A standard report the connected system produces as is (trial balance, GL detail, journal listing, agings) | Retrieved automatically |
  | B | Derivable by code from retrieved ledger data (a lead schedule, a roll-forward) | Retrieved, then computed (later increment) |
  | C | A document attached to records in the connected system (invoices, bills) | Retrieved as attachments (later increment) |
  | D | Held by the client, not in the connected system (reconciliations, schedules they prepare) | Requested from the client |
  | E | From third parties or physical records (bank confirmations, contracts, minutes) | Requested from the client |

  A to C count as "retrievable" (build plan §4.1).
- **Classification (rules first, Q2):**
  - **The order:** a manual override wins; else the methodology tier; else keyword rules over the description and area (versioned in code, for example "trial balance" → A, dataset `trial_balance`; "bank confirmation" → E); else unclassified.
  - **The dataset:** each A rule names the dataset it needs.
  - **Effective tier:** an A item whose dataset the live connection can't deliver (from `capabilities().datasets`) shows "A, not available from {provider}" and is treated as requested from the client until it can be.
  - **When it runs:** on item creation and import, on methodology application, and when an override is cleared. Audited (`request_item.classified`, with the rule's ID).
- **Overrides:** `PUT …/request-items/{item_id}/tier` (`request_item.update`): a tier, or clearing the override. Audited.
- **Automatic fulfilment (Q4):**
  - **What triggers it:** a connection becoming active, or an item becoming A with an available dataset.
  - **What it does:** the platform starts a retrieval for each open A item with an available dataset, for the engagement's fiscal period, through the existing retrieval workflow (work slots, action caps and audit unchanged).
  - **Whose retrieval it is:** it runs as the system on behalf of the client admin who connected.
  - **Idempotent:** a running or successful run for the item and period isn't repeated.
- **Board:**
  - filters for status, audit area, tier (including unclassified), source (retrieved, uploaded, none), client assignee and description text, kept in the URL;
  - counts by status;
  - a "Retrieved, never asked" figure (Q5), with the retrievable share of the request list (A to C as a percentage).

**Non-goals**
- Model fallback for unclassified items (Q3).
- Tier B computation and tier C attachment retrieval (later increments, with real connectors).
- Follow-ups to the client (increment 8).

## 5. User stories and acceptance criteria
- **AC-1** Given a new, imported or methodology-seeded item, then it gets a tier and, for A, a dataset, by the order in §4. Each classification is audited with the rule that decided it.
- **AC-2** Given a team member allowed `request_item.update`, when they override a tier or clear the override, then the item's tier changes and the change is audited. Others can't.
- **AC-3** Given the live connection's capabilities, then an A item whose dataset isn't available shows as not available from that provider and isn't retrieved automatically.
- **AC-4** Given a connection becomes active, or an item becomes A with an available dataset, then a retrieval starts for each open A item within the engagement's fiscal period, once, under the existing caps. When the engagement's daily action cap is reached, the rest wait and the cap is reported, as today.
- **AC-5** Given the Board, then filters narrow the list and survive a reload (they're in the URL). Counts by status are shown, and so is the "Retrieved, never asked" figure, defined as in Q5.
- **AC-6** Given every new state, then loading, empty ("No items match these filters"), error and not-allowed states exist, and colours come only from tokens.

## 6. Behaviour and flows
1. **Classification** runs in the requests service inside the same unit of work as the item's creation or change.
2. **Auto-retrieval** is a subscriber:
   - `connection.created` triggers it for every open A item of the engagements on that client entity;
   - `request_item.classified` triggers it for one item.

   Both go through `connections.start_retrieval`, so the caps and idempotency already there apply.

## 7. Domain and data changes
`request_items` gains:
- `dataset` (nullable);
- `tier_source` (`methodology`, `rule`, `override`, or null for unclassified);
- `tier_rule` (the rule ID, nullable).

No new tables.

## 8. Interfaces
- `PUT /v1/engagements/{id}/request-items/{item_id}/tier`.
- The items list gains `dataset`, `tier_source` and a computed `available` (whether the live connection can deliver the dataset).
- `GET /v1/engagements/{id}/board-summary`: counts by status, "retrieved, never asked", and the retrievable share.

## 9. Authorisation and tenancy
- **Overrides:** `request_item.update` (unchanged roles).
- **Board summary:** `request_item.read`.
- **Auto-retrieval:** a `SystemContext` for the run's engagement, on behalf of the connecting client admin (Q4). `evidence.upload` already allows `system`.

## 10. AI behaviour
None. Classification is rules only in this increment (Q3).

## 11. Integrations
Connector `capabilities()` only.

## 12. Edge cases and failure modes
- **No fiscal period or no live connection:** nothing is retrieved automatically, and items show why.
- **An item's description changes later:** reclassified unless overridden.
- **The connection is revoked:** A items show "not available" again, and auto-retrieval stops.
- **Many A items at once:** the existing action cap and work slots pace them.

## 13. Security and privacy
- **Rules are code:** they never come from client text.
- **Descriptions are firm text,** matched by keywords, never executed.

## 14. Audit trail and evidence integrity
`request_item.classified`, `request_item.tier_overridden`, and the existing `sync_run.started` (with the system actor, on behalf of the connecting client admin).

## 15. Observability
Counts of items by tier and source, auto-retrievals started and refused (by code).

## 16. Performance and scale
Requests lists of up to 2,000 items. The summary is one aggregate query.

## 17. UX
The SPEC-016 Board, with a filter bar above the list and a summary strip (counts, "retrieved, never asked", retrievable share). Tier chips show the letter with a tooltip giving its meaning.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1, AC-3 | unit | Rule table, precedence, availability from capabilities |
| AC-2, AC-4 | integration | Override and audit; auto-retrieval on connect and on classification, once, under caps |
| AC-5, AC-6 | component (vitest) | Filters, URL state, summary strip, states |

## 19. Rollout
One requests migration. Auto-retrieval sits behind a feature flag (`auto_retrieval`, default on locally, off elsewhere until staging is proven) (Q6).

## 20. Open questions
- [ ] **Q1: what the tiers mean.** *Recommendation:* the table in §4 (A: a standard report from the connected system; B: derivable by code; C: an attachment in the system; D: held by the client; E: third parties or physical), added to the glossary. This is a product definition, so it's yours to confirm or change.
- [ ] **Q2: precedence.** *Recommendation:* override > methodology tier > rules > unclassified. The firm's own template beats generic rules.
- [ ] **Q3: model fallback.** *Recommendation:* defer it to its own spec, with a classifier agent and its evaluation suite (the Phase 2 exit needs a classifier suite at agreed thresholds). Until then, unclassified items show "Unclassified" and staff can set the tier.
- [ ] **Q4: automatic retrieval and on whose behalf.** *Recommendation:* start retrievals automatically for available A items, on behalf of the client admin who connected (their consent is the authority, ADR-040), paced by the existing caps.
- [ ] **Q5: "retrieved, never asked".** *Recommendation:* items whose first evidence was retrieved, with no client upload before it. Follow-ups don't exist yet (increment 8); once they do, this gains "and never followed up".
- [ ] **Q6: rollout.** *Recommendation:* a feature flag `auto_retrieval`, on in local and test, off in staging and production until you switch it on.
- [ ] **Q7: protected paths.** *Recommendation:* an approval file covering:
  - `connections/**` (the auto-retrieval subscriber and capabilities);
  - `backend/tests/unit/**`;
  - `schema_check.py` (the new update columns);
  - `banned_patterns.py` (if needed);
  - `api/app.py` (if a router is added);
  - the flag registry (the flags file, if protected).

## 21. Future / explicitly deferred
- The classifier agent (model fallback) and its evaluation suite.
- Tier B computation and tier C attachments.
- "Never followed up" once follow-ups exist (increment 8).
