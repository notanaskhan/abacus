# S27: blocked rows and solo rituals (DEC-2259)

Recorded at the S27 build (2026-11-04, on main 9d5bbd6a3 plus the S27 stack #1176 onward). These
rows are not built in S27. Each names what holds it; none is marked done, and no gate they guard is
treated as met (DEC-1389, DEC-1391, DEC-2227).

## Blocked (14)
| Row | What holds it |
|---|---|
| F-09-T197 to F-09-T203 | Vendor contracts, real firms, partner agreements and hires: human and vendor actions (DEC-2227) |
| Q-03-T174 | Pen test #2 itself: deferred in full under DEC-1389 (`docs/plan/status/pen-test-deferral.md`) |
| Q-03-T176, Q-03-T177 | Need Q-03-T160's quotas (not built), Q-03-T161 (partial) and the staging ×100 load profile |
| Q-03-T178 | Needs Q-03-T137 (never built) and live Bedrock in staging |
| Q-03-T179, Q-03-T180 | Need Q-03-T147, which waits on Q-03-T072 |
| Q-04-T096 | A vendor action |

## Solo rituals (2)
| Row | How it stands for one builder with no live firms |
|---|---|
| Q-04-T098 | N-lane support reserve: no on-call rota, no live firms and no SEV1/2 to run; live-path defects go through the next batch; runbook upkeep happens with the rows that change a runbook |
| Q-04-T099 | AY-lane support reserve: no partner desk, office hours or pilot firms (DEC-1391); the monthly flag-hygiene report runs on the synthetic test firm PF-X1 with Q-04-T097 |

## Recorded from the end pass
Q-03-T182, Q-03-T183, Q-03-T184, Q-03-T185, Q-03-T186, I-01-T22 and Q-04-T097 are review and
proof rows whose evidence is the S27 end pass (targeted suites, contract and generated-test sweeps,
parity, axe, the PF-X1 flips). Their results land with the end pass, reported as synthetic where a
firm is involved (DEC-1530).
