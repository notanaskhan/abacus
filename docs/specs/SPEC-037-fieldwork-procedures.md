---
id: SPEC-037
title: "Fieldwork, part 1: procedures and workpapers, starting with journal entry testing"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-042, ADR-050, ADR-052, ADR-065, ADR-111, ADR-115, ADR-131, ADR-132]
related_specs: [SPEC-008, SPEC-031, SPEC-034, SPEC-036]
created: 2026-10-19
updated: 2026-10-19
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Abacus collects and checks evidence until it's ready for review. This spec takes the next step into **fieldwork**: running audit procedures on the data and evidence Abacus already holds, and producing workpapers that a reviewer signs off.

It builds the shared machinery once and proves it with one procedure:
- **population** and **selection** by code (ADR-132);
- **assessment** of items, optionally by an agent, decided by people;
- **workpapers** rendered by code, with preparer and reviewer sign-off (ADR-131);
- **the first procedure: journal entry testing** (Q1), on the general ledger detail we already import (SPEC-034).

The search for unrecorded liabilities follows as the second procedure (Q2).

## 2. Problem and context
- **Where the hours are:** firms spend most of an audit's hours testing and documenting, not collecting. Today Abacus stops at "ready for review", and the team then works in spreadsheets outside it.
- **Data we already hold:** reconciled general ledger snapshots with every posting (date, account, type, reference, counterparty, description, amounts), trial balances, evidence linked to requests, and the firm's methodology templates.
- **Journal entry testing** is required on every audit (AU-C 240: responding to the risk of management override). Its population is the full journal listing, which Abacus already renders (TASK-070). The criteria are mechanical: manual entries, round amounts, entries after year end or near it, unusual accounts, users, weekends, and descriptions with certain words. That suits code.
- **Competitors** (Fieldguide, for example) show agents writing workpapers and picking samples. Our position: selections an auditor can re-perform, and figures computed by code.

## 3. Actors
| Actor | Role here |
|---|---|
| Engagement partner, manager | Set the procedure's parameters (materiality-based thresholds, criteria); review and sign workpapers |
| Senior, staff | Run the procedure, inspect support for selected entries, record exceptions, prepare the workpaper |
| The platform (code) | Builds and reconciles the population, applies the criteria and sampling, renders the workpaper |
| The entry assessor (agent, Q4) | Proposes, for each selected entry, whether its support explains it, citing the evidence |

## 4. Goals and non-goals
**Goals**
1. **Procedures** (new `fieldwork` module, Q5): a procedure is defined in versioned configuration and code. An engagement runs a procedure instance with its parameters, population, selection, items, exceptions, conclusion and workpaper.
2. **Materiality, entered by a person:** overall materiality, performance materiality and the trivial threshold on the engagement, with who set them and when. Procedures read them; nothing computes or suggests them in this spec (Q3).
3. **Population (code, ADR-132):** for journal entry testing, every journal entry in the engagement's latest reconciled general ledger snapshot, grouped into entries as TASK-070 does. The count and totals must tie to the snapshot, or the procedure stops with a reason.
4. **Selection (code):**
   - **criteria**, each a pure rule with a version: entries at or above a threshold derived from performance materiality; round amounts; posted within N days before or after year end; posted after year end; manual entry types; entries to rarely used accounts; descriptions matching a firm-editable word list; weekend dates;
   - **plus a recorded random selection** of the rest, by seed and count;
   - **plus a person's own picks**, each with a reason.
   - Every selected entry records which rules selected it. Re-running gives the same items.
5. **Support and assessment:**
   - each selected entry can be linked to evidence (existing evidence versions, or a request created for the client: "Support for journal entry JE-1042");
   - optionally, the entry assessor proposes whether the support explains the entry, with citations (Q4);
   - a person marks each entry `supported`, `exception` (with a note) or `not tested` (with a reason).
6. **Workpaper (ADR-131):** "Journal entry testing" rendered by code with these sheets:
   - Summary: parameters, population tie-out, criteria, counts, exceptions and the conclusion;
   - Population;
   - Selections, each with its rules and the person's result;
   - Exceptions;
   - Sign-off.

   It moves `draft` → `ready` (the preparer) → `reviewed` (another person). Any change makes a new draft version.
7. **Screens:**
   - a "Fieldwork" tab on the engagement listing its procedures and their status;
   - the procedure page: parameters, population tie-out, selection with each entry's reasons, results, and the workpaper preview and sign-off;
   - loading, empty, error and not-allowed states.
8. **Flag** `fieldwork.procedures` (off; on for the synthetic Dev firm).

**Non-goals**
- Financial statements, disclosures, forms and questionnaires.
- Computing or suggesting materiality.
- Documentation completion and locking (ADR-131 Q1, a later spec).
- Statistical sampling for substantive tests of details (later, in `sampling`).
- The search for unrecorded liabilities (SPEC-038, Q2).
- Any agent writing figures, selecting entries, concluding or signing (ADR-005, ADR-050).

