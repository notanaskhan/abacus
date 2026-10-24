---
id: TASK-1030
title: Screen contracts for POR-03, POR-04, POR-14, POR-20 and ADM-10 (R-01-T03)
spec: SPEC-323
acceptance_criteria: [AC-1]
risk_zone: green
status: done
epic: R-01
plan_key: R-01-T03
branch: s7-r01-portal-requests
created: 2026-10-24
updated: 2026-10-24
---

Plan of record: R-01 (docs/plan/epics/R-01.md §2.1, §5).

## Objective
"Every artboard maps to a data condition, persona, clock and tier, and the link-contract test knows
every outbound target of the five screens." Write R-01's five screen contracts from the handoff:
44 artboards (POR-03 12, POR-04 7, POR-14 6, POR-20 12, ADM-10 7) with persona, clock, parity tier,
copy keys and outbound links; Deviations for DEC-58 a/c/e/f/g, DEC-59, DEC-35, DF-03, DF-15,
DF-40, the POR-14d viewer and the POR-14f no-oracle copy; the POR-04 e/f variant-slot contract.

## What changed
- `docs/screens/POR-03.md` (a–i, motion, c2, M), `POR-04.md` (a–g, with the `RequestSheet`
  question and decision slot contract for C-01 and T-06 / T-09), `POR-14.md` (a–f),
  `POR-20.md` (a–l) and `ADM-10.md` (a–g), on `_TEMPLATE.md`, modelled on `POR-02.md`. Each names
  its building task, the API rows and matrix actions from R-01 §4.3 (spelt per DEC-139 where new:
  `portal_documents.read`), status objects in their `client_label` wording, copy keys verbatim from
  spec.md and the built artboards, links, acceptance, figures that must foot, AVOID lists,
  deviations, parity tiers from R-01 §5.5 and open gaps.
- Links: every designed link of the five screens in `handoff-links.json` is named (POR-03 → POR-19;
  POR-20 → ADM-10, CLI-04, SIG-01, TXP-12, AUD-14, CLS-11; ADM-10 → ADM-01…09, ADM-11, ADM-12,
  POR-20, POR-02); POR-04 and POR-14 have no designed outbound link. Every ID named is already a
  manifest screen, so no manifest entry changed.

## Decisions taken in the session
- POR-03 c2 and POR-04 c keep the README clock 9:12 AM (the time of Claire's email); POR-14 b–e
  render at their own dates (Sep 22, 23, 11, 28); POR-04 e at 1:10 PM.
- POR-14 d's viewer is `harborline-certifications`, not Sam Ortiz (R-01 §2.1); f reads "This link
  has expired or was already used" (no oracle, P-08-T18).
- POR-20 h's sample respondent is Rachel Imholt (Summit Trail Outfitters), the handoff's POR-17
  contact. ADM-10 e's Reconnect v1 differs from POR-20 i's; POR-20 i's copy is the seeded v1 and
  ADM-10 e's drawer content is masked in parity (open gap for R-01-T22).
- Strings the handoff lacks (load errors, upload refusals, stale Undo, flag-off, 409 stale draft,
  lint findings) are reserved keys that the building tasks write, inside the copy bans.

## Progress log
- 2026-10-24: contracts written from `sources/handoff/handoff/screens/{POR-03,POR-04,POR-14,
  POR-20,ADM-10}*/` (README, spec, screenshots) and R-01 §2–§5. POR-20 and ADM-10 drafted by a
  subagent from the same sources and reviewed. Checks: `pnpm -C apps/web exec vitest run
  src/routes/link-contract.test.ts` (19 passed, rule 5 included), `validate_docs`.
