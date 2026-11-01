---
id: RB-19
title: Tax-engine bridge failure near a filing deadline
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-08-13
---
# RB-19 · Tax-engine bridge failure near a filing deadline

| Field | Value |
|---|---|
| Owner | N (the bridge); AY reaches the partner's CCH admin |
| Severity range | SEV2 inside a filing window (Sep 15, Oct 15); SEV3 outside it |
| Linked from | TAX-09 (export refused or an import refused), ADM-08's tax-engine segment, `export_disabled` and `engine_file_invalid` answers in the API logs |
| SLO affected | none: the engine stays the system of record (R-04, DEC-49) |
| Kill switches that apply | the W2 capability `cch_axcess` in `docs/architecture/write-capabilities.yaml`; the firm's file-bridge install (ADM-08, `export_settings.enabled`); the flag `tax.engine_bridge` (routes and TAX-09 actions) |
| Rehearse by | Fri Aug 13, 2027, on staging with the synthetic test firm (PF-X1), rehearsed by AY |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Accrued never transmits and never writes into CCH Axcess: it hands the engine a file a person
imports (W2 file mode) and reads back the files a person exports (ADR P-18). When that bridge
fails, returns keep moving in CCH; Accrued's record falls behind and must be brought back by people,
with evidence, never by guessing.

## 1. Recognise it
- **Export:** "Export to CCH" answers 409 `export_disabled` (a switch is off: `facts.switch` names
  `capability` or `firm`) or the export workflow fails rendering or storing the workbook.
- **Import:** an engine file is refused 422 `engine_file_invalid` (`facts.reason`: `bad_pdf_name`,
  `not_a_pdf`, `unknown_pdf_kind`, `unreadable`) or 409 `engine_return_mismatch` (the file belongs to
  another return).
- **Format change:** every import of one kind fails for one firm the same day: the partner's Axcess
  changed its export (R1, RK-48).

## 2. Contain
- One firm or one format: switch that firm's file-bridge install off in ADM-08 (a firm admin, fresh
  MFA). TAX-09 then shows the export as disabled; nothing half-written leaves.
- A defect in our adapter for everyone: turn the W2 capability off in the write-capability
  registry (one protected PR) or `tax.engine_bridge` off per firm (`make flag`, Tuesday slot rules
  do not apply to a kill). Imports already approved stay; nothing is deleted.

## 3. Preserve
- The refused file's hash and name (never the file in a ticket: it carries return information) and
  the `engine_sync_events` row ids for the return; the export id and its workflow id.

## 4. Assess
- Which returns are inside 10 business days of their due date (TAX-01 "Due this week" tile; the
  C21 due dates pinned on each return).
- Whether the fault is ours (adapter, mapping, golden file mismatch) or the engine's format.

## 5. Notify
- AY tells the partner and the firm's CCH admin, using the contact held in the vault for that
  pilot code (opaque reference only, never in git), what is affected and the fallback below.
- No client hears of it: the client sees nothing of the bridge.

## 6. Recover
1. **Manual entry fallback (near a deadline).** The preparer keys the return in CCH directly from
   the approved checkpoint (TAX-09 shows its values), and attaches the engine's own PDFs to the
   return through the bridge's `pdfs` import when it works again, or as evidence uploads on the
   binder meanwhile. A person marks the export done ("Mark exported" on TAX-09, with the engine reference),
   so the file-mode chip reads Synced on a person's word (ADR-231, DEC-1160). The 8879 binding still
   comes from the approved checkpoint, so drift relock and the transmission gate keep working.
2. **Adapter fix.** Fix forward on the hotfix lane (production broken), with a golden file for the
   new format; never edit a frozen mapping in place. Then switch the install back on in ADM-08.
3. **Catch-up.** For each affected return, export again from its latest approved checkpoint, or
   import the engine's files in order (return, pdfs, acks); an import approved twice is refused,
   so the order is safe to repeat.

## 7. Verify
- TAX-09's chip reads Synced on every affected return; ADM-08's last sync opens the latest.
- The packet's 8879 amounts equal the engine's (no relock pending), and each transmitted return's
  acks are imported.

## 8. Review
Typical actions: a golden file for the changed format, a probe of the partner's Axcess version at
the window's start (Pilot 0 check), and the fallback rehearsed again before the next deadline.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
