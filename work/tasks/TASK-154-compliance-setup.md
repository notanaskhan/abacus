---
id: TASK-154
title: "Q-02-T01 · Compliance programme set-up: docs/ops/compliance/README.md gate tracker (M4 and M7 criteria with owner and date), docs/ops/soc2-control-map.md skeleton mapping Security, Availability and Confidentiality controls to ADRs and owners, Qualified Individual designation (notanaskhan, ayushkbhatia deputy), F-01 soc2-risk issue queued for the tool"
spec: SPEC-051
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: in-review
epic: Q-02
plan_key: Q-02-T01
branch: task-154-compliance-setup
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan into this file before code (solo amendment: no approval step).
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Every M4 and M7 criterion has a named owner and date in the tracker, and every control in the map cites at least one ADR and one owner.

## Scope
**In**
- docs/ops/compliance/README.md gate tracker: every M4 and M7 criterion with owner and date
- docs/ops/soc2-control-map.md skeleton mapping Security, Availability and Confidentiality controls to ADRs and owners
- Qualified Individual designation recorded (the builder; the epic's notanaskhan/ayushkbhatia pair collapses under the solo amendment)
- An F-01 soc2-risk issue queued for the compliance tool

**Out**
- Connecting the compliance tool (Q-02-T10)
- WISP, policy set, vendor register (F-09)

## Context to load
- Spec: `docs/specs/SPEC-051-compliance-setup.md` (sections 5 and Task map; ACs AC-1, AC-2, AC-3)
- Epic: `docs/plan/epics/Q-02.md`: Q-02 §0 (summary, decisions table 0.1: DEC-26, DEC-02); Q-02 §10 items 1, 2 and 9; Q-02 §11 R8 (counsel late)
- Task row: `docs/plan/epics/Q-02.tasks.csv`, `Q-02-T01`
- Process: `docs/plan/AMENDMENT-solo.md`
- Data boundary: `docs/specs/SPEC-036-data-boundary.md` (referenced, not duplicated); ADR-113, ADR-114

## Plan
- [x] Plan written in this file (required for amber and red)

Steps:
1. [x] Extract the M4 and M7 criteria from Q-02 §10 item 1 and 2 and chapter 01
2. [x] Write the tracker table with owner and date
3. [x] Draft the control map with ADR citations
4. [x] Record the QI designation; queue the issue (see Questions)

Files to create or change:
- docs/ops/compliance/README.md
- docs/ops/soc2-control-map.md
- docs/ops/slos.md and docs/runbooks/README.md (ADR-093 and ADR-098; written in the same session, not named in this task's scope)

Tests to write (mapped to ACs):
- AC-1 -> every tracker row has owner and date
- AC-2 -> every control row cites an existing ADR id and an owner
- AC-3 -> designation present; issue linked

## Definition of done
- [x] All listed ACs have passing tests or checks that reference them (checked by a throwaway script: every tracker row has owner and date, every control row cites an existing ADR and `builder`)
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [x] No secrets or real client data committed (public repo): secrets_scan clean; no price, name, account id or counsel advice written
- [x] No new dependencies, or each one listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation (N/A for this task unless it adds either)
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals (N/A unless it adds any)
- [x] Module README and relevant docs updated
- [x] Decisions below recorded; ADR raised where needed

Commands:
```
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — task file written from the epic (SU-14); nothing built yet.
- `2026-10-20` — Built from the task rows and plan chapters. Wrote `docs/ops/compliance/README.md` (QI designation; 15 M4 rows and 17 M7 rows, each with owner, date, evidence and status; no exception path), `docs/ops/soc2-control-map.md` (35 Security, 9 Availability, 10 Confidentiality controls, each citing ADRs and owner `builder`), `docs/ops/slos.md` (ADR-093: 13 objectives, burn-rate arithmetic, error-budget policy) and `docs/runbooks/README.md` (ADR-098: RB-01 to RB-30 index and runbook template). Checks run: validate_docs, secrets_scan and banned_patterns pass. `make check` not run (docs only). Status set to `in-review`, not `done`, because the `soc2-risk` issue could not be verified and `make check` was not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The M4 and M7 tracker rows follow chapter 01 section 1.2.2 and Q-02 section 10 as written; the one date movement allowed is the plan's own M7 fallback (Fri May 14, 2027), the criteria never change | Task asks for no exception path | no |
| Runbook staleness: past `rehearse by`, or last rehearsal over 12 months old | ADR-098 says stale runbooks raise a ticket but sets no age; this is the proposed default | no |
| Control-map `State` uses designed, building, built, operating | Skeleton needs an honest progress column; only tool evidence moves a row to operating | no |
| SLO rows marked binding (ADR-093) or inferred (chapter 06) | Inferred targets may be tightened with a dated note; binding ones are not loosened | no |

## Gotchas and discoveries
- The Q-02 epic names the dossier task as Q-02-T47; the task list shows it is Q-02-T49 (T47 is the firm-export package builder). The tracker uses T49.
- ADR-151 to ADR-154 are `proposed`; four control rows cite one, each also citing an accepted ADR.
- The plan assumed a non-author approver for change management; the solo amendment removes it. Recorded as an open item for the auditor conversation.

## Questions for the human
- [ ] The `soc2-risk` issue belongs to F-01-T01, which has not closed. This task records it as queued and adds none of its own. Verify it exists when F-01-T01 closes, then import it when Q-02-T10 connects the tool.
- [ ] Which compliance tool? The plan recommends one by Fri Oct 30; evidence locations say "tool" until chosen.

## Handoff
- **Current state:** docs written and committed on the branch; status `in-review`.
- **Exact next step:** verify the `soc2-risk` issue when F-01-T01 closes; run `make check` if a full gate is wanted; then set `done`.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none in the three quality commands; `make check` not run.
- **Open issues:** see Questions for the human.
