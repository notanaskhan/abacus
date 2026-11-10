# Discovery notes · PF-X1 (synthetic, DEC-4100)

F-09-T51 for the synthetic test pilot firm, the only Pilot 0 partner while no real firm has signed
(DEC-1391). **Synthetic (PF-X1).** Read from the Brightwater Hale scenario, not from an interview.

| Topic | PF-X1 |
|---|---|
| Ledger | the fake QuickBooks Online and NetSuite connectors; Granite Peak's FY2025 and FY2026 NetSuite trial balances (`brightwater_hale/files/`) |
| Tax engine | CCH Axcess, through the fake file bridge (`abacus_tools/fakes/cch_axcess.py`) |
| E-signature | DocuSeal (ADR-342) |
| Identity | the local fake OIDC server; no Google Workspace |
| Size | 46 staff; audit, tax and CAS service lines |

A real firm's notes come from its own interviews (`interview-guide.md`).
