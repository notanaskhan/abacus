---
id: ADR-151
title: Busy-season change policy - the freeze starts at the first real go-live
status: proposed
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
**Accept with the Dec 14-18, 2026 bundle** (sprint S4). ADR-092 freezes January to March and starts now, tuned to audit. With no real firm before May 2027, a freeze through Q1 2027 would slow building on staging for no risk reduction. Plan decision DEC-68 settles this; this ADR is P-29. Plan risk zone is amber; this file carries red as instructed.

## Decision
- **The freeze starts when the first non-synthetic firm goes live.**
- **Windows are per firm, from the date that firm first holds real data** (chapter 01 §1.2.4): Jan 1 - Apr 20 for every live firm, and Sep 1 - Oct 20 for firms live on tax or EBP work, each preceded by a readiness test.
- **Mini-freezes** on Sep 8-15, Sep 23-30 and Oct 8-15, and **no production promotion in a deadline week** (Mar 15, Apr 15, Sep 15, Sep 30, Oct 15).
- **Inside a window** only fixes and already-flagged features ship: live-path code changes only to fix defects; new modules merge dark behind default-off flags; migrations are expand-only; flags flip per firm in the Tuesday evening window with the journey passing on staging, a shadow run and a written rollback; no model or prompt upgrade without the full evaluation suite and a shadow run.
- **There is no year-one exception.** The first real firm's first window is a window like any other.
- **Until go-live,** the 18 Dec train is a stability milestone, not a freeze.

## Options considered
### Option A: from the first real go-live — chosen
- Pros: full-speed build on staging through Q1 2027; windows match tax seasons.
- Cons: policy switches on a date known only at go-live.

### Option B: ADR-092 January to March from now
- Pros: already accepted.
- Cons: tuned to audit; freezes work with no real firm.
- Why rejected: no risk is being protected before go-live.

## Consequences
**Positive**
- Q1 2027 build runs at full speed; windows follow tax deadlines.

**Negative / costs accepted**
- Release cadence changes on the go-live date.

**Follow-up work created**
- Code: `deploy/windows.yaml` and `abacus_tools/release_windows.py` (Q-04-T001/T002, S12); RB-16 readiness runbook (Q-04-T055, S21).
- Specs: release plan amended (DEC-05); `docs/ops/release-windows.md`.
- Glossary: change window, mini-freeze, deadline week (`docs/product/glossary.md`).
- Matrix: none.
- Registry: `deploy/windows.yaml` (protected) holds the dated windows.

## Enforcement
- [x] Lint rule: `make windows` validation in `make check-fast`.
- [ ] Architecture / dependency rule in CI: none.
- [x] Test: `in_window(tenant, at)` and `deadline_week(at)` cases.
- [x] Hook or protected path: `deploy/windows.yaml`.
- [ ] Reviewer agent checklist item: none.
- [ ] Advisory only — reason: n/a

## Guidance for agents
Before go-live, do not apply ADR-092's freeze. After it, check the window before promoting.

**Do**
```
if in_window(tenant, now): only_fixes_and_flagged_features()
```

**Don't**
```
deploy_schema_change()   # inside a window
```

## Revisit when
The first real firm's go-live date is set, or a second tax cycle shows the windows are wrong.

## Related
- ADRs: supersedes ADR-092's clause "From January to March ... Major changes ship October to December" (replaced by the windows above); amends ADR-075 (Busy-season readiness) so the December load test precedes each window.
- Plan: P-29; DEC-68; ch. 02 D-15; ch. 06 D-OPS-01 and §3.6 (on-call).
- Specs: release plan.
