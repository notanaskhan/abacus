# 2029 cohort onboarding plan (Q-04-T232), on PF-X1

**No contracted firms (DEC-1391).** The plan's 8–12 firms do not exist in this build, so the waves
below are the plan's calendar with no firm in them; the rehearsal firm is the synthetic PF-X1
(Brightwater Hale, DEC-1530), reported as synthetic (DEC-2081). Firm names never enter git: a
firm is a cohort code `PC29-NN` (`deploy/windows.yaml` rules), mapped in the vault.

Acceptance: "Every contracted firm has a wave and load dates, and the plan names which firms move
to May 2029 if the reserve runs out." Met for zero contracted firms; each firm signed later is
added to a wave here with its dates before its provisioning row (Q-04-T236).

## Waves (the plan's dates)

| Wave | Provisioning (PLT-01 c, g; dossiers LEVEL=shadow) | Data loads | Firms |
|---|---|---|---|
| 1 | Mon Oct 30 – Fri Nov 10, 2028 (Q-04-T236) | by Fri Nov 17 | none contracted; PF-X1 rehearses the path |
| 2 | Mon Nov 13 – Fri Nov 24, 2028 | by Fri Dec 1 | none contracted |
| 3 | Mon Nov 27 – Mon Dec 18, 2028 | by Mon Dec 18 | none contracted |

**Nothing between Jan 15 and Apr 15, 2029.** No firm is provisioned, flipped or loaded inside the
season window (`season-2029` in `deploy/windows.yaml`, Jan 1 – Apr 20, with its deadline weeks).
A wave that slips past Dec 18 moves whole to May 2029; it never lands in the season.

## RK-07 pause rule

When the support reserve runs over for two sprints in a row (`docs/ops/pilot/support-hours.csv`
against the reserve rows; read by `abacus_tools.m12_pack`), onboarding of the next wave pauses:
the latest-signed firms of the open wave move to May 2029 first, in reverse signing order, and the
next cut tier is invoked instead of borrowing from the hardening reserve (Q-04 §1.8.4, chapter 11
RK-07). Firms that move: **none named** (no firm is contracted); the order rule above names them
the day a wave holds any.

## Per-firm checklist (for when a firm is signed)
Cohort code and wave · `real_data_since` in `windows.yaml` · dossier at shadow (`make go-live-check`)
· enrolments and baselines (`make pilot-enrol`) · named desk owner (AY) and on-call (N) · the
firm's entitlements and flags in the next bundle · first pilot-metrics read in its second week.
