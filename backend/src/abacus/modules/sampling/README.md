# sampling

Populations and selection by code, pure functions over ledger snapshots (ADR-132; SPEC-037).

- `build_population(postings)`: postings grouped into journal entries by ledger's `journal_key`;
  `tie_out` checks lines and debits against the snapshot.
- `select(population, parameters, picks)`: criteria v2 (`large`; and, at or above the trivial
  threshold, `round`, `near_year_end`, `manual`, `rare_account`, `weekend`, `keywords`), a random
  draw from the rest (`seeded_v1`: only `random.Random(seed).random()`, whose sequence Python
  guarantees), and people's picks. Every selected entry lists every rule that chose it.
- `MANUAL_KINDS`: manual transaction types per export format (D2).

## Sampler library v2.3 (`compute/`; ADR-340; A-03-T04)

Red, protected path (A-03-T01; `docs/architecture/protected-paths.md`). Pure: imports only the
standard library, `kernel.numeric` and `kernel.calendar` (import-linter, A-03-T21).

- `canonical(records)`: canonical order by normalised record key, total, SHA-256 population hash.
- `v2_3.select(population, method, seed=, size=, strata=)`: `attribute_nonstatistical`,
  `attribute_statistical` (uniform without replacement) and `threshold_random_stratified`; every
  output carries `engine_version`, `inputs_hash` and `items_hash`.
- The only random primitive is `random.Random(seed).getrandbits(32)` (`draw.Stream`); rejection
  sampling and the partial Fisher–Yates walk are ours. Seeds are 24-bit.
- `attribute_size`, `udl`/`udl_percent` (exact binomial), `projected_misstatement`/`projected_misstatement_ratio`.
- `SAMPLER_VERSIONS` registers `2.3` frozen; new behaviour is a new version. `seeded_v1` (journal
  entries, ADR-132) is separate and unchanged.
