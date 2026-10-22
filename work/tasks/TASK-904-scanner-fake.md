---
id: TASK-904
title: Scanner fake - verdict injection and the pending state (F-04-T18)
spec: SPEC-307
acceptance_criteria: [AC-6]
risk_zone: red
status: done
epic: F-04
plan_key: F-04-T18
branch: f04-t18-scanner-fake
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Scenario artefacts yield infected, error, timeout or pending verdicts; EICAR and zip-bomb checks unchanged" (F-04.25).

## What changed
- **`kernel.scanning`:**
  - `inject_verdict(sha256, verdict, delay_seconds=)` and `inject_marked(sha256, mark)` read a scenario artefact's `scan:` mark: `infected`, `error`, `timeout` or `pending(2s)`;
  - `forget_injected()` clears them.
- **`LocalScanner` answers:**
  - `infected` gives `malware`;
  - `error` and `timeout` give `unscannable`, as `ClamdScanner` answers both;
  - `pending` waits up to 10 s (the scanning state) and then comes back clean. Scans already run off the event loop.
- **Guards:**
  - EICAR and archive bombs are still checked first, so no injection can clear them;
  - injection is refused outside the synthetic environments (local, test, evaluation), so never in staging or production, which run ClamAV.
- **Loader:** the scenario loader calls `inject_marked` for marked artefacts when the E0 slice (F-04-T20) uploads them.

## Progress log
- 2026-10-23: `tests/unit/kernel/test_scanner_fake.py` and the existing scanning tests pass.
