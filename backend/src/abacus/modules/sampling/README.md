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

## Populations, sample sets and item requests (A-03-T07, T10, T13; contract `docs/contracts/sampling.md`, frozen v1)

- **Populations** (`populations.py`): built once, frozen, from an upload or a ledger snapshot.
  - Records keep display fields only, with their canonical SHA-256 and total.
  - A Restricted column is refused (422 `restricted_column`) and never copied.
  - Completeness ties compare the total with named amounts by code.
- **Sample sets** (`sample_sets.py`): numbered versions, each drawn once and frozen (0520's trigger).
  - **Size.** The firm's size table or the exact binomial size; a smaller size is an override with a rationale.
  - **Seed.** 24 server bits (only the scenario loader seeds a synthetic firm).
  - **Draw.** `SampleDrawWorkflow` runs it (`draw.run_draw`; replay histories `sample-draw-v1-*.json`).
  - **Approval.** An EP or manager approves through review's L2. 409 `population_not_tied`, `content_changed` or `override_not_acknowledged`; the preparer never approves.
- **Item requests** (`item_requests.py`): one request per template and sample item, through `requests.api.create_items_bulk`.
  - A third party gets one `request_item` grant per delegated request (INV-4).
  - The preview names no seed or parameter.
- **Rollout:** behind `sampling.sample_sets`.
  - Flip per firm on Tue Sep 21, 2027, after the CPA signs `docs/quality/golden-reviews/sampling@2.3.md`.
  - Retire in the Oct 21 batch.
  - Re-perform, rollback and renewal are in `docs/runbooks/RB-46-sampler-and-mapping.md`.
- **Tests:**
  - The module's own: `tests/unit/sampling/`, `tests/golden/sampling/`, `tests/integration/backfill/test_a03t07_*`, `t10`, `t13`.
  - Independent (ADR-078): `test_a03t18_*`.
