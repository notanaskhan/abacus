# S54 human and infrastructure steps (DEC-6002, DEC-6044)

| Row | Step a person takes | Where |
|---|---|---|
| C-02-T43 | W1 delta pen test (deferred, DEC-1389) | staging |
| Q-03-T376 / T377 | x100 load test and migration rehearsal | x100 staging (plan in `docs/ops/loadtests/2028-11.md`) |
| Q-03-T378 | live-stage accuracy samples | needs live data (none) |
| Q-04-T240 / T241 | 2029 cohort wave 2 onboarding | real firms (PF-X1 synthetic run possible, DEC-4100) |
| Q-04-T242 | quarterly runbook rehearsal Q4 2028 | staging; set `last_rehearsed` on each runbook |
| Q-04-T243 / T244 | support reserves (on-call, partner desk) | hours logged by the people on duty |
| Q-04-T353 | production-canary flag slot | human flip (rollout plan in `docs/ops/rollouts/quality-records-2028-q4.md`) |
| Q-05-T28 | j18 / j14 / j01 staging runs | staging, after the Thu batch |
| Q-05-T29 | RB-101 drill with certificate verification | staging, synthetic tenant |
| T-06-T55 | CPA review of the T-06 goldens | vendor |
| T-08-T28 / T29 | tax reviewer signs the eval labels; nightly real-model run | reviewer; `--route bedrock` after clearance |
