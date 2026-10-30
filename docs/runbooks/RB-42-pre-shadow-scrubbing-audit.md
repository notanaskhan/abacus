---
id: RB-42
title: Pre-shadow scrubbing audit (seeded cases through every sink, read back)
owner: builder
owning_epic: Q-03
alarms: []
last_rehearsed: never
rehearse_by: 2027-05-28
---
# RB-42 · Pre-shadow scrubbing audit

| Field | Value |
|---|---|
| Owner | the founder on call |
| Task | Q-03-T083 (SPEC-341 AC-49; ADR-031, ADR-167) |
| When | before the first firm enters shadow (M9, Tue Jun 1, 2027), then after any change to the logger, `error_tracking.scrub`, the metric views or the log driver |
| Where | staging, then the production canary, each as its own environment's ops task |
| Tool | `python -m abacus_tools.scrub_audit` (`seed`, `sample`, `check`) |
| Fails closed | a sink that never shows the run marker makes the run **inconclusive** (exit 2), never clean |

## What the audit proves
The offline suite (`tests/security/test_classification_scrubbing.py`, AC-19 to AC-22) proves the
scrubbers on in-process stand-ins. This audit proves the same seeded cases, sent through the real
logger, Sentry client and metric exporter of a deployed task, arrive in CloudWatch Logs, Sentry and
the metric store **masked**: no seeded SSN, EIN, ITIN, bank account, date of birth or IP PIN as
written (or as bare digits), and no valid TIN form of any origin, in any sampled event.

## 1. Before the run
1. The Sentry read token: an internal-integration token with `event:read` on the project, stored
   as the ops task's `ABACUS_SENTRY_AUDIT_TOKEN` secret (Secrets Manager; never an argument, a
   log line or a workflow input). Without it the Sentry sink is skipped and the run is
   inconclusive.
2. Know the metric namespace the OTLP collector writes to (`--metrics-namespace`), and any metric
   log group outside `/abacus/<env>/` (`--log-group`, e.g. an EMF group).
3. The ops task's role reads `/abacus/<env>/*` log groups and lists metrics (staging:
   `infra/envs/staging/compute.tf`; production gets the same statements with its compute stack).

## 2. Seed
`ops-task.yml`, command `abacus_tools.scrub_audit seed`, args `["--env", "staging"]`, reason
"Q-03-T083 scrubbing audit". The task prints `{"run": "sa-xxxxxxxx"}`: that is the run marker.
It refuses in any environment other than the one it names.

## 3. Read back (wait 10 minutes for the log driver, Sentry ingestion and one metric export)
Command `abacus_tools.scrub_audit sample`, args
`["--env", "staging", "--run", "sa-xxxxxxxx", "--since-minutes", "30", "--sentry-org", "<org>",
"--sentry-project", "<project>", "--metrics-namespace", "<namespace>"]`.
The task prints the report: sinks sampled, whether each received the marker, and findings (the
location and the masked form only).

## 4. Read the verdict
- **clean** (exit 0): record it (§5).
- **inconclusive** (exit 2): a sink never received the seed. Fix the reason (token, namespace,
  ingestion delay, a sink that is off) and repeat from §2 with a new run. Never record an
  inconclusive run as clean.
- **leak** (exit 1): SEV2 under the security-incident flow (RB-08's classification for a
  Restricted value that left the process). For each finding:
  1. Reproduce it offline: add a test to `tests/security/test_classification_scrubbing.py` that
     puts the same form through the same path and fails on today's code (the acceptance: every
     miss becomes a test there).
  2. Fix the scrubber in the same PR; the test passes.
  3. Purge the sink copy (CloudWatch: delete the stream's events by retention or `delete-log-stream`
     on a stream holding only the seed; Sentry: delete the event) and record what was purged.
  4. Re-run from §2 after the fix is deployed.

## 5. Record
Commit `docs/ops/scrub-audits/<YYYY-MM-DD>-<env>.json` (the report as printed; it holds no
values) and add a row to `docs/ops/scrub-audits/README.md` with the run marker, the verdict and
any tests added. Set this runbook's `last_rehearsed` to the date of the first clean staging run.
