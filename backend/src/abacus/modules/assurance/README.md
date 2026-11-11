# assurance

Zone: amber, with red paths `release.py` and `archive_gate.py`. Pre-registered by F-03-T08 (ADR-140).

Owns the assurance service line. Built so far (A-01, A-02): the audits index and cockpit (`index.py`, `cockpit.py`, `audits_contract.py`; AUD-01 to AUD-03), phases in record mode and by gate (`phase.py`), release and archive (`release.py`, `archive_gate.py`), completion, the trial balance read model and mapping (`tb_read_model.py`, `mapping.py`), home counts and review gates.

- **Contracts:** `docs/contracts/audits-cockpit.md`; the binder export it offers lives in `evidence` (`docs/contracts/engagement-export-v1.md`).
- **Flags:** `audits.cockpit`, `audits.binder_export` (both retire by the Thu May 27, 2027 train).
- **Compute:** `compute/materiality.py` (A-04-T08, DEC-1850): the pure materiality engine (Decimal, no clock, `engine_version` and `inputs_hash` on every figure); `compute/` imports only `kernel.numeric` and `kernel.calendar` (the import-linter compute contract).
- **Runbook:** RB-33 binder export and pilot rollback (`docs/runbooks/RB-33-binder-export-and-pilot-rollback.md`).

Will own (docs/plan/03-backend-architecture.md §2.2): materiality, risks, controls, walkthroughs, service organizations, confirmations, findings, misstatements, deficiencies, EQR, completion, letters, reports and releases, group audit components.

## EBP modules (A-05; A-05-T62)
- **Flags:** `ebp.modules`, `ebp.form5500_tieout`, `assurance.estimates_rp`; the modes ride A-04's `workpapers.drafting`; the EBP audits module is a DB entitlement (ADR P-28).
- **Compute:** `compute/ebp/*.py` (provisions, eligibility, remittance, loans, accounts, expenses, form5500 with `schedule_4i`, estimates): pure Decimal engines stamping `engine_version` and `inputs_hash`; reference data in `compute/ebp/reference/*.yaml` (PROTECTED, CPA-reviewed).
- **One late-remittance object:** `ebp_late_remittances` (0658), read in place by EBP-04, EBP-07 4a and AUD-27.
- **Runbook:** `docs/runbooks/ebp-modules.md` (flip, rollback, corrections, recompute, annual reference updates).

## Release and archive (A-07; A-07-T52)
- **G8, release.** `release.py` and `release_workflow.py`: the engagement partner, a fresh second
  factor, an approval grant bound to the report version and the gate hash. `ReleaseWorkflow`
  re-checks G5 to G7 and records `report_releases` in one unit of work. A refusal voids the
  grant and records nothing. In `assurance_release_mode = external`, `record_release` records a
  release made outside Accrued.
- **Clocks.** `clocks.py`: the archive (AU-C 230) and the AU-C 265 letter, each 60 days from
  the release date, at risk from 7 days, stopped by the lock or the sent letter.
- **G9, archive.** `archive_gate.py` computes the nine items and the A to H binder index.
  `archive_lock.py`: a manager or the partner locks at 9 of 9 on the checklist they saw.
  `ArchiveLockWorkflow` seals (`archive_seal.py`: RFC 8785 manifest, a sorted Merkle root) to
  `records` in COMPLIANCE mode until release + 5 years, extends evidence GOVERNANCE retention,
  then sets `locked`.
- **After lock.** `archive_additions.py`: a person adds, only the partner approves (never the
  person who added it), and the addition's manifest is sealed before its decision.
  `SealVerifySweepWorkflow` re-verifies every seal monthly; a mismatch is RB-29.
- **Immutability** is the kernel's `archived_guard()`. To add a guarded table or an exception
  kind, follow the backend-module skill's "A guarded table and an archived-write kind".
- Operations: `docs/runbooks/audit-release-archive.md`.
