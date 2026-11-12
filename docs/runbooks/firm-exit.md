---
title: Firm exit (flags off, dual-approved firm export, data return, crypto-shred certificate)
owner: builder
alarms: []
last_rehearsed: 2026-11-12
rehearse_by: 2027-05-28
---
# Firm exit

| Field | Value |
|---|---|
| Owner | the builder (under the solo amendment, every founder role); the key custodian (break-glass, ADR-156) schedules the key deletion |
| Task | Q-04-T035 (TASK-7800); ADR-034, ADR-156, ADR-179; DEC-72 |
| Target | export verified within 2 business days of the exit decision; key deletion scheduled at the end of the agreed grace period |
| Rehearse | on the rehearsal tenant (synthetic) each quarter with the rollback runbooks (Q-04-T107); the production canary once it exists |
| Kill switches that apply | every flag the firm has a value for (`make flag … ALL_OFF=1`); `compliance.firm_export` stays on until the export is downloaded |
| Related | `firm-rollback.md` (a rollback keeps the firm; this ends it), RB-13 (offboarding header), RB-14 (legal holds), RB-33 (one firm's binders), ADR-179 (destruction certificates) |

A firm exit ends a firm's use of Accrued. The firm gets everything it holds as files it can open
without us; then, after the grace period its exit terms set, its per-tenant key is destroyed, so
nothing of it can be read again (ADR-034). Nothing inside an engagement is deleted along the way:
evidence and ledger snapshots are immutable, and objects under COMPLIANCE Object Lock persist as
unreadable bytes until their retention floor date (ADR-156). This procedure holds no firm names,
hosts, account ids or client data: firms are pilot codes, the canary is "the canary".

**Open (counsel):** the exit terms (grace period, what is returned, who signs for the firm) are
counsel's (ADR-034 follow-up). Until they are written, the grace period is 30 days from the day the
firm confirms receipt, and §5 waits for the firm's written confirmation.

## 1. Decide (day 0)
1. A DEC row records the exit: the firm's pilot code, the reason, the grace period and who at the
   firm confirms receipt. Write the start in the log below (or the incident timeline).
2. Check holds: `GET /v1/legal-holds` for the firm. A held engagement or client stops
   §5 until the hold is released (RB-14); the export in §3 still runs.
3. No deploy in flight and no window open for the firm (`make windows`).

## 2. Flags off
In one unit of work, everything but the export:

    make flag FIRM=$FIRM ALL_OFF=1 OPERATOR=<you> REASON="firm exit, <DEC>" APPROVED_BY=<approver>

then set `compliance.firm_export` back on for the export only. Check: the firm's staff see no new
surface; the portal's clients see the firm's closing notice only.

## 3. The firm export, dual-approved (DEC-72)
1. The firm's security admin requests the export of everything it holds in ADM-06 (**Export firm
   data**, or `POST /v1/firm/data-exports` with an `Idempotency-Key`), with a fresh second factor,
   naming a partner-level approver. The database refuses the same person twice.
2. The approver approves (`POST /v1/firm/data-exports/{id}/approve`, fresh MFA). The build makes
   one A-01 engagement package per engagement the approver may read (Q-02-T47); any other
   engagement is named in `index.json`'s `omitted` with its reason, so every engagement is
   accounted for once. An `omitted` engagement the firm needs is exported by its partner through
   A-01 (`firm-rollback.md` §3) before §5.
3. Once `ready`, the requester or the approver downloads it within 7 days (a 15-minute link, onshore).
   Note the export id, `bundle_sha256` and `manifest_sha256` from the export's history card.

## 4. Verify where the firm receives it
On the machine the firm's files go to, into a folder that does not exist yet:

    python -m abacus_tools.firm_exit verify <firm-export>.zip --into <new folder> \
        --bundle-sha256 <bundle_sha256> --manifest-sha256 <manifest_sha256> > verify.json

It passes only when the archive and `manifest.json` match the export row, every file the manifest
names matches its size and digest, nothing else is in the archive, and each engagement package
passes `abacus_tools.package_check` (both checksum files, nothing unlisted, the manifest agrees).
Keep `verify.json`: the certificate is made from it. Where the tool is not available, each
package's README check is the same (`shasum -a 256 -c manifest.sha256`, then `checksums.sha256`).

The firm confirms receipt in writing; the grace period starts that day.

## 5. Crypto-shred at the end of the grace period
1. Re-check holds (§1.2). A hold stops here.
2. `compliance.firm_export` off; the firm's memberships are deactivated (no sign-in remains).
3. The key custodian (break-glass, two people as RB-12) schedules the tenant key's deletion, and
   keeps the answer:

       aws kms schedule-key-deletion --key-id <the firm's key> --pending-window-in-days 30 \
           --output json > kms.json

   The replica key in the DR region is deleted with it (a multi-Region key's replicas go first).
   No application role can do this (an SCP reserves it to the custodian, ADR-156).
4. The certificate, from the verify report and the custodian's answer:

       python -m abacus_tools.firm_exit certificate --verification verify.json \
           --key-deletion kms.json --firm <pilot code> --out exit-certificate.json

   It refuses a report that did not verify, an export without two different people, a key that is
   not `PendingDeletion`, or a deletion date before the export was built. It names both dates (the
   export verified, the key deleted), the export's digests and its own SHA-256. It goes to the vault
   and to the firm; it never goes in git.

## 6. Close
1. Close the DEC row with the export id, the certificate's SHA-256 and the key deletion date.
2. After the deletion date, check the key is gone (`aws kms describe-key` answers `NotFound` or
   `PendingDeletion` has ended) and note it in the log.
3. Rehearsal only: set this file's `last_rehearsed`, and add a row below.

## Rehearsals

| Date | Where | Steps | Result |
|---|---|---|---|
| 2026-11-12 | rehearsal tenant (synthetic, local stack; in-memory key service) | §3 dual-approved firm export through the real routes, §4 verify against the row's digests, §5.4 certificate from the custodian's answer shape | passed: `backend/tests/integration/test_q04t035_firm_exit_rehearsal.py`. §2 flags off is rehearsed by `firm-rollback.md`; §5.3 needs the custodian on AWS (not run; no production stack) |
