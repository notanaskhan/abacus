---
title: Firm rollback (flags off, engagement packages out, verified in a blank folder)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-05-28
---
# Firm rollback

| Field | Value |
|---|---|
| Owner | N (SEV1/2 on-call primary, `docs/ops/pilot/README.md`); the other founder approves the flips |
| Task | Q-04-T019 (A-01 hand-off; chapter 10 M9; SPEC-402 AC-4) |
| Target | inside **60 minutes** from the decision to every package verified |
| Rehearse | on the production canary before M9 (Tue Jun 1, 2027), then each quarter (Q-04-T107) |
| Kill switches that apply | every flag the firm has a value for (`make flag … --all-off`); A-01's `audits.binder_export` stays on until the packages are downloaded |
| Related | RB-33 (one firm's audit binders, in more depth), RB-13 (offboarding: a separate decision), RB-14 (legal holds still apply) |

A rollback takes a pilot firm back to where it was before Accrued: its new surfaces off, its
engagements in its own hands as files it can open without us. Nothing is deleted: evidence and
ledger snapshots are immutable, and retention and holds still apply. This procedure holds no
firm names, hosts, account ids or client data: firms are pilot codes, the canary is "the canary".

## 1. Decide and start the clock (minute 0)
1. Either founder decides; a DEC row names the reason (as RB-33 §1). Write the start time in the
   rehearsal table below (or the incident's timeline for a real rollback).
2. No deploy in flight, no window open for the firm (`make windows`); note the firm id (`FIRM`)
   and the engagement(s) to export.

## 2. Flags off (target: by minute 10)
1. Keep `audits.binder_export` on until §3 is done; everything else goes now, in one unit of work:
   `make flag FIRM=$FIRM ALL_OFF=1 OPERATOR=<you> REASON="firm rollback, <DEC>" APPROVED_BY=<other founder>`
   (`abacus_tools.flags --all-off`; one `feature_flag.bulk_off` event), then set
   `audits.binder_export` back on for the export only.
2. Check: the firm's staff see the pre-pilot screens; its portal users see no new surface.

## 3. Export each engagement (target: by minute 40)
For each engagement in scope (the rehearsal: one), as the engagement partner or manager with fresh
MFA, onshore (A-01's rules; RB-33 §3 has the detail):
1. AUD-02 **Export binder…** (or `POST /v1/work-items/{id}/exports` with `Idempotency-Key`, all
   binders, `include_audit_trail: true`); wait for `ready`.
2. Download it (`GET /v1/exports/{id}/download`; resume with `Range`).
3. Record the export id and the bundle SHA-256 (the `ETag`) in the log (vault), never the files.

## 4. Verify in a blank folder (target: by minute 55)
On the machine the firm's workpapers live on (the rehearsal: the operator's), into a folder that
does not exist yet:

    python -m abacus_tools.package_check <export>.zip --into <new folder>

It refuses a package that would write outside the folder, and passes only when
`manifest.sha256` and `checksums.sha256` both verify, every file is listed and the manifest agrees.
Where the tool is not available, the package README's own check is the same:

    cd <new folder> && shasum -a 256 -c manifest.sha256 && shasum -a 256 -c checksums.sha256

Open `index.xlsx` and one evidence file to see the folder works as the firm's workpapers.

## 5. Close (minute 60)
1. `audits.binder_export` off once the firm confirms receipt.
2. Write the end time; the total must be at most 60 minutes. Close the DEC row with the export ids.
3. Rehearsal only: set this file's `last_rehearsed` to the date, and turn the canary's flags back
   on from its recorded values (the bulk-off event lists them).

## Rehearsals

| Date | Where | Who | Start | Flags off | Exported | Verified | Total minutes | Result |
|---|---|---|---|---|---|---|---|---|
| — | production canary | N, AY approving | — | — | — | — | — | not run: the production compute stack and canary tenant are not provisioned yet |
