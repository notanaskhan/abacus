---
id: TASK-2148
title: ADR-342 DocuSeal replaces DocuSign as the e-signature provider; N-02 and F-09 rows re-scoped
spec: SPEC-381
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: N-02
plan_key: P-26
branch: adr-docuseal
created: 2026-10-30
updated: 2026-10-30
---

## Objective

The builder decided on 2026-10-30 that DocuSign is too expensive and that a self-built ceremony is
too slow; DocuSeal's hosted API is the replacement. AC-1: ADR-342 is drafted and accepted (superseding
ADR-149), DEC-1275 records the decision, and every N-02 and F-09 row that names DocuSign is
re-scoped to DocuSeal in `backlog.csv` and the epic task files, with an amendment note on both epic
specs and the M8 gate's c2 and c3 rows.

## Plan

- `docs/adr/ADR-342-e-signature-provider-docuseal.md` (accepted 2026-10-30); `docs/adr/README.md` and
  `docs/adr/backlog.md` index rows.
- `docs/product/decision-log.md`: DEC-1275.
- `docs/plan/backlog.csv`, `docs/plan/epics/N-02.tasks.csv`, `docs/plan/epics/F-09.tasks.csv`: the
  rows listed in ADR-342's follow-ups, rewritten (title and acceptance); ids, sprints, sizes and
  dependencies unchanged.
- `docs/plan/epics/N-02.md`, `docs/plan/epics/F-09.md`: amendment note under the title.
- `docs/ops/gates/M8-tax-go-no-go.md`: criterion (c), c2 and c3 name DocuSeal KBA.
- No code. The adapter rework is N-02-T18's re-scoped row; the status poll is N-02-T19's.
- No amounts anywhere in git (vault only).
- Rollback: revert the PR; ADR-149 stays accepted and untouched.

## Human to-dos

- Open a DocuSeal account (sandbox now; Pro when the adapter is ready) and store the API key in the
  vault, never in git.
- Ask DocuSeal support in writing for the KBA method: question source, pass threshold, attempts and
  lockout, SSN and ITIN handling, the failure events the API reports, and whether webhooks can carry
  a verifiable secret. Ask also for its security report (SOC 2 or equivalent) and US hosting.
- Counsel: Pub 1345 view on DocuSeal KBA (F-09-T92); ESIGN/ERSD text unchanged.

## Progress log

- 2026-10-30: drafted from DocuSeal's public docs (API, signing API, embedded form, form webhook,
  pricing, KBA pages). Rows re-scoped by `tools` script in the session scratchpad; CSV bytes
  otherwise unchanged (CRLF round-trip checked).
- 2026-10-30: ayushkbhatia accepted ADR-342; ADR-149 marked `superseded by ADR-342`; DEC-25 and DEC-1275
  rows, the ADR index and backlog, and both epic amendment notes updated.
