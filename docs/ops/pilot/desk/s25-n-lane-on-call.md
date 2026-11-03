# S25 support reserve, N lane: on-call and incident response (Q-04-T089), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081). The sprint is S25 of the plan (Oct 4-15, 2027, in the autumn window); no
pilot firm is live (DEC-1391) and no production stack exists.

Acceptance: "Every page in the sprint was acknowledged within 15 minutes and every SEV1/2 has a
postmortem within 5 business days."

## Pages and incidents

| Week | Pages | Acknowledged within 15 minutes | SEV1 | SEV2 | Postmortems due |
|---|---|---|---|---|---|
| Oct 4-10, 2027 | 0 | - | 0 | 0 | 0 |
| Oct 11-15, 2027 (deadline week, double cover) | 0 | - | 0 | 0 | 0 |

No page fired: nothing is live to page about, and the paging integration has no production signal
to read. No SEV1 or SEV2 was opened, so no postmortem is due. There is no incident record in the
repository or in ADM-06's register (RB-27), which only a live environment holds.

## The rota
`docs/ops/on-call.md` names N primary and AY backup for every day of the sprint, double cover on
Oct 11-15; `python -m abacus_tools.quality.on_call` passes. The rota's test page (Q-04-T066: primary
to backup within 15 minutes) needs the paging integration and has not run.

## Hours
`docs/ops/pilot/support-hours.csv` gains S25's N rows: 0 hours, no SEVs, in both weeks.

## What only a live firm can show
A real page and its acknowledgement time; the test page's escalation; a SEV1/2 and its blameless
postmortem within 5 business days (ADR-097).
