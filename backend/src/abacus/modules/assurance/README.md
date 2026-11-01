# assurance

Zone: amber, with red paths `release.py` and `archive_gate.py`. Pre-registered by F-03-T08 (ADR-140).

Owns the assurance service line. Built so far (A-01, A-02): the audits index and cockpit (`index.py`, `cockpit.py`, `audits_contract.py`; AUD-01 to AUD-03), phases in record mode and by gate (`phase.py`), release and archive (`release.py`, `archive_gate.py`), completion, the trial balance read model and mapping (`tb_read_model.py`, `mapping.py`), home counts and review gates.

- **Contracts:** `docs/contracts/audits-cockpit.md`; the binder export it offers lives in `evidence` (`docs/contracts/engagement-export-v1.md`).
- **Flags:** `audits.cockpit`, `audits.binder_export` (both retire by the Thu May 27, 2027 train).
- **Compute:** `compute/materiality.py` (A-04-T08, DEC-1850): the pure materiality engine (Decimal, no clock, `engine_version` and `inputs_hash` on every figure); `compute/` imports only `kernel.numeric` and `kernel.calendar` (the import-linter compute contract).
- **Runbook:** RB-33 binder export and pilot rollback (`docs/runbooks/RB-33-binder-export-and-pilot-rollback.md`).

Will own (docs/plan/03-backend-architecture.md §2.2): materiality, risks, controls, walkthroughs, service organizations, confirmations, findings, misstatements, deficiencies, EQR, completion, letters, reports and releases, group audit components.
