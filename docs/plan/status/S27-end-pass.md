# S27 end pass (2026-11-04)

One review, test and gate pass over the S27 stack (#1176 to #1217) before its single CI run, and
the evidence for the S27 review and proof rows (DEC-2259). Every firm-facing step ran on the
synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and is reported as synthetic.

## Numbering
Main moved during the build (#1174 and #1175 took TASK-3247, TASK-3248, DEC-2228 and DEC-2229).
The stack was rebased and its own ids renumbered in every commit: TASK-3247 → TASK-3288,
TASK-3248 → TASK-3289, DEC-2228 → DEC-2260, DEC-2229 → DEC-2261 (only lines not already on main).

## Tests run
- Backend, every S27 unit, contract and security file, the generated security suites (permission
  matrix, fresh MFA, route introspection, tenant isolation) and the 0664/0665/0666 integration
  suites (down and up with forced RLS, human-only CHECKs): 10,567 passed.
- Web, the S27 screens and their hosts (AUD-02, AUD-09, AUD-16, NOT-02, BND-03, EBP-04,
  evaluation, A-07 view models and contracts, routes, fixtures, app-core, AUD-15, SHL-11, POR-05).
- Gates: `make check-fast` green after the fix round (ruff, pyright strict, import-linter, banned
  patterns, docs and runbooks, generated files and heads, secrets scan, dependencies, web tsc,
  eslint, prettier and bundle budgets).

## Found and fixed (one round)
- Independent tests surfaced INV-5: an agent-raised finding read "Accrued Agent" without its
  person. Fixed: `agents.api.run_initiators` and "<person> via Agent" in `findings._rows`.
- A-07 stubs: container fields unclassified (ADR-031); `report.release` and `archive.lock` did not
  deny the system and the client principals explicitly; the T04/T05 tests read `document()` as a
  dict and miscounted the routes (59 = 18 + 41).
- Status vocabulary: `eqr_checklist_item.done` used an undrawn disc; now `check_olive`.
- Pyright strict across the S27 services and tests (casts on JSON reads, typed default factories,
  the repository's per-line ignores for private use in tests).
- Integration fixtures broke the evidence content-address CHECK; one EQR test claimed an actor-id
  check 0664 does not make (it binds the actor kind); the OCR scan flagged the column registry.
- Web: AUD-16's pane needed the router-safe overlay opener; NOT-02 and BND-03 stay `planned` in
  the manifest (with their paths) until their inbound links are wired.
- Banned patterns: `Any` and type-checker ignores explained (ADR-009); the Textract client built in
  `kernel.storage` (STORE-001); notices reaches requests' and organisations' data through their
  APIs (OWN-001); notices may import methodology and reporting (BOUND-002, DEC-2262); a built SQL
  string replaced by bound parameters (SQL-001); the confirmation send authorised on a typed person
  (AGENT-001); a glossary ban on "publish" that hit unrelated code removed.
- RB-47 written for the Textract alarms (ADR-098); task frontmatter uses the SPEC-000 row form.
- Secrets scan: a test TIN made invalid-area; `rule_key` in the BND-03 seed allow-listed.
- The route table and the OpenAPI document regenerated.

## Security review (red diffs)
0664 to 0666: every new table tenant-scoped with forced RLS, insert-only and immutable where the
model says so, human-only CHECKs bound to `app.actor_kind`; chain 0663 → 0666 on main's head. The
OCR port logs hashes and counts only; the Textract module carries no secrets; every new route
declares one matrix action and denies the agent its writes (generated suites green). No open
finding after the fix round.

## Review and proof rows
| Row | Evidence | Open |
|---|---|---|
| Q-03-T182 | The N-provided contract suites in the run above | Nightly drift report: no live provider run here |
| Q-03-T183 | AY-provided contract suites in the run above | Connector suites against provider sandboxes need credentials (human) |
| Q-03-T184 | Compliance invariant catalogue and generated coverage (security suites green); DAST, Inspector and GuardDuty need the hosted stack | Hosted findings triage |
| Q-03-T185 | Generated allow/deny/cross-tenant tests cover every new route (route introspection, matrix suites) | None found uncovered |
| Q-03-T186 | Flaky quarantine unchanged | Parity re-measure on Playwright 1.64.1 (Q-03-T181's drift) and the production canary need the visual run and production |
| I-01-T22 | — | HOME-02 Tier C/D parity, axe and keyboard need the visual run; j23/j13 full-stack steps need staging |
| Q-04-T097 | — | The PF-X1 `home.approvals` flips run in the staging windows (staging deploy is the batch's) |
