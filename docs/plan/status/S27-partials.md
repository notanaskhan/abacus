# S27 code partials (2026-11-06)

The partials left in S27's built rows, built on main 37856f6c7. Ayush chose to land these without CI ("let's skip CI and continue with the rest of the merge order as planned"), so no CI run has read this code.

| PR | Row | Now live | Decision |
|---|---|---|---|
| #1296 | T-03-T07 | A state line's form and dates come from published `due_date_rules` | DEC-2357 |
| #1297 | T-03-T07 | "{year} estimated payments" binder part, sealed list cursors, confirmed-on and contact | DEC-2358 |
| #1298 | N-04-T11 | `NoticeAnalysisWorkflow`; attached 1099s searched for citations | DEC-2359 |
| #1299 | A-06 | SUM effect writers, PATCH effect, conclusion and sign-off strips, column totals | DEC-2360 |
| #1300 | A-05-T31, T32 | Rollovers and the FS tie, actual match, the participant's year rate; migration 0673 | DEC-2361 |
| #1301 | A-05-T31, A-04-T32, N-04-T14 | EBP-04 keys and totals row, AUD-09 concluder, NOT-02 polling | DEC-2362 |

## Still open
- **Blocked by a later row:** `proposed-entries:send-preview` (R-02-T03, sprint 29); NOT-02 e and f live swaps (N-04-T22, sprint 29); HOME-02's approval row (T-03 cut-list item 3, T-08 / I-01); state holiday calendars (T-08).
- **Needs a stored figure or field first:** the W-3 tie; `LateRemittanceOut`'s deposit-by date, §6621 rate line and SCC date; NOT-02's issued dates and corrected mark; BND-03's request-status helper; Fix in Knowledge (`AgentRunOut` has no program id).
- **Withdrawn:** "SUM rows by account": the handoff's statement is one row per misstatement.

## Checked
- `make check-fast` passes on the stack.
- Targeted unit, contract and security suites pass after fixes (4,450 in the last pass, 8,179 before it).
- Integration against Postgres: extensions and estimates, notice analysis, SUM, EBP-04 and schema.

## Not checked
- No CI run has read this code, and the full unit, contract and security suites did not finish on it: a run stopped at 99% had about 9 failures, names not captured. The last targeted pass covers the modules this stack touches.
- The other integration shards, the Temporal run of `NoticeAnalysisWorkflow` (its step is called directly; the sandbox test loads it), a citation against a real word layer as the system actor, web journeys, staging.
