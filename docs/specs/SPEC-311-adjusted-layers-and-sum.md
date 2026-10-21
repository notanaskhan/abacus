---
id: SPEC-311
title: "Recorded entries in the trial balance's AJE, RJE and Final layers, and the summary of uncorrected misstatements"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-050, ADR-005]
related_specs: [SPEC-301, SPEC-309, SPEC-310]
created: 2026-10-21
updated: 2026-10-21
---

## 1. Summary
This is A-06 F3 and F4 over the entries SPEC-301 already records.

- Fieldwork registers as the ledger's adjustment source, which closes the fail-closed slot from SPEC-309.
- An entry counts as recorded once the partner has approved it or the client has accepted it. A recorded entry adds to its account's AJE or RJE column and to Final.
- A proposed entry appears only as a count. A passed entry (declined by the client) never enters a layer; it goes to the summary of uncorrected misstatements (SUM).
- Code computes every figure. Whether the aggregate is material stays the partner's judgement.

No migration.

## 2. Acceptance criteria
- **AC-1 Layers.**
  - With a source registered, the trial balance view carries per account `aje`, `rje`, `final` (EOY + AJE + RJE) and the refs of the entries that touch it.
  - It carries the Final totals, with Final balanced exactly when the positive finals equal the negative finals.
  - It carries the count of proposed entries.
  - An entry's account that isn't in the trial balance appears as a new line with no unadjusted balance.
  - Without a source, Final is still refused (`layer_unavailable`).
- **AC-2 Leadsheets.** `?layer=final` makes CY the final balance; Δ and Δ% follow.
- **AC-3 TB() and staleness.**
  - `TB("1000","FINAL")` reads the final balance.
  - A paper using it records the refs of the recorded entries in its content hash, so recording an entry shows its sign-offs as stale.
- **AC-4 SUM.**
  - `GET /v1/engagements/{id}/uncorrected-misstatements` returns the passed entries (ref, description, amount, accounts) and the aggregate.
  - It compares the aggregate against the decided materiality, or the newest proposed one, flagged as not decided. It returns:
    - overall, performance and clearly-trivial materiality;
    - the band: clearly trivial (at or below trivial) · below performance · below overall · at or above overall;
    - the headroom to overall.
- **AC-5 Web.**
  - The trial balance gets an Unadjusted / Final toggle. Final is disabled, with its tooltip, until a source exists.
  - Final shows AJE, RJE and Final columns with entry tags, the Final balance pill, and the proposed-entries note. Leadsheets follow the toggle.
  - Findings' Entries view adds the SUM card.

## 3. Out of scope
- C8's `proposed_entries` model and threshold policies (A-06 T01–T06).
- Posting (C-02).
- The partner's SUM conclusion record.
- Evaluating the SUM per FS line (needs A-03's mapping).
- Review notes on the trial balance.
