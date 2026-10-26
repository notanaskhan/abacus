# Parser fuzzing (Q-03-T030)

Every parser that reads a client file is fuzzed nightly with Hypothesis
(`backend/tests/property/fuzz/test_parsers.py`): the trial-balance and general-ledger importers
for the five ledger formats (QuickBooks Online, Xero, QuickBooks Desktop, NetSuite, Intacct), the
XLSX request-list importer, and PDF extraction both in-process and in its isolated child
(ADR-110). Client content is hostile (ADR-052); the property is that each parser either returns or
raises its declared error (`NormaliseError`, `RequestListInvalid`; extraction never raises and its
child never dies).

## Runs

| Where | Profile | Budget |
|---|---|---|
| `make test` and CI | `ci` (default): 40 examples a target, derandomised | seconds |
| `.github/workflows/fuzz-nightly.yml` | `nightly` (`ABACUS_FUZZ_PROFILE=nightly`): 20,000 examples a target, 2,000 for the isolated child | 15 minutes |

Spending the budget is a clean night. The job summary records each night; the acceptance is 14
nights before M6.

## A crash

The repository is public, so the nightly job publishes no crashing input and names no target:
pytest's output stays on the runner, nothing is uploaded, and the issue and the job summary carry
only the number of crashing targets, the commit and the night's seed.

1. The nightly job fails and opens a **SEV3** issue with the count, the commit and the seed.
2. Reproduce locally at that commit:
   `cd backend && ABACUS_FUZZ_PROFILE=nightly uv run pytest tests/property/fuzz --hypothesis-seed=<seed>`.
   Hypothesis prints the minimised falsifying example and a `@reproduce_failure` blob.
3. Fix the parser and commit the minimised input as
   `backend/tests/property/fuzz/regressions/<target>/<short-name>.bin` (target names are the keys
   of `TARGETS`, such as `tb.qbo_tb_csv` or `evidence.pdf`) in the same PR; `test_regressions`
   replays every committed case on every run. A crash usable against a live parser is fixed in the
   security lane before its case is public (docs/ops/pentests/README.md).
4. Close the issue with the PR.

Inputs are generated, never client data (ADR-085): never commit a real client file as a case.
