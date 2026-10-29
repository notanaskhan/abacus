# Pilot 0 usability log: the top ten (PW0)

F-09 §3.7 G3 and Q-03-T084. Every Pilot 0 finding is filed within two business days as an issue
from the **Pilot 0 usability finding** form (`.github/ISSUE_TEMPLATE/pilot-usability.yml`): screen
ID, state letter, severity, owning epic. The ten that matter most are the rows below; the list goes
to the screen owners (P-07, P-08, R-01, A-01, K-01) and is fixed or re-filed before the PW0 exit.

**Rules** (checked by `python -m abacus_tools.quality.pilot_log`; `--exit` at the exit review):
- **Pilot codes only** (PF-A1…A3, PF-T1, PF-C1). Firm names, people's names and client data never
  enter git or an issue: the code-to-name map is in the founders' vault (docs/ops/pilot/README.md).
- **Defects only are fixed here** (Q-03-T084): a `defect` row is `closed` with its fix PR, or
  `re-filed` to an epic with a reason. A `capability` (new behaviour, a new state, a new screen) is
  never built under this row: it is `re-filed` to the owning epic's cut list, naming that issue.
- A fix PR adds the screen-state or journey test that would have caught it (Q-03-T105's rule).
- **Exit:** before Tue Jun 1, 2027 (M9) all ten rows are `closed` or `re-filed`.

| # | Issue | Pilot | Screen | State | Severity | Owning epic | Kind | Status | Resolution |
|---|---|---|---|---|---|---|---|---|---|

_No Pilot 0 session has run yet (the window opens Mon Jan 11, 2027): the table is empty until F-09
files the first findings. Recorded 2026-10-30._
