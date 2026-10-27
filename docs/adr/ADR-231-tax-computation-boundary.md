---
id: ADR-231
title: "Tax computation boundary: the engine of record computes tax, credits and filed forms; Accrued shows engine values only from approved imports"
status: proposed
date: 2026-10-28
deciders: ayushkbhatia, tax CPA
risk_zone: amber
proposal: P-68
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by T-02-T36 (TASK-1705) in S14 as a pre-window task, whatever the M8
go/no-go returns, because T-04 needs it too. Accept by **Fri May 28, 2027** (the builder and the
tax CPA). T-02-T13 and T-02-T18 merge no engine-summary code before this is accepted on main.

## Context
Accrued coordinates tax work around an engine of record (CCH Axcess first; DEC-49 and P-18: a file
bridge, never transmit). Reviewers see figures on TAX-02 (estimate, tax plan, carryforwards,
two-year rows), TXP screens (TB→TTB, M-1/M-2/M-3, allocations, capital, basis) and the portal (K-1s).
If Accrued computes tax liability or credits itself, two numbers for the same return can disagree,
and the one a client or the IRS sees is the engine's. If Accrued shows engine numbers that no person
approved, a stale or partial import reaches a reviewer as fact.

DEC-77 (chapter 09) decided (b): the engine computes; Accrued computes only workpaper figures in
code. DEC-78 decided that filed forms and final K-1/K-3 PDFs come from the engine and draft K-1s
never reach the portal. ADR-050 (code computes, models judge) already keeps models out of
arithmetic. This ADR is the computation-boundary ADR chapter 01 names (F-02 proposal P-68).

## Decision
1. **The engine computes tax.** Tax liability, credits, payments applied, refunds and balances
   due, and every filed form (federal, state, NY and NYC, 1040-X, the 706 tentative tax) are
   computed by the engine of record. Accrued never computes them, in code or by model.
2. **Engine values only from approved imports.** An engine figure is shown only from the latest
   import checkpoint a named reviewer, manager or partner **approved** (the `return_engine_summaries`
   read model, DEC-49 "Import pending approval"). A pending or rejected import shows nothing, not a
   stale value. Every engine figure carries its import's provenance (import id, approved by, when).
3. **What Accrued computes, in code, with golden tests** (blueprint §9.8, CPA-reviewed): workpaper
   figures — TB→TTB; M-1, M-2 and M-3; allocations including §706(d) and waterfalls; capital
   accounts; §752 basis; PTET; AAA; DNI; sourcing; the §199A worksheet — and display arithmetic on
   imported figures (the effective rate, a Δ% between years, ties and differences). Rounding is
   largest remainder so every split foots. A tie-out of an engine figure against Accrued's own
   workpaper is labelled "Accrued tie-out (shadow)" and never replaces the engine's value.
4. **Filed forms and K-1 PDFs come from the engine** through the file bridge (DEC-78). Accrued's
   T17 renderer shows review previews from an approved checkpoint, watermarked "Draft — not for
   filing". **Draft K-1s and draft prints never reach the portal**; release of an engine K-1 is a
   person (T-02-T21).
5. **No model touches tax figures.** No T-02 or T-04 module imports `ai_gateway`; no tax workflow
   calls a model to compute or restate a figure (ADR-050; agent text about a return uses fact
   references, ADR-230).
6. **Never transmit** (P-18, DEC-49): no MeF, no ERO role; "Mark exported" and "Mark transmitted"
   are manual, acknowledgements are imported.

## Options considered
### Option A: the engine computes; Accrued shows approved imports and computes workpapers — chosen
- Pros: one number of record; the CPA's engine stays authoritative; Accrued's own figures are
  workpapers with golden tests; aligns with never-transmit.
- Cons: the reviewer waits on an import to see the estimate; engine-specific import work.

### Option B: Accrued computes tax
- Pros: instant figures; no import dependency.
- Cons: two numbers of record that can disagree; a tax-engine product Accrued is not; CPA liability.
- Why rejected: DEC-77; scope (D1–D10).

### Option C: show every import as soon as it lands
- Pros: fewer clicks.
- Cons: a stale or partial import reads as fact.
- Why rejected: an approval step is the human decision (INV-1).

## Consequences
**Positive**
- Reviewers, partners and clients see one set of engine numbers, each traceable to an approved import.
- Workpaper computations are testable and CPA-reviewed in code.

**Negative / costs accepted**
- TAX-02's estimate is blank until an approved import exists.
- Every new engine needs its own import mapping (other engines show "Coming soon").

**Follow-up work created**
- T-02-T13 (TAX-02 engine summary from `return_engine_summaries`) and T-02-T18 cite this ADR.
- T-04 (classification chips, TXI-02) and T-05 (TXP screens) cite it for workpaper figures.
- Chapter 09 §9.4.2 gains the P-68 row with this number.

## Enforcement
- Import-linter contract: no tax module imports `ai_gateway` (T-02 §4).
- The engine-summary read model exposes only approved imports (a service test per state:
  pending, rejected, approved, superseded).
- Golden tests for each workpaper computation (blueprint §9.8 figures).
- The portal K-1 route refuses a draft (DEC-78) and the dist crawl finds no draft watermark text
  in portal bundles.
