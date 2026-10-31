# integrations

Zone: red. C20 v1 (`docs/contracts/c20-integrations.md`, final since A-02-T38). Other modules import only `api.py` (DEC-13). Owns the integration catalogue, firm installs, sealed secrets, the write-capability registry's runtime, engine settings and the e-signature install (ADR-103).

- **Catalogue** (`catalog.py`, `catalog_load.py`): platform rows loaded by the ops role from a reviewed document (`abacus_tools.integration_catalog`), never seeded. Catalogue honesty: a row is `available` only when its adapter is registered here with the row's category and connection provider; else `coming_soon` (POR-16 offers *Export instead*, ADR-108).
- **Adapters** (`adapters.py`, `qbo_adapter.py`): metadata only (key, category, provider, read scopes, hosts) that must match the registry's read connector entry; the QuickBooks Online adapter registers only where the app registration is configured. The connection itself runs through `connections` (`integrations → connections`; `connections` never imports `integrations`).
- **POR-16** (`client_connect.py`, `routes.py`): cards and start/reconnect/disconnect over `connections.start_entity`, behind `connections.portal_v2`; consent copy is catalogue content and read-only (DF-19).
- **Reconnect requests** (`reconnect.py`): AUD-06's *Ask client to reconnect*, mailed from the firm's `reconnect_request` template (R-01, POR-20); RB-05.
- **Writes** (`writes.py`, `capabilities.py`, `_capabilities.py` generated from `docs/architecture/write-capabilities.yaml`): `authorise_write` / `execute_write` refuse every write but N-02's W7 (DEC-1280); W1 refused for attest clients at registry level.
- **Secrets** (`secrets.py`): sealed with the tenant key, the install's id as associated data; erased on disconnect. **E-signature install** (`esign_install.py`): DocuSeal (ADR-342, DEC-1279).
- **Engine settings** (`engine_settings*.py`): T-01's CCH file bridge settings (ADM-08).

Runbooks: RB-04 (provider outage), RB-05 (expiring-connections wave). Hand-off notes: `docs/handoffs/A-02/`.
