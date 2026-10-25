# Production ops requests (Q-01-T34; platform-ops contract 3.5)

An operator command runs in production only by merging a PR that adds one file here, named `<yyyy-mm-dd>-<slug>.yaml`:

```yaml
command: abacus_tools.tenants status      # one allowlisted command (contract 3.5)
args: ["--tenant", "00000000-0000-4000-8000-000000000000"]
operator: builder                         # your handle, never an email address
reason: "R1 canary key check"             # at most 200 characters, no client data
```

Merging runs `ops-task.yml`, which validates the file (`python -m abacus_tools.release ops-request <file>`), takes the production deploy lock and runs the command once as an `abacus-ops` task on the current release image. A file is never edited after it merges: a new request is a new file. Requests and their arguments never carry client data, names of real people or secrets.
