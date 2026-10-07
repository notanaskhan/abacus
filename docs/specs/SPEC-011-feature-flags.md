---
id: SPEC-011
title: Feature flag registry with per-firm enablement
status: draft
owner: founder
risk_zone: amber
related_adrs: [ADR-089, ADR-007, ADR-014, ADR-019, ADR-073]
related_specs: [SPEC-005, SPEC-010]
created: 2026-10-07
updated: 2026-10-07
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
ADR-089 says new behaviour ships behind feature flags enabled per firm, and model and prompt rollouts use the same mechanism. This spec adds:
- **A registry:** one reviewed file of flags, each with an owner, an expiry and a default.
- **Per-firm state:** a firm's flag settings, set by platform operators and audited.
- **One read function:** `flag(tenant, name)` for code.
- **CI checks:** they fail on expired flags and on names that aren't registered.

Prompt rollouts use variant flags, which the gateway honours only for registered, eligible prompt versions.

## 2. Problem and context
- **Today:** every merged change is live for every firm at once. A risky change (a new prompt version, a new agent behaviour) can't be staged per firm or switched off without a deploy.
- **What we need:**
  - shadow-before-live (build plan principle 7) needs per-firm enablement;
  - Phase 2 increments ship behind flags to the canary firm first (ADR-094).
- **What to avoid:** flag sprawl, prevented by an owner and an expiry on every flag.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engineers and agents | Declare flags in the registry; read them through `flag()` |
| Platform operators | Turn flags on or off per firm (Q2) |
| CI | Fails on expired or unregistered flags |
| `ai_gateway` | Reads prompt-variant flags (Q3) |

## 4. Goals and non-goals
**Goals**
- **The registry (Q1):** `docs/architecture/feature-flags.yaml`, a protected file. Each flag has:
  - `name`, `description`, `owner`, `created` and `expires` (at most 90 days after `created`, Q4);
  - `kind`: `boolean`, or `variant` with its allowed values;
  - `default`.

  A codegen step (`abacus_tools.codegen.feature_flags`) writes a typed module, and CI checks that it is current.
- **Per-firm state:** `feature_flag_states` (tenant-scoped, forced RLS) holds a firm's value for a flag. Setting one is audited (`feature_flag.set`).
- **Reading:** `kernel.flags.flag(tenant, name)` returns the firm's value or the default. It is cached per process for 30 seconds (Q5). It fails safe: on any read error it returns the default, which is off.
- **CI:**
  - an expired flag (today after `expires`) fails `make check-fast` until it is removed from the registry and the code;
  - a flag name in code that isn't in the registry fails lint (FLAG-001: names are literals from the generated module).
- **Prompt rollouts (Q3):** a `variant` flag named `prompt.<agent_id>` picks the agent's prompt version for that firm. The gateway uses it only if the prompt is registered and, outside synthetic environments, eligible on its route (SPEC-005, SPEC-010). Otherwise it uses the spec's prompt and logs `flag.variant_rejected`.

**Non-goals**
- Percentage rollouts and user-level targeting.
- A flag UI. Operators use a CLI (Q2).
- Flags in the SPA. The SPA reads behaviour from the API.
- Model-route rollouts, which `model_routes` and parity settings already control (SPEC-010).

## 5. User stories and acceptance criteria
### Story 1: Ship dark, enable per firm
- **AC-1** Given a registered boolean flag with default `false`, when code calls `flag(tenant, name)` for a firm with no state, then it returns `false`. For a firm whose state is `true`, it returns `true` within 30 seconds of the change.
- **AC-2** Given a flag read fails (the database is unreachable), then `flag()` returns the registry default and logs `flag.read_failed` (identifiers only). It never raises into the caller.
- **AC-3** Given an operator runs `make flag FIRM=<tenant_id> FLAG=<name> VALUE=<value> REASON=<text>`, then the firm's state is set in one unit of work:
  - `feature_flag.set` is audited with the operator's name, the flag, and the old and new values (as a fingerprint for variants);
  - an unknown flag, or a value not in the variant's list, is refused.

### Story 2: No sprawl
- **AC-4** Given a flag whose `expires` date is past, then `make check-fast` fails, naming the flag and its owner.
- **AC-5** Given code that reads a flag not in the registry, or reads one by a computed name, then lint fails (FLAG-001).
- **AC-6** Given the registry, then every entry has an owner, a description, `expires` no more than 90 days after `created`, and a default that is valid for its kind. Validation runs in codegen and in CI.

### Story 3: Prompt rollouts use flags
- **AC-7** Given `prompt.evidence.screener` set to `evidence.screen@v1` for one firm, and that prompt is registered (and eligible on its route outside synthetic environments), then that firm's screening calls use `@v1` and every other firm stays on the spec's prompt. Usage records show the prompt version actually used.
- **AC-8** Given the variant names an unregistered or ineligible prompt, then the call uses the spec's prompt, and `flag.variant_rejected` is logged and counted.

