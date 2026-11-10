# PF-X1 synthetic files (DEC-4100)

Inputs for the rows that need a pilot firm, run on the synthetic test pilot firm PF-X1
(Brightwater Hale). Everything here is synthetic and says so on every page.

| File | Used by | Loaded how |
|---|---|---|
| `synthetic-msa.md`, `synthetic-dpa.md`, `synthetic-pilot.md` | dossier contract-1 (F-09-T110, Q-04-T021) | never loaded into the tenant: a provider's contract with a firm is Accrued's record (the vault), not firm content. The dossier names their `V-SYN-…` entries |

Not here, on purpose: counsel's text (DEC-2098), any price, any real firm's or person's name, and
any kit sample data (DF-35). Firm content (templates, PBC lists, clients) reaches the tenant only
through service APIs and import endpoints (AGENTS rule 16), as the other slices do.
