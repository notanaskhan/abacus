---
id: TASK-139
title: "F-09-T14 · Discovery thresholds W1-W3 (and the build-plan section 4.1 blanks) in docs/product/discovery/thresholds.md before the first call; interview guide covering ledger, tax engine, e-signature, mailbox, Google or M365, PHI exposure, SQMS needs and pricing; anonymisation rules"
spec: SPEC-049
acceptance_criteria: [AC-25, AC-27]
risk_zone: green
status: in-review
epic: F-09
plan_key: F-09-T14
branch: task-139-discovery-thresholds
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan below into this file first, then build.
> - If scope must change, add it to *Questions for the human* and carry on with the plan's proposed option.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
thresholds.md merges before the first call and the guide covers the inputs to DEC-25, DEC-49, DEC-70, DEC-75 and proposed DEC-100.

## Scope
**In**
- Write `docs/product/discovery/thresholds.md` with W1-W3 (and fill the build-plan §4.1 blanks to point at it) before the first call
- Write the interview guide covering ledger, tax engine, e-signature, mailbox, Google or M365, PHI exposure, SQMS needs and pricing
- Write the anonymisation rules (firm codes only; no client data, DEC-05)

**Out**
- W4-W8 thresholds (merge before Mon Jan 11, 2027)
- Holding the interviews (wave 1)
- Loosening any threshold later

## Context to load
- Spec: `docs/specs/SPEC-049-vendor-legal-assurance-programme.md` (sections: 5 AC-25, AC-27; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/F-09.md` §0 (lines 11-29), §3 (127-244), §9 (401-674), §10 (675-696), §11 (697-723); read in full: §3.6 F1 (thresholds first), F2 (named targets and conversations); §9 row F-09-T14; §10 M1 bullet
- Row: `docs/plan/epics/F-09.tasks.csv`, plan key F-09-T14
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- Chapter 11 §11.6.1: thresholds are written down before the evidence arrives
- `docs/product/build-plan.md` §4.1 (three blanks) and `docs/product/discovery/` as they stand when you start

## Plan
- [x] Plan written into this file before any build step (zone is green; plan is the steps below)

Steps:
1. [x] Draft W1-W3 from chapter 11 §11.6.1 with exact numbers from the plan
2. [~] thresholds.md written before any call; build-plan §4.1 does not exist, so the pointer line is not placed (see Questions)
3. [x] Write the guide so it yields the inputs to DEC-25, DEC-49, DEC-70, DEC-75 and proposed DEC-100
4. [x] Write the anonymisation rules into the guide

Files to create or change:
- docs/product/discovery/thresholds.md (new)
- docs/product/discovery/interview-guide.md (new)
- docs/product/build-plan.md (§4.1 blanks point to thresholds.md)

Tests to write (mapped to ACs):
- AC-25 → doc check: thresholds.md merged before the first call; guide covers the listed topics and the five decisions
- AC-27 → doc check: the guide states firm-code-only notes and no client data

## Definition of done
- [~] Every listed AC is met and has evidence: AC-27 met; AC-25 met except the build-plan pointer (§4.1 does not exist) (tracker row, vault record or decision-log entry), referenced by its AC id
- [x] `cd backend && uv run python -m abacus_tools.quality.validate_docs` passes
- [x] No price, contract text, partner firm name, counsel advice or secret is in git (the repo is public until F-01-T01)
- [x] No code changed; no new dependencies
- [x] Decisions below recorded in `docs/product/decision-log.md` where they bind later work (DEC-119, DEC-120)

Commands:
```
cd backend && uv run python -m abacus_tools.quality.validate_docs
```

## New dependencies
| Package | Version | Why | Decision |
|---|---|---|---|
| none | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — Task file written at kickoff (SU-14). No work started.
- `2026-10-20` — Wrote `docs/product/discovery/thresholds.md` (W1, W2a/b, W3a/b with green, amber and red values from chapter 11 section 11.6.2; counting rules; the three build-plan blanks mapped; W4 to W8 listed as due before Mon Jan 11, 2027; reading and amendment logs; tighten-only rule) and `docs/product/discovery/interview-guide.md` (anonymisation rules first; blocks for ledger, tax engine, e-signature, mailbox, Google or M365, PHI exposure, SQMS needs and pricing, each mapped to DEC-70, DEC-49, DEC-25, DEC-75 and proposed DEC-100; note template). validate_docs, secrets_scan and banned_patterns pass. `docs/product/build-plan.md` was not edited (no section 4.1). Appended DEC-119 and DEC-120 to `docs/product/decision-log.md`. Status `in-review`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Counting rules (qualified conversation, willing, accept, retrievable) written into thresholds.md as part of the thresholds | The plan gives numbers but not the counting rule; written before any call so they cannot drift | no |
| W2 and W3 each split into a discovery part (a) and a later pilot part (b), all numbers fixed now | Plan table has both stages in one row; fixing both now keeps them from being loosened later | no (logged in DEC-119) |
| Controllers' willingness to grant ledger access has no separate pass mark; it is tallied beside W3a and tested by W3b | Plan gives no discovery number for it; inventing one would be a threshold the plan did not set | no |
| While the repo is public, only the structured tally block of each interview note is committed; narrative stays in the vault | The repo is public until F-01-T01; F-09 section 4.6 allows firm-code notes only once private | no |

## Gotchas and discoveries
- Depends on F-09-T01.
- Thresholds may be tightened later, never loosened.
- Other sessions edit `docs/product/` at setup time; start this task after they have finished.
- `docs/product/build-plan.md` has no section 4.1: its phase sections 3 to 6 were replaced by the Accrued plan, and only the shadow-threshold blank (line 81) remains.
- `docs/product/discovery/` did not exist; it was created here. The counting-rules, split and controller decisions above are DEC-119, and the public-repo note policy is DEC-120, in `docs/product/decision-log.md`.

## Questions for the human
- [ ] Where should the pointer to thresholds.md go, given build-plan section 4.1 is gone? Proposed option: one line under section 1 (Principles) or section 7's shadow-threshold blank for W2b. Not applied: it is outside the files this session was asked to write.

## Handoff
- **Current state:** thresholds and guide written and committed on the branch; status `in-review`.
- **Exact next step:** place the build-plan pointer (see Questions), then set `done`. Before the first call, confirm the thresholds file has merged.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** see Questions for the human.