## 6. Behaviour and flows
1. **Declare:** an engineer adds a flag to the registry (protected; the founder approves) and runs codegen. Code reads it through the generated constant.
2. **Enable:** an operator enables it for the canary firm, then for others. Each change is audited.
3. **Remove:** before `expires`, the flag is removed from the registry and the code, keeping the chosen behaviour. Its stored states are left in place; they are inert once the flag is unregistered.

## 7. Domain and data changes
- **`feature_flag_states`:**
  - columns: `tenant_id`, `flag`, `value` (text: `true`, `false` or a variant), `set_by` (operator name), `reason`, `set_at`;
  - primary key (`tenant_id`, `flag`);
  - tenant-scoped with forced RLS;
  - the app may insert, and update `value`, `set_by`, `reason` and `set_at`.
- **The registry file** and the generated `kernel/_flags.py`.

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `kernel.flags.flag(tenant, FLAG) -> bool \| str` | Read (AC-1, AC-2) |
| `make flag …` (`abacus_tools.flags`) | Set per firm (AC-3) |
| `python -m abacus_tools.codegen.feature_flags [--check]` | Generate and validate (AC-6) |
| FLAG-001 (banned_patterns) and the expiry check | CI (AC-4, AC-5) |

No HTTP routes.

## 9. Authorisation and tenancy
- **Who sets flags:** platform operators only (Q2). Firm users can't see or set flags, and there is no matrix action.
- **How the CLI writes:** in the firm's tenant context with actor kind `system` and the actor ID `operator:<name>`, through the unit of work.
- **Tenancy:** reads are tenant-scoped (RLS).

## 10. AI behaviour
Prompt-variant flags (AC-7, AC-8) are bounded by the prompt registry and evaluation eligibility. A flag can never introduce an unevaluated prompt outside synthetic environments.

## 11. Integrations
None.

## 12. Edge cases and failure modes
- **A flag is removed from the registry while firms still have state:** reads of it no longer compile (FLAG-001), and the stale rows are ignored.
- **The cache delays a change by up to 30 seconds.** An urgent kill switch takes effect within that time.
- **The variant's prompt is retired later:** AC-8 applies, and the call falls back to the spec's prompt.

## 13. Security and privacy
- **Classification:** flag states are internal. The `reason` is free text written by operators, so it is never logged and is shown only in the audit trail.
- **Changes are audited:** every change records who made it and why.

## 14. Audit trail and evidence integrity
`feature_flag.set` (the flag, the firm, the old and new value, the operator and the reason) is audited.

## 15. Observability
- **Metrics:** flag reads by flag and value (sampled), `flag.read_failed` and `flag.variant_rejected`.
- **Logs:** identifiers only.

## 16. Performance and scale
One cached read per flag per firm per 30 seconds per process.

## 17. UX
None.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1, AC-2 | unit + integration | Default, firm value, cache expiry, fail-safe |
| AC-3 | integration | CLI sets and audits; unknown flag or value refused |
| AC-4 to AC-6 | unit | Expiry check, FLAG-001, registry validation |
| AC-7, AC-8 | unit + integration | The variant prompt is used only when registered and eligible |

## 19. Rollout
The migration is additive. The registry starts with one flag, `prompt.evidence.screener` (variant, default `evidence.screen@v0`), to prove the mechanism.

## 20. Open questions
- [ ] **Q1: where the registry lives.** *Recommendation:* `docs/architecture/feature-flags.yaml` (protected, reviewed like the permission matrix), with a generated `kernel/_flags.py` checked in CI.
- [ ] **Q2: who sets flags, and how.** *Recommendation:* platform operators through `make flag` (a CLI in `abacus_tools`, run with the app database credentials in the firm's tenant context), audited with the operator's name and a reason. There is no firm self-service and no UI in v1.
- [ ] **Q3: prompt rollouts.** *Recommendation:* `variant` flags named `prompt.<agent_id>`, honoured only for registered prompts that are eligible on the call's route (synthetic environments: registered only). Model choice stays with the catalog and routes (SPEC-010).
- [ ] **Q4: expiry policy.** *Recommendation:* at most 90 days from `created`. Expiry fails `check-fast`. Extending means a new `expires` in a reviewed change, still within 90 days of a new `created`, so each extension is a deliberate decision.
- [ ] **Q5: cache and failure.** *Recommendation:* a 30-second per-process cache. On a read error, return the registry default (off for booleans). Flags must be written so that the default is the safe behaviour.

## 21. Future / explicitly deferred
- Percentage and user-level rollouts.
- A flag page for operators.
- Firm self-service flags.
- Flag usage analytics.
