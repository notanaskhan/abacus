---
title: "Tax review workspace flip (M17): the individual return workspace and its agents, per pilot firm, Tue May 2, 2028"
owner: builder
alarms: [SLO-05, sse-delivery-p95]
last_rehearsed: never
rehearse_by: 2028-04-28
---
# Tax review workspace flip (M17)

| Field | Value |
|---|---|
| Owner | ayushkbhatia operates; notanaskhan approves. Both founders' approvals are on every request (P-29, DEC-809) |
| Task | T-04-T54 (TASK-7527; DEC-4527); T-04 §0, chapter 10 M17 |
| When | **Tue May 2, 2028**, in the 19:00 CT slot, after six weeks of shadow (from Mon Mar 20, 2028), one pilot firm at a time |
| Before it | the T-04 shadow programme on staging and the canary (T-04-T33); the CPA memo `tax-individual@v1` signed (T-04-T49); runtime v2 flipped first (`runtime-v2-flip.md`) |
| Rehearse | on staging before the slot with the synthetic firm PF-X1; set `last_rehearsed` then |
| Rollback | flags off, in reverse order; **data persists**; **CCH stays authoritative** |
| Related | `runtime-v2-flip.md`, RB-28 (real-time delivery), RB-01 (deploy), `firm-rollback.md` |

M17 gives a pilot firm the individual return workspace (TAX-04 review tree, TAX-05 worksheets,
TAX-06 issues, TAX-07 sign-offs, TXI-01 to TXI-03) and, for cleared capabilities with consents,
its agents (TAX-08 assistant, the drafter, the analyst modes, the fix runner). The engine of record
(CCH Axcess) computes and files the return (DEC-77); Accrued holds the review. The agent never
approves, signs or sends (INV-1).

## 0. The flags, in order
One flag per request (DEC-809), numbered by file
(`deploy/production/ops-requests/flip-2028-05-02-<code>-tax-1.yaml` to `-3.yaml`):

1. `tax.individual_workpapers`: TAX-05's worksheets and their fields. Off: 404.
2. `tax.review_workspace`: TAX-04, TAX-06, TAX-07 and the return frame's Review, Issues and
   Activity tabs (T-04-T55's tab registry). Off: 404 and the frame shows only Overview and Intake.
3. `tax_agents.enabled`: the tax capabilities, **only for capabilities cleared on a signed Bedrock
   report** (T-04-T43; `client_data` cleared) **and only with the taxpayers' §7216 consents**.
   Off: TAX-02's Run draft is absent and TAX-08 says why (DF-04). Leave it off for a firm whose
   cleared set is empty.

## 1. Renewal on the Tue Apr 25 train (registry-only)
All three entries expire **2027-05-07**. On the Tue Apr 25, 2028 train one registry-only PR
renews them to **Mon Jul 24, 2028** (outside every window), with no code change. Later renewals
ride T-05-T47, T-05-T73 and T-06-T03; T-06-T69 retires the two workspace flags and renews
`tax_agents.enabled`. Until the renewal merges, the flip plan is refused
(`flag_expires_before_slot`).

## 2. Preconditions (each recorded in the request)
1. The window is closed and the firm's Tuesday 19:00 CT slot is open (`make windows`).
2. The M17 checklist: every gate green or a dated exception — the CPA memo signed (T-04-T49), the
   tax suites at threshold with the §7216 refusal property at 1.0 (T-04-T18, T-04-T43), journeys
   J06 and the agents-off J06 green on staging within 24 hours (T-04-T51), parity and axe (T-04-T47,
   T-04-T48), mutation floor and p95 budgets (T-04-T53).
3. Six weeks of shadow on the firm's returns with no open SEV1/2 against the workspace.
4. The firm's consents: for `tax_agents.enabled`, every taxpayer the agents will read holds both
   §7216 consents for the year; otherwise the agents wait on inputs (by design) and the firm is
   told.

## 3. The flip (19:00 CT)
1. Merge the three requests in order; each is applied by the flag service, never by a deploy.
2. After each, check on the firm: the frame's tabs match the flags; a return opens TAX-04 with its
   counts; a person can approve a field and Undo it within 10 s.
3. Record the flip in Q-04's calendar with the rollback below.

## 4. Rollback
Turn the flags off in reverse order (3, 2, 1). **Data persists**: review decisions, field values,
checkpoints, issues and approvals stay in the database, insert-only, and reappear when the flags
return. **CCH stays authoritative**: nothing here changes what was exported or filed; the engine of
record keeps the return. A firm mid-review continues in CCH; the next flip resumes where it left.

## 5. Rehearsal record
| Date | Firm | Steps | Result |
|---|---|---|---|
| — | PF-X1 (synthetic) | — | not rehearsed: staging |
