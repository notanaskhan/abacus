---
id: TASK-8365
title: A-09-T13 rest — the deterministic structure proposal (AUD-32 c; DV-2; AC-1.4)
spec: SPEC-658
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: s47r-a09-proposal
created: 2026-11-17
updated: 2026-11-17
---

## Objective
`POST /v1/audits/{wid}/consolidations/{cid}/structure/proposal` answered 501 naming A-09-T18. A-09-T18
merged in S47 (coverage route, the synthetic OneWorld connector, bulk upload and pull-all), so the
proposal is built: AUD-32 c, "Agent-proposed 3 tiers from the 5 OneWorld subsidiaries (suggestion;
Use structure · Edit); ownership 100%" (DV-2: deterministic, attributed Accrued Agent as a P-35
suggestion). Decided as DEC-5340.

## Plan (red: agents is PROTECTED)
1. **Hierarchy source (kernel slot).** `kernel/connection_coverage.py` gains `GroupHierarchy`
   (`(subsidiary, parent | None)` pairs), `register_group_hierarchy` and `group_hierarchy()`
   (NotFound `group_connector` unregistered). `connections/fake_oneworld.py` gains `PARENTS`
   (Holdings at the top; Operating and Real Estate under it; Manufacturing and Distribution under
   Operating: the Harlow & Pike slice's investment lines) and `hierarchy()`; `connections/api.py`
   registers it. Synthetic tenants only, as the pull (DV-1).
2. **Compute.** `assurance/compute/group_structure.py` (pure, 100% floor): subsidiaries matched to
   the client's entities by casefolded name (bulk upload's rule); the top matched subsidiary is
   level 1, each child one level below its parent; an unmatched subsidiary and everything under it
   are left out; a fourth tier refuses (`StructureTooDeep`); output ordered by level, then name.
3. **Agents (protected).** `agents/proposals.create_code_suggestion(tx, tenant_id, *, run_id,
   engagement_id, target_type, target_id, field_key, proposed_value)`: a P-35 suggestion attributed
   to a code run opened by `begin_code_run`, in the caller's unit of work (registered target, the
   field and value rules of `create_suggestion`, `suggestion.created` audit and event). And
   `code_run_output(tenant, suggestion_id)`: the suggestion's run and that run's identifier-only
   output. `agents/runs.py` labels `audit.group_structure` "Group structure".
4. **Assurance.** `assurance/group_structure.py`: `propose(ctx, work_item_id, consolidation_id)`
   (the route authorised `consolidation.edit`): a Draft consolidation with a OneWorld source (else
   409 `structure_source_missing`), at least one matched subsidiary (else 409
   `structure_source_missing`); one unit of work: the code run (one ToolCard
   `consolidation.read_subsidiaries`, a narration of counts), its output `{"entities": [[id,
   parent|null, level], ...]}` (identifiers only), and one suggestion on `consolidation` /
   `structure` whose value is `{"t": "text", "v": "<sha256 of the output>"}` (a field value is 200
   characters at most). Nothing is saved (AC-1.4). Applier `apply_structure_suggestion` (Use
   structure): reads the run output, checks the digest, authorises `consolidation.edit`, saves the
   structure through `ledger.save_structure` at the row's current version, and emits
   `ConsolidationStructureAdopted`; its subscription extends the source connection's coverage after
   commit (as the PUT does after its own commit). Edit is the PUT with the proposal prefilled.
5. **Route.** `group_propose_structure` calls `propose`.
6. **Organisations.** `api.client_entity_names(session, client_id)` (the repository's `entities_of`).
- **Tests:** unit `tests/unit/assurance/test_a09t13_structure_proposal.py` (compute rules, the
  tiers, depth refusal, the digest); integration `tests/integration/test_a09t13_structure_proposal.py`
  (5 subsidiaries → 3 tiers, nothing saved until adopt, the run attributed, adopt saves 5 entities at
  levels 1/2/3, a tampered output refused, no source → 409).
- **Rollback:** revert; no migration, no flag.

## Progress log
- 2026-11-17: planned (DEC-5340).
- 2026-11-17: built. Two findings while building, both in DEC-5340: (1) a P-35 field value holds
  200 characters, so the suggestion carries the run output's SHA-256; (2) adopt refused any
  suggestion without verified citations (`UncitedChange`), and a code-computed structure from a
  connector has no evidence to cite, so a suggestion `create_code_suggestion` made (rationale
  `CODE_RATIONALE`, `code#computed`, outside `_REF`, so the agent paths cannot write it) adopts
  as proposed without citations. Edited values are still refused here (Edit is the PUT). The
  database already refuses any update to a finished run's output.
- Gates: `make check-fast` green; `make generate` run. Tests: unit 19 (compute at 100% line and
  branch), integration 6; neighbours 2,352 (every suggestion adopt, A-09, OneWorld and coverage
  file) green; unit agents 1,156, assurance 1,050, connections 543, audit_trail 559 green.
  Local-only failures: WeasyPrint's `libgobject` (as S46/S47); `test_q03t235_audit_labels` fails
  on `confirmation_follow_up:platform` from S47's A-08 rows (main, not this change).
- Security review (red: agents): inline, as listed in the PR. No finding left open.
- 2026-11-17: Ayush kept the citation exemption for code-run suggestions (`code#computed`) as built.
- Not built: AUD-32's live screen wiring (fixture mode only, as before); a live OneWorld
  connector (DV-1).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5340 | The proposal's tiers come from the OneWorld parent of each subsidiary (the fake carries the slice's parents); the suggestion's value is a digest of its code run's identifier-only output, because a field value holds 200 characters | no |
