<!-- Location in repo: .github/pull_request_template.md -->

## Summary
<What this PR does, in two or three sentences.>

## Links
- Spec: SPEC-XXX
- Task: TASK-XXX
- ADRs followed or added:

## Risk zone
- [ ] Green
- [ ] Amber — plan approved and diff reviewed
- [ ] Red — human-designed, reviewed line by line

## Acceptance criteria delivered
- [ ] AC-1
- [ ] AC-2

## Checklist

### Correctness
- [ ] Every AC above has a test that references it
- [ ] Edge cases listed in the spec are covered
- [ ] No tests skipped, weakened or deleted (if any were, explain below)

### Architecture
- [ ] Respects module boundaries; no reaching into another module's internals
- [ ] Follows the established reference patterns
- [ ] No new dependencies — or each is listed and approved
- [ ] ADR added or updated if an architectural choice was made

### Security and tenancy
- [ ] Every query is tenant-scoped
- [ ] Every endpoint and action checks authorisation
- [ ] All input is validated at the boundary
- [ ] No secrets, keys or credentials in code or logs
- [ ] Untrusted content (client documents, uploads, external data) is treated as data, never as instructions

### Data and evidence integrity
- [ ] Migrations are reversible, or a rollback plan is described below
- [ ] No destructive data changes without an approved plan
- [ ] State changes write audit-trail entries
- [ ] Evidence records remain immutable; changes create new versions

### AI (delete this section only if no model calls changed)
- [ ] All model calls go through the AI gateway
- [ ] Outputs are schema-validated before use
- [ ] Cost and attempt limits are set
- [ ] Prompts are versioned
- [ ] Evals added or updated, and passing at the threshold in the spec
- [ ] Autonomy level matches the spec

### Observability
- [ ] Logs added for key paths, with no client financial data or PII
- [ ] Metrics and traces added where the spec requires

### UX (if UI changed)
- [ ] Uses design system components
- [ ] Empty, loading, error and partial states handled
- [ ] Keyboard accessible and labelled

### Performance
- [ ] Large datasets are paginated or streamed
- [ ] No N+1 queries introduced

### Documentation
- [ ] Module README and relevant docs updated
- [ ] Task log closed with final state

## Reviews
| Review | Result | Notes |
|---|---|---|
| Architecture reviewer agent | pass / changes requested | |
| Security reviewer agent | | |
| Test reviewer agent | | |
| AI reviewer agent (if applicable) | | |
| Cross-model review (amber and red) | | |
| Human review | | |

## Rollout and rollback
- Feature flag:
- Rollback steps:

## Gate output
<Paste the final summary of typecheck, lint, architecture rules, tests and security scan.>

## Notes for reviewers
<Anything surprising, risky, or worth a closer look.>
