---
id: SPEC-043
title: "Findings register and the summary of uncorrected misstatements: a finding from a fieldwork exception (or by hand), a misstatement on it, and the totals against materiality"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-050, ADR-131]
related_specs: [SPEC-037, SPEC-038, SPEC-040]
created: 2026-10-20
updated: 2026-10-20
---

## 1. Summary
The plan's AUD-15 (findings register) and AUD-16 (misstatements), first slice (epic A-06).
- **Raising a finding.** A team member raises a finding on a fieldwork exception, prefilled from the row, or by hand on the engagement.
- **Recording a misstatement.** A senior, manager or partner records a misstatement on a finding:
  - **kind**: factual, judgmental or projected;
  - **amount**: the overstatement (+) or understatement (−);
  - **account**: from the engagement's ledger;
  - **corrected**: whether the client has corrected it.
- **The summary of uncorrected misstatements.** Code totals the uncorrected misstatements by kind (ADR-050). It leaves out each one at or below clearly trivial, and sets the total against performance and overall materiality.

People decide; the agent does nothing here.

## 2. Acceptance criteria
- **AC-1** Raise a finding with a title (1–200 characters) and a description (up to 2,000 characters), optionally linked to a procedure and one of its current rows. Insert-only, with an audit event.
- **AC-2** Record a misstatement on a finding. The newest record per finding counts, and the earlier ones stay (insert-only). The amount is a non-zero decimal.
- **AC-3** The summary, computed by code:
  - per kind, the total of uncorrected misstatements above clearly trivial, and their count;
  - the grand total, compared with performance and overall materiality ("below performance", "at or above performance", "at or above overall");
  - "set materiality first" when there's no materiality.
- **AC-4** Permissions:
  - raise (`finding.raise`): staff, senior, manager, partner;
  - record a misstatement (`misstatement.set`): senior, manager, partner;
  - read (`procedure.read`);
  - the agent is denied both, and independence is required.
- **AC-5** A Findings tab holds the register table (title, source, misstatement, corrected), "New finding", and the summary card. A fieldwork row whose result is an exception offers "Raise finding".

## 3. Data
- `findings` (insert-only): `tenant_id`, `engagement_id`, `procedure_id` (null), `selected_item_id` (null), `title`, `description`, `raised_by`, `created_at`.
- `misstatements` (insert-only): `tenant_id`, `finding_id`, `kind` (`factual` | `judgmental` | `projected`), `amount` numeric(18,2) ≠ 0, `account_code` (null), `corrected` bool, `recorded_by`, `created_at`.

## 4. Out (later)
Deficiencies and severity (the partner's decision, D / SD / MW), the AJE from a misstatement, and the representation letter's list.
