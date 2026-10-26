---
id: ADR-186
title: Autonomy policy versions and Auto mode - a versioned, stricter-only firm AI policy published by the QM owner and approved by a second partner
status: accepted
date: 2026-10-26
deciders: ayushkbhatia   # solo edition (docs/plan/AMENDMENT-solo.md item 7): decided with the plan's proposed option, DEC-50 (b)
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
This is proposal **P-49** (chapter 09 §9.4.2; agent ADR AG-09), the record of **DEC-50 (b)**. The plan's chapters call it "ADR-148"; that number was a plan alias, and ADR-148 on `main` is P-28 (entitlements). The number here comes from `docs/adr/backlog.md`, drafted with G-02-T01 (TASK-1289).

ADR-061 gives each firm one autonomy level (0 advise, 1 routine, 2 manage, 3 portfolio), stored as `firms.autonomy_level` and changed by a firm admin with fresh MFA (`PUT /v1/firm/autonomy`, SPEC-024 AC-5, TASK-042). That is not enough for the firms Accrued serves:

- A peer reviewer, a cyber-insurer or the FTC asks for the firm's *written, versioned* AI policy and who approved it, not for a number in a settings row.
- The design (ADM-04) and chapter 05 §5.3.12 split policy by engagement type: Auto mode (a standing plan approval) may be acceptable for monthly closes and tax returns but not for an attest engagement.
- A quality-management owner (`quality_partner`, SQMS) owns the firm's methodology; a firm admin is an operator, not the person accountable for AI use on client work.
- A single editor can loosen the firm's controls alone.

Without a decision, G-02 (ADM-04), P-10 (the run planner's effective autonomy), K-02, P-07 (ENG-03 helper), N-02 and C-02 each read autonomy differently.

## Decision
1. **The AI policy is versioned.** A firm's AI policy is a sequence of insert-only versions ("BH AI policy vN") in `agents` (`autonomy_policy_versions`, one editable draft per firm in `autonomy_policy_drafts`). A version's content (`sections`, `schema_version`, `effective_from`) never changes after insert. States: `awaiting_approval` → `published` | `declined` | `withdrawn`; nothing leaves `published`. "Superseded" is derived for display (a later version is effective), never stored.
2. **Sections, v1.** `autonomy` (`level`, 0 to 1 in Season 1), `gates` (stricter-only overrides of the compiled gate catalogue; today only `policy_acceptance_on`, locked false under ADR-187), `policy_principal` (`on`, locked false), `auto_mode_defaults` per engagement type (C1 keys), `client_data` (`require_7216_consent` locked true, `consent_template_ref`, `disclosure_in_letters`, `client_drafts_enabled` locked false), `governance` (`install_role`, `publish_approver`, `override_tolerance_pct`, `accuracy_sample_n`, `trace_retention_years` ≥ 7). Later sections (`triggers_columns`, `kill_switch_roles`, `learned_context`) arrive as `schema_version` 2 in their own epics (K-04, K-05).
3. **Stricter-only.** Platform defaults are compiled from a protected YAML (`docs/architecture/ai-policy-defaults.yaml` → `agents/_ai_policy_defaults.py`, with a drift test). A draft that loosens any locked or default-strict cell answers **422 `policy_loosening_refused`** with the field path; no control offers a loosening. A gate's default human approver is never wider than the permission matrix allows (generated test).
4. **Who.** Every firm member reads the policy (`ai_policy.read`). The QM owner (`quality_partner`) drafts and **requests publication** with fresh MFA (`ai_policy.publish`); **a different partner approves** with fresh MFA (`ai_policy.approve`, `level_in(partner)`), enforced by the service (409 `approver_must_differ`) and by a database CHECK (requester ≠ approver on every row not carried over). `security_admin` may draft only the `client_data` section. `firm_admin` is read-only. Agents and the system are denied every policy write (I-AGENT-NEVER; ADR-005).
5. **Effective version.** `agents.api.effective_ai_policy(tenant, engagement_type, at)` returns the published version whose `effective_from` is the latest at or before `at` on `kernel.clock`. Runs read the version effective when they start.
6. **Auto mode.** "Auto mode on" for an engagement type means a standing plan approval for that type (accepted as level 2 for that type only). It is **stored** in v1 and **forced off for every real firm** until runtime v2 enforces it (P-10); on a real firm every Auto mode cell reads Off with a lock and the reason "Auto mode isn't available for client data yet". Managers and above toggle Auto mode per engagement within the policy (P-10).
7. **Cutover from ADR-061.** `firms.autonomy_level` is frozen as a fallback and legacy display. A migration (G-02-T23) gives every firm without a version a **v1 published, `carried_over = true`**, whose `autonomy.level` equals its current `firms.autonomy_level`, written by the system with `ai_policy.carried_over` (never attributed to a person). `identity.autonomy_level()` reads a provider the agents module registers, falling back to the frozen column capped at 1. With `ai_policy.v1` on for a firm, the legacy `PUT /v1/firm/autonomy` answers **409 `superseded_by_ai_policy`**; flag-off firms keep the legacy route and its tests until a superseding SPEC retires it.
8. **Immediate controls stay outside versioning.** The client-data opt-in (SPEC-036, firm admin, fresh MFA), each agent's shadow or live stage (read-only on ADM-04) and the per-firm "Pause all agents" (ADR-157's existing per-firm switch, now also `security_admin` and `quality_partner`; resume keeps fresh MFA) are displayed on ADM-04 but are not policy cells.