## 5. User stories and acceptance criteria
**Story: Priya tests journal entries in an afternoon.** The general ledger is in. Dana, the manager, sets performance materiality at $120,000 and keeps the firm's default criteria. Priya opens Journal entry testing: 18,412 entries tie to the ledger. Code selects 46: 12 large, 9 posted in the last three days of the year, 7 round amounts, 4 to rarely used accounts, 3 on weekends, plus 11 at random. Priya links support for most from evidence already in Abacus, requests the rest from the client, marks two exceptions with notes, and signs the workpaper as ready. Dana reviews and signs it.

- **AC-1** Given a reconciled general ledger snapshot, when the procedure starts, then its population ties to the snapshot (entry count, debits and credits). If it doesn't tie, it stops with a reason and selects nothing.
- **AC-2** Given materiality and the criteria, then selection is a pure function: the same snapshot, parameters and seed give the same entries, each with the rules that chose it.
- **AC-3** Given materiality not yet set, then the procedure can't select, and says so.
- **AC-4** Given a selected entry, then a person records `supported`, `exception` (with a note) or `not tested` (with a reason). An agent's assessment, if any, is only a proposal with citations and the AI tag.
- **AC-5** Given the procedure, then its workpaper renders deterministically from its records. Signing `ready` needs every selected entry to have a result; `reviewed` needs a different person in a reviewer role. Any later change makes a new draft version, and earlier signatures stay with their version.
- **AC-6** Given a client, then nothing from fieldwork is visible to them, except requests created for support.
- **AC-7** Given every new screen, then loading, empty, error and not-allowed states exist, and colours come only from tokens.

## 6. Design notes
- **Module:** `fieldwork` (procedures, items, results, workpapers) and `sampling` (populations, selection methods: pure functions plus their records). Fieldwork reads ledger snapshots through `ledger.api` and evidence through `evidence.api`, and creates requests through `requests.api`.
- **Data** (insert-only where it records facts):
  - `engagement_materiality` (versions);
  - `procedures` (instance, definition and version, status);
  - `populations`;
  - `selections` (method, parameters, seed);
  - `selected_items` (entry key, rules);
  - `item_results` (append-only; the newest is current);
  - `workpaper_versions`;
  - `workpaper_signatures`.
- **Permissions:**
  - `materiality.set` (partner, manager);
  - `procedure.run` (partner, manager, senior, staff);
  - `procedure.read` (engagement team, reviewer);
  - `workpaper.sign_ready` (preparer roles);
  - `workpaper.sign_reviewed` (senior, manager or partner, not the preparer);
  - clients are refused by role.
- **Rendering:** streaming openpyxl, fixed metadata and ZIP timestamps, as `render_gl` does.

## 7. Delivery
- **TASK-083 (red):** materiality, `sampling` (populations, criteria, seeded selection), the procedure records, journal entry testing's population and selection, and the API.
- **TASK-084 (red):** results, linking support and requesting it, the workpaper renderer, sign-off, and the screens.
- **TASK-085 (red, if Q4 is yes):** the entry assessor agent, its evaluation suite, and its place in the procedure.

## 8. Test plan
| AC | Level | What |
|---|---|---|
| AC-1 | unit, integration | Tie-out on synthetic ledgers; a broken tie stops |
| AC-2 | unit (property) | Determinism; each criterion selects exactly its entries |
| AC-3, AC-4 | integration | Materiality gate; results and their audit |
| AC-5 | unit, integration | Byte-identical rendering; sign-off rules; versioning |
| AC-6 | integration | Client roles refused |
| AC-7 | vitest | States |

## 9. Open questions
All resolved: the founder approved every recommendation below on 2026-10-19.
- **Q1: the first procedure.** *Recommendation:* journal entry testing. It's required on every audit, its population is the general ledger we already import and reconcile, and its criteria are mechanical. The search for unrecorded liabilities needs payments made *after* year end, which our year-scoped ledger import refuses today. It therefore needs a new "subsequent period" import first, so it comes second.
- **Q2: the second procedure.** *Recommendation:* the search for unrecorded liabilities (SPEC-038). It adds a subsequent-period disbursements import, selection of payments by timing band against thresholds (as in the screenshot you shared), and matching to the year-end payables listing.
- **Q3: materiality.** *Recommendation:* entered by the partner or manager, with its benchmark and percentage recorded as text. Code derives the selection threshold from performance materiality by the firm's setting (default: 100%); nothing suggests materiality.
- **Q4: an agent in this spec.** *Recommendation:* yes, but last (TASK-085), and real-firm use only through SPEC-036's gates. The assessor reads each selected entry and its linked support and proposes "explained" or "not explained", with citations. People decide. Without it, the procedure is complete and useful.
- **Q5: one module or two.** *Recommendation:* `sampling` (already reserved in the module map) for populations and selection, reusable by later procedures; `fieldwork` for procedures, results and workpapers.
- **Q6: the default criteria.** *Recommendation:* the list in §4.4, with the window (3 days), the round-amount rule (a multiple of 1,000 at or above the trivial threshold) and the word list as firm settings, so a firm's methodology can change them. Each changes the selection only through a recorded parameter.
