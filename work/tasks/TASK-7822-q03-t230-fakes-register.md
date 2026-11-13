---
id: TASK-7822
title: "Q-03-T230: the fakes register names the DocuSeal fake; sandbox verification stays open"
spec: SPEC-000  # row Q-03-T230
acceptance_criteria: [AC-1]  # no fake reported unverified at the quarter's end
risk_zone: green
status: in-review
branch: lo39-q03-t230
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39
created: 2026-11-13
updated: 2026-11-13
plan_key: Q-03-T230
---

## Objective
`python -m abacus_tools.quality.fakes` reports 5 of 5 fakes unverified. One entry was stale: it named
`signatures/contract.py` as a DocuSign fake; the envelope fake is `abacus_tools/fakes/esign.py`
(`FakeEsign`) and imitates DocuSeal since ADR-342.

## Plan
- `docs/quality/fakes.yaml`: the entry names `fakes/esign.py`, DocuSeal, and the envelope workflow
  suite that drives it.
- Open: verification against each real provider (NetSuite, WorkOS, an OIDC provider, Amazon SES,
  DocuSeal) needs their sandboxes and credentials, which only Ayush holds; the consumer suites run in
  the lo39 end pass.

## Progress log
- 2026-11-13: register fixed; the check names the right file.

## Decisions made during this task
None.
