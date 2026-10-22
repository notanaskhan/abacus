---
id: TASK-423
title: Screen contracts for POR-01 and POR-02 (P-08-T03)
spec: SPEC-307
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: P-08
plan_key: P-08-T03
branch: TASK-423-p08-screen-contracts
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Both contracts list every artboard with persona, clock and tier, and the link-contract test knows
every outbound target of POR-01 and POR-02." Write the two P-08 screen contracts from the handoff
(revision wins): POR-01 a–g plus the DF-17 two-step setup state c′ and the DF-03 390 layout;
POR-02 a–h and M (g and h from revision R2). Each artboard has a persona, a clock and a data
condition (SPEC-307 AC-8), a parity tier, copy keys verbatim, outbound links with their
planned/fixture/live status, the AVOID lists as tests, and Deviations for DEC-35, DEC-58(d),
DEC-59, DF-17, DF-24 and DF-03.

## What changed
- **Contracts** `docs/screens/POR-01.md` and `docs/screens/POR-02.md` on `_TEMPLATE.md`, modelled on
  `BND-01.md`. Artboards: POR-01 a–g (7) + c′ + 390; POR-02 a–h + M (9). Each names its building
  task (T09, T15, T19, T23), the API rows and matrix actions from P-08 §4.3, the status objects in
  their `client_label` wording, copy keys for `screens/<ID>/copy.ts` (strings verbatim from spec.md,
  revision.md and the built artboards; per-artboard row text stays seed data for P-08-T08), links,
  acceptance (spec + R2 + the P-08 stories that bind the screen), figures that must foot, AVOID
  lists, deviations, parity and open gaps.
- **White label.** Both contracts state AGENTS frontend rule 7 (DEC-01, ADR-133, DEC-59): portal
  code never renders "Accrued" (copy, title, favicon, alt and aria text, bundle strings), and list the
  portal copy bans (Accrued, password, task, agent names, firm status words).
- **Links.** POR-01: POR-02, POR-13, POR-14, POR-15, POR-18, POR-23 (role-routed landings, P-08
  Story 2.3). POR-02: POR-03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 16, 21 and POR-01 (sign-out). All
  were already manifest IDs in `routes/manifest/por.ts`, so `seed-manifest.mjs` had nothing to add
  and no manifest entry was edited.

## Decisions taken in the session
- POR-02 b renders at Mon Feb 2, 2026 (its header reads "Monday, February 2"); README's Sep 14
  label is canvas metadata (revision > spec > README, DEC-04/DEC-15; P-08 §2.1). g at Thu Oct 22,
  2026, 8:30 AM CT; POR-01 d at Wed Sep 2, 2026.
- Copy for states with no handoff string (code expired, resend too soon, sign-in paused, unknown
  host, c′, no active grant) is not invented here: the keys are reserved and the building tasks
  (T09, T15, T19) write the strings on the C-20 grammar and record them back, inside the copy bans.
- POR-02 b strings that exist only in the built frame (to-do lines, "Due Apr 15, 2026", "We're
  getting started", "0 of 21 requests done") are taken from the screenshot: the built screen
  reflects later decisions (README).
- DEC-35's "5 attempts" cap is read as never binding; 3 wrong codes per email lock (P-08 OQ-3, the
  plan's option).

## Progress log
- 2026-10-23: contracts written from `sources/handoff/handoff/screens/POR-0{1,2}*/` (README, spec,
  POR-02 revision.md, screenshots a–h) and P-08 §2.1, §4.3, §5.1–5.7. Checks:
  `pnpm -C apps/web exec vitest run src/routes/link-contract.test.ts` (19 passed, rule 5 included),
  `validate_docs`, `banned_patterns`.
