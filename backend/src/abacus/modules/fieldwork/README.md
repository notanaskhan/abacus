# fieldwork

Audit procedures and their records (SPEC-037; ADR-116, ADR-117). Code builds the population and
selects; people conclude.

- **Materiality** (`GET`/`PUT /v1/engagements/{id}/materiality`, `materiality.set`): overall,
  performance and trivial, with the benchmark as text, entered by the partner or manager (Q3).
  Insert-only; the newest is current.
- **Firm defaults** (`GET`/`PUT /v1/firm/fieldwork-settings`, `methodology.read` / `.manage`):
  the criteria's parameters, copied into each new procedure (Q6).
- **Journal entry testing** (`POST /v1/engagements/{id}/procedures`, once per engagement; flag
  `fieldwork.procedures`): parameters, a seed chosen by code, people's picks with reasons
  (`…/picks`). `POST …/select` (202) starts `ProcedureSelectWorkflow`: `selecting.run_selection`
  streams the newest reconciled general ledger for the engagement's entity and year end, builds
  the population with `sampling`, ties it out (`population_not_tied` otherwise), selects, and
  records `populations`, `selections` and `selected_items` in one transaction. Changing the
  parameters and selecting again keeps the old selection. Not performed (D4): entries after year
  end (SPEC-038) and who entered an entry (not in exports).
- Results, the workpaper, sign-off and screens: TASK-078.
