---
id: TASK-2229
title: Wire the designed links of the S17 Lane 2 screens (DEC-1272 follow-up)
spec: SPEC-000  # DEC-1272's deferral; link-contract rule 1 (SPEC-307 AC-8)
acceptance_criteria: [AC-1]  # quoted under Objective
risk_zone: green
status: in-review
epic: F-04
plan_key: DEC-1272-follow-up
branch: s17-wire-links
created: 2026-10-30
updated: 2026-10-30
---

## Objective
DEC-1272 kept TAX-01, TAX-02, HOME-02, SHL-16, ADM-05, CLI-05 and TAX-09 `planned` "until their
designed links are wired with `to.<ID>()`". Wire every designed link whose two ends are built and
turn the screens `fixture` where rule 1 then holds.

Acceptance: "link-contract.test.ts passes with the screens on fixtures, and each wired link has a
test."

## Plan
- `routes/to.ts`: `hrefOf` and the `ov` overlay builders; `app-core/open.ts`: `useOpenHref`,
  `useOpenOverlay`; rule 1 reads `ov.<ID>(` for a target with no path (synthetic case added).
- Sources: HOME-01, HOME-02 (`hosts.ts`), TAX-01, TAX-02, ADM-01, ADM-05, FIL-01 (and its fixture
  route); routes drop the handlers the screens now own.
- Tests: `routes/links.test.ts`, ADM-05's client link, HOME-01's popover link.
- Rollback: revert the commit; the manifest entries return to `planned`.

## Progress log
- 2026-10-30: built on s17-wire-links. CLI-05 and TAX-09 stay planned (DEC-1273 names why).
