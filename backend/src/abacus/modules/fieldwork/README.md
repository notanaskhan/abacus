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
- **Results** (`PUT …/items/{item}/result`, `procedure.run`): `supported`, `exception` (note) or
  `not_tested` (reason), with evidence versions the engagement holds; appended, the newest counts.
  `POST …/items/{item}/request-support` creates an ordinary request worded with the entry's
  reference, date and amount only. `PUT …/conclusion`: the preparer's conclusion.
- **Workpaper** (`workpapers.py`, `workpaper.py`; ADR-116): `POST …/workpaper/sign-ready`
  (`workpaper.sign_ready`) makes the next `workpaper_versions` row, holding the selection, result,
  conclusion and materiality IDs and the SHA-256 of the content rendered without the Sign-off
  sheet; `POST …/workpaper/sign-reviewed` (`workpaper.sign_reviewed`) by someone else, while
  nothing has changed. `GET …/workpaper/file?version=n` re-renders and checks the fingerprint (D1);
  without a version, the current draft. Sheets: Summary, Selections, Exceptions, Sign-off.
- **Screens:** the engagement's Fieldwork tab; "Journal entry testing defaults" in firm admin →
  Methodology.
