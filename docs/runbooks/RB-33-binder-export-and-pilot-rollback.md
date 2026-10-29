---
id: RB-33
title: Binder export and pilot rollback
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-05-25
---
# RB-33 · Binder export and pilot rollback

| Field | Value |
|---|---|
| Owner | the builder (N lane), with the pilot firm's engagement partners |
| Task | A-01-T30 (A-01 DoD 10; M9 rollback path, Tue Jun 1, 2027) |
| Kill switches | `audits.binder_export` (off: export routes 404, no "Export binder…" entry); `audits.cockpit` (off: `/audits*` and `/v1/audits*` 404) |
| Alarms | none wired yet (no alarm resource in `infra/` exists for any module). Two are specified in §5 for Q-01's alarm work; until then the checks in §5 are run by hand daily during the pilot |
| Contract | `docs/contracts/engagement-export-v1.md` (format `accrued.binder-export` 1.0, SPEC-344) |

A pilot rollback hands a firm its audit binders as files and takes the audit surfaces away from it, without losing a byte or touching another firm. The export is the only exit path: no presigned link, no database dump (ADR-104, ADR-036).

## 1. When to roll back

Roll back one pilot firm when either founder decides it (a DEC row names the reason): a SEV1 or SEV2 touching its audits that is not fixed within the pilot's agreement, the firm asks to stop, or Pilot 0's exit criteria fail (Q-04). Never roll back more than the firm named.

## 2. Before you start (15 minutes)

1. No deploy in flight and no release window open for the firm (`deploy/windows.yaml`; `make windows`).
2. Note the firm id (`FIRM`), the decision DEC id (`DEC`) and the people who will download (each an engagement partner or manager on their engagements, with fresh MFA, onshore).
3. Check the export is on for the firm: `audits.binder_export` (if off: `make flag FIRM=$FIRM FLAG=audits.binder_export VALUE=true OPERATOR=<you> REASON="RB-33 rollback, $DEC" APPROVED_BY=<other founder>`).

## 3. Export every binder (per audit work item)

For each audit work item of the firm (AUD-01 lists them; `GET /v1/audits`):

1. The engagement partner opens the work item's AUD-02 or AUD-03 and chooses **Export binder…** (or `POST /v1/work-items/{id}/exports` with `Idempotency-Key`, scope all binders, `include_audit_trail: true`). The export is `queued` for its 10-second Undo window, then `packaging`, then `ready`.
2. Download it (`GET /v1/exports/{id}/download`; resumable with `Range`). Large binders: resume with `Range: bytes=<received>-` and `If-Range: "<etag>"`; never ask support for an object key (there is none to give).
3. Verify from the unpacked folder: `shasum -a 256 -c manifest.sha256` and `shasum -a 256 -c checksums.sha256`. Both must print only `OK`.
4. Record the export id, bundle SHA-256 (the ETag) and the verifier's name in the rollback log (vault, `V-…`); never the files.
5. Repeat within the 7 days an export lives (`expires_at`); after that, export again.

## 4. Take the audit surfaces away

Only once every binder of the firm is downloaded and verified:

1. `make flag FIRM=$FIRM FLAG=audits.cockpit VALUE=false OPERATOR=<you> REASON="RB-33 rollback, $DEC" APPROVED_BY=<other founder>`.
2. `make flag FIRM=$FIRM FLAG=audits.binder_export VALUE=false …` once the firm confirms receipt.
3. Nothing is deleted: evidence and ledger snapshots are immutable (AGENTS.md rule 4) and retention and legal holds still apply (RB-14). Offboarding is RB-13, a separate decision.
4. Tell the firm (the pilot channel), and close the DEC row with the export ids.

## 5. Export failures and integrity

| Signal | Where | Means | Do |
|---|---|---|---|
| An export ends `failed` | audit `engagement_export.failed` (`failure_code`); AUD-02 sheet "Export failed" | the build stopped (a section provider raised, storage refused, a withdrawn file) | Read the code; retry once with a new Idempotency-Key; a second failure is a SEV3 for the builder |
| `integrity_mismatch` failure | `engagement_export.failed` with `failure_code = integrity_mismatch` | a stored file's bytes no longer match the SHA-256 recorded at upload | Stop: this is RB-29 (integrity alert), not a retry |
| 410 `export_expired` on download | the API | 7 days passed, or a held file was withdrawn since (DEC-537) | export again |
| 429 `download_rate_limited` | the API | 60 requests a minute or 2 open streams per person | wait `retry_after` |

**Alarms to wire (Q-01, Terraform):** `export.failed-rate` (more than 3 `engagement_export.failed` in an hour, any firm, SEV3, links RB-33) and `export.integrity-mismatch` (any `failure_code = integrity_mismatch`, SEV2, links RB-29 and RB-33). Until wired, during a pilot: run the audit explorer daily for `engagement_export.failed`.

## 6. Load check (2 GiB)

A-01 R4: a multi-GB EBP binder must download through the API. Before the first pilot (staging, synthetic firm only): build a binder of about 2 GiB from the scenario's large-file set, export it, download it once whole and once interrupted at about half and resumed with `Range`, and check both against `checksums.sha256`. Record the times in the rehearsal line below. The bundle streams in 1 MiB slices from 64 MiB sealed segments; a stream stops at 30 minutes, so a resume is expected on slow links.

## 7. Flag retirement plan

Both A-01 flags retire by the **Thu May 27, 2027** release train (A-01 DoD 9): `audits.cockpit` and `audits.binder_export` become always on, their flag-off branches and 404s go, and this runbook's kill-switch rows move to the per-firm `audits` entitlement. Until then each renewal stays under DEC-137 and outside the release windows (`make flag-calendar`).

## Rehearsals

| Date | Where | Who | Result |
|---|---|---|---|
