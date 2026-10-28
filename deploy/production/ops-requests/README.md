# Production ops requests (Q-01-T34; platform-ops contract 3.5)

An operator command runs in production only by merging a PR that adds one file here, named `<yyyy-mm-dd>-<slug>.yaml`:

```yaml
command: abacus_tools.tenants status      # one allowlisted command (contract 3.5)
args: ["--tenant", "00000000-0000-4000-8000-000000000000"]
operator: builder                         # your handle, never an email address
reason: "R1 canary key check"             # at most 200 characters, no client data
```

Merging runs `ops-task.yml`, which validates the file (`python -m abacus_tools.release ops-request <file>`), takes the production deploy lock and runs the command once as an `abacus-ops` task on the current release image. A file is never edited after it merges: a new request is a new file. Requests and their arguments never carry client data, names of real people or secrets.

## Flip requests (Q-04-T010; P-29 rule 3)

A per-firm flag flip is a file named `flip-<yyyy-mm-dd>-<pilot code>.yaml` (the slot's date, the firm's code from `deploy/windows.yaml`), one flag per request (DEC-809):

```yaml
kind: flag_flip
tenant: 00000000-0000-4000-8000-0000000000a1     # PF-A1
slot: 2027-09-21T19:00:00-05:00
flags: [{name: sampling.sample_sets, value: "true"}]
journeys: [j04-fs-audit]                        # plus any the flag registry lists for the flag
shadow_run: https://...                         # the shadow comparison
rollback: docs/ops/flips/2027-09-21-PF-A1.md#rollback
operator: ayushkbhatia                          # the flag's owner
approved_by: notanaskhan                        # never the operator
# optional: eval_report (needed for a prompt.* variant), cpa_memo, hotfix: <reason>
```

The PR runs `flip-precheck` (`.github/workflows/ops-request.yml`): each journey must have passed on staging within 24 hours, the shadow run must be named, the approver must not be the operator, and the slot must be valid for the firm's window (the Tuesday 19:00–21:00 CT slot inside it; a Tuesday or Thursday outside it). Merging runs the flip as `abacus_tools.flags` through `ops-task.yml`; the flip guard checks the slot again at that moment, so merge inside the slot.

