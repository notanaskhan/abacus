---
id: TASK-026
title: Feature flag registry with per-firm enablement
spec: SPEC-011
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: amber
status: awaiting-plan-approval
branch: task-026-feature-flags
worktree:
created: 2026-10-07
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-011 (approved, Q1–Q5): the flag registry and its codegen, per-firm state, `flag()`, the operator CLI, the CI checks (expiry and FLAG-001), and prompt-variant flags in the gateway.

## Scope
All of SPEC-011. Excluded: percentage rollouts, a UI, and SPA flags.

## Context to load
- Spec: `docs/specs/SPEC-011-feature-flags.md`
- ADRs: ADR-089, ADR-007, ADR-014
- Code: `abacus_tools/codegen/permission_matrix.py` (pattern), `kernel/` (db, uow), `ai_gateway/__init__.py` (`_call`, prompt lookup), `abacus_tools/quality/banned_patterns.py`

## Plan
- [ ] Plan approved by human

### Design (for founder review)
1. **The registry:**
   - `docs/architecture/feature-flags.yaml` holds a list of flags: `name`, `description`, `owner`, `created`, `expires`, `kind` (`boolean` or `variant`), `values` (for variants) and `default`.
   - It starts with `prompt.evidence.screener` (variant `[evidence.screen@v0]`, default `evidence.screen@v0`).
   - `abacus_tools/codegen/feature_flags.py` validates the registry (AC-6) and writes `kernel/_flags.py`: one constant per flag (`PROMPT_EVIDENCE_SCREENER = Flag(...)`) and `FLAGS`. With `--check`, CI checks it is current.
2. **The expiry check** (AC-4): the codegen's `--check` also fails on a flag past `expires`, naming the flag and its owner. It is added to `make check-fast`.
3. **`kernel/flags.py`:**
   - `flag(tenant, f: Flag) -> bool | str` takes the constant, not a string (AC-5 by typing);
   - reads `feature_flag_states` in `tenant_session` and caches each (tenant, flag) for 30 seconds;
   - on any error returns `f.default` and logs `flag.read_failed`;
   - a stored value no longer valid for the flag (a variant removed) falls back to the default.
4. **FLAG-001** (`banned_patterns`): `Flag(` may be constructed only in `kernel/_flags.py`, and `flag()` must be called with a `_flags` constant (a name, not a call or a string).
5. **Migration 0022:** `feature_flag_states`, as in §7 of the spec, with forced RLS, insert columns, and UPDATE on `value`, `set_by`, `reason` and `set_at`. It is kernel-owned in the schema maps.
6. **The operator CLI** (`abacus_tools/flags.py`, `make flag FIRM= FLAG= VALUE= OPERATOR= REASON=`):
   - checks the flag and value against the registry;
   - upserts in a unit of work under `TenantContext(firm, "system", "operator:<name>")`;
   - audits `feature_flag.set`, with the old and new values as SHA-256 fingerprints (audit references can't carry text) and the flag's registry position;
   - uses the app database URL from settings.
7. **Prompt variants** (AC-7, AC-8), in `ai_gateway._check` and `_call`:
   - if the generated registry has a flag `prompt.<agent_id>`, read it;
   - when it differs from the call's prompt, use it only if it is registered (`prompt()`) and, outside synthetic environments, eligible on the admitted route (the eligibility check is passed the variant's prompt version);
   - otherwise use the call's prompt and log and count `flag.variant_rejected`;
   - the usage record's `prompt_version` is the one used.

   This lives in `ai_gateway`, which reads flags through `kernel.flags` (the kernel never imports modules).

**Protected paths (approval file):**
- `docs/architecture/feature-flags.yaml` (new);
- `backend/src/abacus/kernel/**` and `backend/src/abacus/ai_gateway/**`;
- `backend/migrations/**`;
- `backend/src/abacus_tools/**` and `backend/tests/unit/**` (pins);
- `Makefile`.

### Questions for approval
- **D1. Expiry is checked by the codegen's `--check` in `check-fast`, not as a separate tool?** *Recommendation: yes.* One place validates the registry.
- **D2. Audit references for flag values are SHA-256 fingerprints of the old and new values (the audit `Ref` refuses free text); the operator's name is in the actor ID and the reason is stored on the row?** *Recommendation: yes.*
- **D3. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-07` — SPEC-011 approved and merged (#46). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Questions for the human
- Design questions D1–D3 (above).

## Handoff
