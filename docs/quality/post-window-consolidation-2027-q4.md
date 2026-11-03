# Post-window consolidation, 2027 Q4 (Q-03-T167, Q-03-T168)

The autumn window closed Oct 20, 2027 (plan calendar). Solo edition: nothing was dark-merged
behind a window this sprint; the deferrals below are the S26 rows' recorded partials (their task
files), each closed or re-dated here by the plan's Fri Oct 29 deadline. "S27" is the next sprint;
"live" waits on a real firm (DEC-1391) or a staging deploy; "human" needs a person outside the
build (a signature, counsel, a vendor).

## Back end and data (Q-03-T167)

| Deferral | Row | Re-dated |
|---|---|---|
| EBP-03 sample service behind `GET …/ebp/eligibility/sample` (501 today) | A-05-T23 | S27 |
| Notices workflows and matching (N-04 workflow tasks beyond intake) | N-04-T06, T07 | S27 (N-04-T11 onward) |
| SUM snapshot writing on conclusion | A-06-T13, T15 | S27 |
| The section drafter's re-draft consumer for `ic` | A-04-T29 | S27 |
| `work_items.due_on` kept in step with a notice's respond-by | N-04-T06 | S27 |
| `decision_pending` / `position_mismatch` raised by the sign-off (asserted in the contract doc only) | N-04-T10 | S27 (N-04-T12, T16) |
| C4 v1.1 consumers reading the OCR routes | P-11-T20 | S27 (with the consumers) |
| Runtime sink scan for SSN/DOB patterns (logs, audit rows, outbox, model context) | A-05-T29 | live (RB-42 seeded audit on staging) |
| Planning agent-run events, RA sign-off, bridge letter, reliance; Granite Peak's card | A-04-T28 | S27; Granite Peak stays blocked on DEC-1969 |
| The review slice cannot load past Apr 13 (Feld checkpoint before the tax board's returns) | P-04-T36 | S27 (found by A-04-T28) |
| Mutation-survivor tests for the S26 amber rows | Q-03-T171 | the mutation lane's next run |
| Trivy, CodeQL, Inspector; uv.lock and base-image bumps | Q-03-T170 | when CI runs again |
| Runbook rehearsals (review grammar, audit planning flip) | P-04-T61, A-04-T40 | live (next staging deploy) |
| CPA memo for `materiality@1`, real-firm flips | A-04-T40 | human, then live |

## Front end (Q-03-T168)

| Deferral | Row | Re-dated |
|---|---|---|
| AUD-15: assignee, concluder and disposition need a findings-contract addition; screen contract doc; gallery registration; "Add to AU-C 265 letter" until AUD-22 | A-06-T18 | S27 (contract first) |
| AUD-08 (e) driven from the host prop; Edit's host editor for a drafted rationale | A-04-T26 | S27 |
| AUD-04: outlined agent tick variant in the C-02 kit; export actions; two withheld citation quotes | A-04-T27 | S27 (kit); quotes when the sources are loaded |
| EBP-03: provision cards; Raise exception… and opt-out request wiring | A-05-T23 | S27 |
| NOT-01: duplicate, manual-entry and no-client states; Draft Form 2848… to SIG-02; assignee picker | N-04-T09 | S27 |
| N-04-T10's TypeScript fixture assertions and Whitley figures | N-04-T10 | S27 (with NOT-02) |
| HOME-02: Margaret's materiality decision opens selected on staging | I-01-T21 | live |

Every deferral of the window is now dated: closed in S26, re-dated to S27, or waiting on a named
live or human step.
