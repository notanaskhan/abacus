# sampling

Populations and selection by code, pure functions over ledger snapshots (ADR-132; SPEC-037).

- `build_population(postings)`: postings grouped into journal entries by ledger's `journal_key`;
  `tie_out` checks lines and debits against the snapshot.
- `select(population, parameters, picks)`: criteria v2 (`large`; and, at or above the trivial
  threshold, `round`, `near_year_end`, `manual`, `rare_account`, `weekend`, `keywords`), a random
  draw from the rest (`seeded_v1`: only `random.Random(seed).random()`, whose sequence Python
  guarantees), and people's picks. Every selected entry lists every rule that chose it.
- `MANUAL_KINDS`: manual transaction types per export format (D2).