## Options considered
### Option A: versioned per-type policy, QM owner publishes, a second partner approves (DEC-50 b) - chosen
- Pros: answers "show me your written AI policy and who approved it"; per-type Auto mode; two people for any change; history and diffs for free.
- Cons: two sources of autonomy truth during cutover; more tables and a C13 approval gate.

### Option B: keep ADR-061's firm-wide level 0 to 3 (DEC-50 a)
- Pros: built; one number.
- Cons: no version history or approver; no per-type rule; one firm admin changes it alone.
- Why rejected: fails the governance outcome G-02 exists for (G-02 §1).

### Option C: per-engagement settings only
- Pros: flexible.
- Cons: no firm-level written policy; reviewers would inspect hundreds of rows.
- Why rejected: no single policy to show or approve.

## Consequences
**Positive**
- Every AI behaviour change is a numbered, two-person, attributable event ("AI policy v4 published by Margaret Okonkwo · approved by Daniel Reyes").
- Downstream epics read one effective-policy function.

**Negative / costs accepted**
- Cutover keeps `firms.autonomy_level` alive as a fallback (G-02 R10).
- A firm with one partner cannot publish a new version (it keeps its carried-over v1); recorded as accepted.

**Follow-up work created**
- G-02-T15 (contract stub), T22 (AC suite 3), T23 (migration, compiled defaults, validator), T24 (services, routes, C13 gate kind), T25 (ADM-04).
- A superseding SPEC that retires `PUT /v1/firm/autonomy` (TASK-042, SPEC-024 AC-5) once every live firm is on `ai_policy.v1`.

## Enforcement
- [x] Test: generated matrix tests deny `ai_policy.draft/publish/approve` to the agent, the system and every client principal (G-02-T02).
- [ ] Test: AC suite 3 (G-02-T22): stricter-only validator, `approver_must_differ`, effective-date resolution, real-firm Auto mode off.
- [ ] Database: insert-only versions, forward-only state trigger, requester ≠ approver CHECK, human-only actor CHECK on `decided_by` (G-02-T23).
- [ ] Hook or protected path: `docs/architecture/ai-policy-defaults.yaml` and its generated module are protected (G-02-T23).
- [ ] Reviewer agent checklist item: a policy cell that can be loosened, or a write path that skips the validator, is a defect.

## Guidance for agents
Read autonomy through `agents.api.effective_ai_policy` (or `identity.autonomy_level()` until T23 lands), never from `firms.autonomy_level` directly in new code. Never write a policy version outside the service, never let the requester approve, and never offer a control that loosens a locked cell.

**Do**
```
policy = await agents_api.effective_ai_policy(tenant_id, "tax_return", clock.now())
if not policy.auto_mode_defaults["tax_return"]: ...
```

**Don't**
```
row = await session.execute(text("SELECT autonomy_level FROM firms ..."))  # new code
```

## Revisit when
Runtime v2 enforces Auto mode (P-10); a pilot firm needs a single-partner publish path; or K-04/K-05 need `schema_version` 2.

## Related
- ADRs: ADR-005, ADR-061 (superseded for the level's home by this ADR), ADR-157, ADR-187 (P-08), ADR-147 (roles), ADR-167 (§7216 consent gate)
- Specs: SPEC-349 (firm governance v1), SPEC-036, SPEC-024 AC-5
- Docs: `docs/plan/09-decisions-adrs.md` DEC-50, P-49; `docs/plan/epics/G-02.md` §4.2, §4.4
