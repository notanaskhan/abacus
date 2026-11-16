# C9 · Ledger consolidation (v2.1)

| Field | Value |
|---|---|
| Register row | C9 in `docs/contracts/README.md` (v2.1 additive) |
| Version | v2.1 (additive) |
| Status | stub (A-09-T03) |
| Provider epic | A-09 (N) |
| Consumers | K-04 (ENG-14), A-10 (FSP-02), T-06, AUD-31/32/33 |
| Freeze sprint | S45 (Fri Jul 21, 2028, A-09 §8.1) |
| Flag | entitlement `group_audit`; rollout `ledger.consolidation`, `assurance.group_audit` (A-09-T09) |
| Spec | `docs/specs/SPEC-658-a09-group-audit.md` (F1 to F4) |
| ADRs | ADR-341 (P-63), ADR-004, ADR-040, ADR-050 |

## 1. Purpose
Consolidations in `ledger`: structure (three tiers at most, ownership 100%, USD), trial balances attached per entity, label and period, finalize, lock and reopen, and the consolidated TB by level and entity with code's ties, tallies and attribution.

## 2. Who may call it
Every route answers, in order: a client principal 404; the action on the work item's engagement (walls 404, independence 403), or on a record's own path the entitlement first and the service's authorisation; 404 without `group_audit`; then 501 naming its task. Every field is classified; balances and evidence are client confidential, materiality firm confidential; nothing here carries TRI. Code: `backend/src/abacus/modules/assurance/group_contract.py` (ledger stays dependency-free, DEC-66, so assurance hosts the routes). Typed fixtures: `assurance/group_fixtures.py` (computed footings).

| Operation | Method and path | Matrix action | Task |
|---|---|---|---|
| Create · read · edit · discard | POST `/v1/audits/{wid}/consolidations` · GET/PATCH/DELETE `…/consolidations/{cid}` | `consolidation.edit` / `.read` | T13 |
| Structure · proposal | PUT `…/structure` (422 `structure_invalid`) · POST `…/structure/proposal` (201 a P-35 suggestion, the `audit.group_structure` code run; 409 `structure_source_missing`; DEC-5340) | `consolidation.edit` | T13, T14 |
| Attach · not needed | POST `…/entities/{ceid}/trial-balances` · POST `…/trial-balances/{tbid}/not-needed` | `consolidation.edit` | T13 |
| Bulk upload · pull all | POST `…/bulk-upload` · POST `…/pull-all` (202) | `consolidation.edit` | T18 |
| Finalize | POST `…/finalize` (409 `trial_balance_missing`) | `consolidation.finalize` | T13 |
| Lock · reopen | POST `…/lock` · `…/reopen` (reason) | `consolidation.lock` | T13 |
| Consolidated TB | GET `…/tb?level=1|2&view=consolidated|entity:<id>` | `consolidation.read` | T13 |
| Export | GET `…/export.xlsx` | `consolidation.export` | T13 |

## 3. Models
`ConsolidationOut` (status, lock state, entities with `TrialBalanceSlotOut`s, tiers, code's interim debits, missing slots, `allowed_actions`), `ConsolidatedTbOut` (columns, `TbRowOut` cells debit positive and credit negative with elimination tags, `GroupTalliesOut` total assets, NI, balanced and intercompany tie/off/pending). Footings pinned by the fixtures: interim debits 187,860,000; total assets 50,760,000; Level 2 39,760,000; NI 3,500,000 and 4,760,000.

## 4. Status words
`consolidation`, `consolidation_lock`, `consolidation_tb` (A-09-T04).

## 5. Human-only actions
Finalize, lock and reopen: EP and manager only; agent, system and support deny (I-AGENT-NEVER suite); `consolidation_events.actor_kind = 'human'` (A-09-T05).
