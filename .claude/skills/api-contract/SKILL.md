---
name: api-contract
description: Create or change an API contract stub for one screen family — Pydantic models with classification tags, routes that declare one matrix action each and return seed-derived fixtures behind a flag, matrix and flag entries, make regen, and docs/contracts/<name>.md. Use when a screen needs an endpoint that does not exist yet, or when an existing response shape must change.
---

# API contract stub (contract-first; ADR P-36; chapter 01 §1.3.2)

## Paths that arrive later
If one of these is missing when this skill needs it, stop and report which one and the task that creates it.
- docs/contracts/ and the contract register C1–C21 (arrive with F-03-T01, S0); docs/contracts/_TEMPLATE.md with it
- modules/<m>/registry.py module registration (arrives with F-03-T07, S1)
- backend/tests/contracts/ consumer contract tests (arrive with F-03-T18, S1)
- docs/product/status-vocabulary.yaml and its generated enums (arrive with F-03-T04, S0)
- the Brightwater Hale seed scenarios and `stub_from_seed` (arrive with F-04, S1–S3); until then stubs return `501 not_implemented`
- per-module matrix and flag files (`permission-matrix.d/`, `feature-flags.d/`) arrive with F-03's registry split; until then
  edit docs/architecture/permission-matrix.yaml and docs/architecture/feature-flags.yaml

Input: the contract a task needs: `<name> vN`, its screen IDs and artboard states, seed figures that must foot,
human-only gates and expected actions.

## 0. Preconditions — stop if one fails
- The need lists screen IDs and artboard states, seed figures that must foot, human-only gates and expected actions.
- Contract tests come first: write the consumer's contract tests in backend/tests/contracts/<name>/ from the screen
  contracts before the stub, then make the stub pass them.
- Search docs/product/decision-log.md and docs/plan/09-decisions-adrs.md for the screens and the module. An open
  decision is not a stop: decide it with the plan's proposed option, record it, and continue.
- The module is registered (modules/<m>/registry.py). If not, register it first in the same change.

## 1. Shape
- Path under /v1/<resource>; nouns from the glossary; one matrix action per route (`<entity>.<verb>`).
- Lists return {items, next_cursor, total, counts, facets}; cursors opaque; `total` null when the design shows none.
- Records carry server-computed `allowed_actions`; never role names.
- Errors: catalogue codes with identifier-only `facts`. External effects take an `Idempotency-Key`.
- Every field is `Annotated[..., classified(...)]`. Restricted fields never appear in list payloads; TINs never appear;
  walled records appear only as a count.
- Status fields use enums generated from status-vocabulary.yaml. A missing word: add the row to the vocabulary first.
- Agent-produced text is typed AgentTextValue or AgentBlocks. Human-only actions (sign off, approve, release, send, post)
  are separate operations whose matrix rows deny agent principals.

## 2. Stub
- Models and routes in the module (routes → service stub; no business logic). Each route returns seed-derived fixtures
  from scenarios/brightwater_hale (`stub_from_seed`) behind the flag; flag off → 404. Where no seed exists yet:
  `501 not_implemented`.
- Matrix rows and the flag (with an owner and an expiry of 90 days or less) in the same change.
- make regenerate (it runs make generate). Never edit openapi.json or *.gen.ts.
- docs/contracts/<name>.md from docs/contracts/_TEMPLATE.md: version, provider, consumers, screens and states, endpoints
  (action, flag, request, response), status words, human-only actions, audit events written, errors, examples, change log.

## 3. Verify
- The contract tests pass against the stub: `cd backend && uv run pytest tests/contracts/<name>`.
- make check.

## 4. Finish
Branch contract/<name>-vN; commit "contract: <name> vN (stub)"; merge once make check is green. Contract stubs and
migrations merge first in a sprint's batch. Append to the Progress log.

## Changing a contract
- Additive (new optional field, filter or facet): in place, with a change-log line.
- Breaking (removed or renamed field, narrowed type, changed meaning): a vN+1 beside vN for one sprint, recorded in
  the decision log; remove vN once every screen reads vN+1.

## Never
Weaken a contract test to fit the stub; put business logic in the stub; add a dependency without an allowlist entry;
grant an action to roles the need does not name; return a field no screen needs; put firm content in constants.
