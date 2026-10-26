---
id: TASK-1365
title: SHL-08 "Ask ‹client›…" and the SHL-14 prefill entry (P-03-T20 gap)
spec: SPEC-322
acceptance_criteria: [AC-28]
risk_zone: amber
status: blocked
epic: P-03
plan_key: P-03-T20
branch: s10c-audit
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Turn on SHL-08 d's "Ask Jonah & Claire Feld…" by giving SHL-14 a prefill entry, if the handoff
gives the prefilled request's words.

## Plan
Read the handoff (SHL-08 spec frame D, README links table; SHL-14 spec, revision, README) and
the screen contract `docs/screens/SHL-14.md`. Build the entry only with verbatim copy;
otherwise keep the control disabled and record why.

## Progress log
- 2026-10-27: read the handoff (SHL-08 spec frame D and README links table; SHL-14 spec,
  revision and README) and `docs/screens/SHL-14.md`. The link's words and destination exist;
  the prefilled request's words (title, category, client wording) do not, and SHL-14's
  Attachments row is always empty, so the locked file cannot be attached either. Per the brief,
  no copy is invented: no prefill entry, the control stays the disabled hint-only link of
  DEC-426. Recorded as DEC-460 with what would turn it on. No code change.
