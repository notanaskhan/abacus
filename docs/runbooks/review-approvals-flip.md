---
title: Review approvals flip (SHL-10 live approval of agent output, per pilot firm, Tue Jul 13, 2027)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-07-09
---
# Review approvals flip

| Field | Value |
|---|---|
| Owner | the founder on call flips; the other founder approves (Q-04-T004, P-29) |
| Task | P-04-T46 (P-04 §2: "SHL-10 … live Jul 13"; chapter 10 M10) |
| When | Tue Jul 13, 2027, in the 19:00 CT window, one pilot firm at a time |
| Rehearse | on staging with the J04 PBC journey before Fri Jul 9, 2027; `last_rehearsed` above is set then |
| Rollback | the flag off for the firm. Decisions persist: `review_decisions` is insert-only and every approve or reject already written stays, with its audit event |
| Related | `firm-rollback.md` (all of a firm's flags), RB-42 (scrubbing audit before shadow), `docs/plan/status/n01-t26-matcher-v3-clearance.md` (the matcher's own clearance) |

The flip lets a pilot firm's people approve or reject the agent's cited proposals in SHL-10 (Hannah
Leclerc's screening flag from AUD-03: approve and the request reads "Received"; reject with "Needs
client input" and it returns). The agent never approves, signs or decides (INV-1); this flag only
shows a person the proposal to decide on.

## 0. Before the window: blocker to clear

**The flag the plan names does not exist yet.** P-04 §2 lists `review.approve_agent_output` as a
rollout flag, but `docs/architecture/feature-flags/review.yaml` holds only `review.grammar_api` and
`review.checkpoints`, and SHL-10's routes (`review/contract.py`) answer behind `review.grammar_api`.
Flipping `review.grammar_api` for a firm would turn on every C3 surface, not only SHL-10. Before Jul 13
(DEC-1384): add `review.approve_agent_output` (boolean, default false, `owner`, an expiry after Oct 20
and outside Sep 1 – Oct 20), gate SHL-10's proposal approve and reject on it, regenerate, and replace
`review.grammar_api` in §3 below with it. Until then, this runbook cannot run as written.

## 1. Preconditions (each recorded in the ops request)

1. **The firm opted in** (TASK-076) and its agent stage for each specialist in scope is `live`:
   `make agent-stage FIRM=<id> AGENT=evidence.screener` reports `live`, set from a passing shadow
   report (§2).
2. **Bedrock full-suite reports pass** for the specialists in scope at their current prompt
   versions (P-04 §8 evals): screener needs_revision recall ≥ 0.97, ready precision ≥ 0.85,
   adversarial containment 1.0, citation verification 1.0, ECE ≤ 0.10; matcher top-1 1.0 and
   none-fit precision 1.0; upload reviewer at its committed thresholds. The report paths go in the
   request (`EVAL_REPORT`).
3. **Provider terms cover the route** (ADR-114): an entry in `docs/operations/provider-terms.yaml`.
4. **The firm's window is open** (`make windows`): the Tuesday 19:00 CT slot, not a freeze.

## 2. The evidence pack

- **Staging journey:** the J04 PBC journey's `pbc-ai` legs (`apps/web/e2e/journeys/J04-fs-audit.spec.ts`,
  P-04-T45) pass on staging against the live adapter; the run URL and SHA go in the request.
- **Shadow comparison:** `make shadow-report FIRM=<id> AGENT=evidence.screener` as of the request,
  passing SPEC-036 Q1 (50 runs over 14 days) and QD-10 (25 scored decisions, disagreement ≤ 8 %, no
  DE-1, DE-4 or DE-5 miss); its SHA-256 and `as_of` go in the request (`SHADOW_RUN`).
- **Both approvals:** the approving founder's name in `APPROVED_BY` (never the operator).

## 3. The flip (per firm, inside the window)

```bash
make flag FIRM=<firm-id> FLAG=review.grammar_api VALUE=true OPERATOR=<you> \
  REASON="P-04-T46 SHL-10 live approval" APPROVED_BY=<other founder> \
  ROLLBACK="flag off; decisions persist" REQUEST=<ops-request file> \
  EVAL_REPORT=<report paths> SHADOW_RUN=<sha256>@<as_of>
```

(`FLAG=review.approve_agent_output` once §0 is done.)

## 4. Verify (within 15 minutes)

1. As a staff member of the firm on a live screening flag: SHL-10 opens with the proposal, two
   verified citations and the policy note; Approve writes one `review_decisions` row by that person
   and the request reads "Received"; a return to client waits on its 10-second grant.
2. An agent token calling the approve route is refused (403); a client principal gets 404.
3. The audit log names the person for each decision ("‹person›", never the agent).

## 5. Roll back

`make flag FIRM=<firm-id> FLAG=<the flag> VALUE=false OPERATOR=<you> REASON="<why>" APPROVED_BY=<other founder> ROLLBACK="n/a" HOTFIX="<reason>"`
outside the window. SHL-10 stops offering proposals at once; decisions already made stay. Record a
DEC row with the reason.
