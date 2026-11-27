# Quality and records rollout, Q4 2028 (Q-05-T30; DEC-6044)

Flags stay dark through the window. Q-04 executes each flip; every flip has its rollback.

| Flag | Canary (Q-04-T353) | Design partners (Q-04-T354) | Retirement (Q-04-T251) | Rollback |
|---|---|---|---|---|
| `quality.management` | Tue Nov 21, 7 pm CT | Nov 28 to Dec 7, before M21 | into `quality_management`, Thu Dec 14 bundle | flip off; AUD-28 and ADM-11 read "Not available"; no data is lost |
| `records.governance` | Tue Nov 21, 7 pm CT | Nov 28 to Dec 7 | into `assurance_completion`, Thu Dec 14 bundle | flip off; FIL-02 hides; scheduled destruction batches pause (RB-101 kill switch first) |

**Cycle-import help:** pilot firms evaluate on Dec 15, 2028. The import endpoint takes the firm's
prior monitoring cycle as a file (KNW import path); help text and a synthetic sample live with the
import screen, not in code.

**Hand-off notes:** I-03 (home tiles read the quality queues), K-05 (skills reference the
standards), W-03 (workbench agent reads AUD-30), X-01 (the destruction role's SCP), R-03 (portal
never shows quality records), N-03 (notifications for overdue monitoring items).

**Capacity ledger:** the support reserve rows (Q-04-T243, T244) log hours; this rollout adds the
canary watch (one evening) and the design-partner flips (two afternoons).
