---
id: ADR-132
title: In a procedure, code builds the population and selects the sample; agents assess items; people conclude
status: accepted
date: 2026-10-19
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, **stop** and raise it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Audit procedures such as journal entry testing or the search for unrecorded liabilities follow one shape:
1. define a population;
2. select items by criteria or sampling;
3. obtain and inspect support for each;
4. record exceptions;
5. conclude.

Another auditor must be able to re-perform the selection and get the same items. A model choosing items, or computing thresholds, can't guarantee that, and ADR-050 already forbids models doing arithmetic on financial data.

## Decision
1. **Population (code):** built from immutable snapshots (a trial balance, a general ledger) by a declared, versioned rule. It's stored as a population record: source snapshot, rule and version, filters, item count and total, which must tie to the source. Code reconciles the population to the ledger before anything is selected.
2. **Selection (code):** by a declared method:
   - criteria (thresholds, risk attributes);
   - statistical or haphazard sampling with a recorded seed;
   - a person's own picks, each with a reason.

   The method, parameters, seed and selected items are stored, so re-running the selection gives the same items. Thresholds come from the engagement's recorded materiality, entered by a person, never by a model.
3. **Assessment (agent, optional):** for each selected item, an agent may propose an assessment from the item and its evidence ("the invoice dates the service to December; it relates to the prior period"). Each proposal cites what it read and is shown with the AI tag. A person accepts, changes or rejects each one (ADR-005).
4. **Conclusion (person):** exceptions are recorded by people, and the procedure's conclusion is a person's, written into the workpaper (ADR-131).
5. **Procedure definitions are code and configuration, versioned:** the population rule, selection methods allowed, what evidence each item needs, and the workpaper layout. A firm's methodology names which procedures apply to an engagement. Changing a definition is a new version; running procedures keep theirs.

## Options considered
### Option A: code selects, agents assess, people conclude — chosen
- Pros: re-performable; ADR-050 holds; agents help where judgement on documents is needed.
- Cons: every procedure needs its rules written as code.

### Option B: an agent runs the whole procedure and writes the workpaper
- Pros: fast to demonstrate.
- Cons: not re-performable; figures and selections can't be trusted; fails ADR-050.
- Why rejected: an auditor can't rely on it.

## Consequences
**Positive**
- Selections and populations are evidence-grade; agents' work is bounded and reviewable.

**Negative / costs accepted**
- Each new procedure is engineering work, not a prompt.

**Follow-up work created**
- SPEC-037; the `sampling` module (populations, selection methods).

## Enforcement
- [ ] Test: the same population, method, parameters and seed always select the same items.
- [ ] Test: a population ties to its source snapshot's totals.
- [ ] Agent specs for assessors hold no action that selects, concludes or signs (task scope).

## Guidance for agents
When building a procedure, write the population and selection as pure functions over snapshots. Models are given selected items and their evidence, and return assessments with citations only.

## Revisit when
- Firms want to bring their own sampling tools' selections (import a selection, keeping its record).

## Related
- ADRs: ADR-004, ADR-005, ADR-050, ADR-052, ADR-065, ADR-131.
- Specs: SPEC-034, SPEC-037.
