---
id: ADR-167
title: TRI, phi and pii_kind field flags beside the four classification levels; the gateway refuses TIN patterns in model context; the shape of the section 7216 consent gate
status: accepted
date: 2026-10-23
deciders: notanaskhan, ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.
> - **Accepted 2026-10-24.** Q-02-T32 (classification flags and the gateway refusal) may start. Counsel's OQ-1 is still open; it governs only the consent text's disclosed recipient (§3, built by T-01 as C19), not the flags or the gateway refusal.

## Status and acceptance

Drafted by Q-02-T25 (P-12, DEC-52). Acceptance needs three things, recorded in this file when they happen:
1. notanaskhan accepts;
2. ayushkbhatia accepts;
3. counsel names the recipient that the consent text discloses for model inference (open question OQ-1).

**Acceptance record:**
- 2026-10-24: ayushkbhatia accepted, in the build session. Under `docs/plan/AMENDMENT-solo.md` (one builder; no approvals to wait for), that is the deciders' acceptance; notanaskhan's separate sign-off is not required.
- Counsel's OQ-1 (the recipient the consent text discloses for model inference) is **still open**. Accepting does not answer it. OQ-1 governs only the consent text, which is counsel's and loads as database content when T-01 builds C19 (S17). §1 (the flags) and §2 (the gateway TIN refusal) do not depend on it, so they are binding now. When counsel answers, the answer is recorded here (counsel's conclusion only, never their advice) without changing §1–§3.

The plan's due date was Fri Jan 22, 2027 (Q-02 table 0.1, end of S6). This ADR records engineering shapes only. It gives no legal advice and quotes no counsel. The consent text, and whether a given use needs a consent, are counsel's. Engineering loads the text as database content and does not interpret it.

## Context

ADR-031 classifies every model field as Restricted, Confidential, Internal or Public, and logging, error tracking, exports and the AI gateway read that one tag. Three things it cannot yet express are needed before the tax pilot and before any real firm's data reaches a model:

- **Tax return information (TRI).** Tax work needs per-taxpayer consent before TRI is used or disclosed, including to a model provider (DEC-52). The gateway must be able to tell which context fields are TRI.
- **Kinds of personal identifier.** A taxpayer identification number (SSN, ITIN or EIN), a bank account number and a date of birth each need their own masking and their own reveal rule (offshore users never see a full SSN, DEC-52). A single "Restricted" tag says the value is sensitive, not what it is.
- **Health information.** Benefit-plan and some client records can carry it. It needs the same "which fields" answer.

The plan recorded a conflict (C-02, compliance digest). The compliance digest asked for a TRI classification level, but ADR-031 has four levels that every consumer orders and compares. DEC-52 settled it: a TRI class expressed as flags beside the four levels, not a fifth level.

Three planned pieces depend on this shape:
- Q-02-T32 (S7) builds the flags and the gateway refusal.
- Q-02-T52 (S8) tests them independently (ADR-078).
- T-01 builds the consent gate as contract C19, frozen in S17.

The C19 shape has to be fixed now, so that the flags carry what the gate will need and no consumer builds a private consent check meanwhile.

P-03's masked agent material (P-03-T15) is the main control that keeps identifiers out of model context. This ADR adds a backstop at the gateway.

## Decision

### 1. Three flags beside the four levels (C-02)

ADR-031's four levels stay as they are; this ADR extends ADR-031 and does not supersede it. `classified()` gains three optional keyword flags:

```python
classified(level, *, tri: bool = False, phi: bool = False, pii_kind: PiiKind | None = None)
```

- `tri=True`: the field holds tax return information.
- `phi=True`: the field holds health information.
- `pii_kind`: the kind of personal identifier the field holds. The initial members are `tin` (SSN, ITIN or EIN), `bank_account` and `date_of_birth`. Adding a member is additive: a new member, its mask, and a test that the scrubbing removes it.
- **Any flag forces Restricted.** A flag on a field whose level is not `restricted` fails at import (Q-02 AC-19). There is no "Confidential TRI".
- The flags are written into the field's JSON schema next to the level (`x-classification`, plus `x-tri`, `x-phi` and `x-pii-kind`). The OpenAPI document and the generated client therefore carry them.
- `tri_paths(model)` and `pii_paths(model, kind)` return the dotted paths of flagged fields, nested models included. Logging, Sentry, metrics, exports, the access-events writer and the gateway read these. No consumer keeps its own list of field names.
- `mask(value, kind)` is the one masking function. For `tin` it keeps the last four digits only (`tin_last4`, DEC-52). Full TINs are sealed (encrypted at rest under the tenant key) and revealed only by a logged `tin.reveal` with a reason. The matrix refuses that action to offshore members (`not_offshore`).
- Restricted values are already never logged (ADR-031). The flags add that a value masked for display is masked by its kind, and that an export or trace view can name what it withheld without showing it.

### 2. The gateway refuses TIN patterns in model context

- Before any network call, `ai_gateway` scans the fully assembled context for SSN, ITIN and EIN patterns: every text part, the task JSON, and the untrusted blocks.
- A match counts only if it passes that number type's published validity rules. Those rules are code in the gateway, with tests, and are not restated here.
- Masked forms pass: fewer than nine digits shown, or the last-four form `mask()` produces.
- A match refuses the call with a new boundary reason, `pii_in_context`, beside ADR-115's reasons:
  - it is audited as `ai.boundary_refused` with the reason and the context part's name, never the value;
  - it is never retried and never rerouted;
  - the run ends in the existing degraded state, and a person carries on.
- False positives are accepted. A nine-digit account number that happens to pass the rules is refused too. Failing closed is the point of a backstop. A refusal is a defect report against the context builder that let the value through, not a reason to loosen the scanner.
- The refusal applies on every route (fake, direct, Bedrock) and in every environment, so tests and evaluations exercise it.

### 3. The shape of the consent gate (built by T-01 as C19)

This ADR fixes the shape. T-01 builds it, and C19 freezes it in S17.

- **Matrix condition `consent(<purpose>)`.** An action that reads or uses TRI declares a consent condition in the permission matrix. Consent-check providers are registered through `register_consent_check` (F-03-T08). Purposes are a closed list held with the consent registry (at least the use purpose and the disclosure purpose DEC-52 names).
- **Gateway condition 6.** When an assembled context includes a TRI-flagged field (from `tri_paths`), the call carries its data subjects (the taxpayers). The gateway calls `organisations.api.tri_consent_verdict(tenant, subjects, at)`, which returns `Verdict(valid, missing)`. The call is refused with reason `consent_7216` before any network call unless every subject holds a valid consent for every required purpose at `at`. On a joint return the subjects are both spouses. The refusal is audited and never retried.
- **The tool layer refuses too.** Any agent read of TRI goes through `organisations.api.require_tri_consent(ctx, subjects)`, which raises `consent_required` and names the client. Every allowed read writes an `access_events` row with the consent set as a dimension. The gateway check is the second line, not the only one.
- **Agents-off path.** A taxpayer without a valid consent gets the same work without the agent: the work item shows that AI is off for that client, and nothing is queued to retry when a consent arrives.
- **Recipients come from the registers, never typed.** The recipients a consent discloses are generated from the provider-terms register (ADR-114) and the sub-processor register (ADR-154). For model inference the register's party is "Amazon Web Services (Bedrock)", not the model vendor's name (DEC-52), subject to OQ-1. A change to the register's recipients makes existing consents need renewal. This is the same rule as SPEC-036's re-opt-in on a material register change.
- **Consent text is database content.** It is counsel-approved, versioned, and loaded through the consent registry's import path. It is never a constant, seed or migration (AGENTS.md rule 16).

### 4. Open questions for acceptance

| # | Question | Who answers | Needed by |
|---|---|---|---|
| OQ-1 | Counsel confirms the recipient that the consent text names for model inference, as generated from the register: "Amazon Web Services (Bedrock)". Q-02-T25's acceptance requires this naming to be recorded here | counsel, through F-09-T38/T47; recorded by a founder | Fri Jan 22, 2027 |
| OQ-2 | Which v1 models carry `phi` at all. Benefit-plan audits are the likely first. If none do in v1, the flag ships unused, with its test | notanaskhan | before Q-02-T32 starts (S7) |
| OQ-3 | The initial `pii_kind` members beyond `tin`. `bank_account` and `date_of_birth` are proposed; any other kind waits for a field that needs it | notanaskhan | before Q-02-T32 starts (S7) |

## Options considered

### Option A: four levels plus `tri`, `phi` and `pii_kind` flags that force Restricted (chosen)
- Pros:
  - every existing consumer of the level keeps working;
  - "TRI is always Restricted" is enforced, not a convention;
  - masking, reveal and the gateway get the precision they need from one declaration on the field.
- Cons: two things to read per field (level and flags); consumers must use the path helpers, not the level alone.

### Option B: a fifth level, TRI
- Pros: one tag per field.
- Cons:
  - every consumer that orders or compares levels changes;
  - TRI is a subset of Restricted, and as a level it would sit beside it, not under it;
  - it says nothing about identifier kind or health data, so flags would still be needed.
- Why rejected: conflict C-02, settled by DEC-52.

### Option C: a separate register of TRI and PII fields outside the models
- Pros: no change to `classified()`.
- Cons: the register drifts from the models, and a new field is unprotected until someone remembers the register.
- Why rejected: ADR-031's point is that the tag lives on the field.

### Option D: rely on masked context alone, with no gateway pattern check
- Pros: no false-positive refusals.
- Cons: one missed path in a context builder sends an identifier to a provider.
- Why rejected: a sealed identifier must have a second line at the one place every model call passes through.

## Consequences

**Positive**
- The gateway, logs, Sentry, exports and access events answer "which fields are TRI, health data or a TIN" from one declaration.
- An unmasked TIN cannot reach any model provider, even through a context-builder bug.
- T-01 builds C19 against a fixed shape, and no consumer writes its own consent check in the meantime.

**Negative / costs accepted**
- False-positive refusals on nine-digit values that pass the validity rules. The run degrades and a person proceeds.
- One more boundary reason (`pii_in_context`) for the gateway and its error copy.
- Consent renewal when a register recipient changes is operational load for firms.

**Follow-up work created**
- Q-02-T32 (S7): the flags, `tri_paths`, `pii_paths`, `mask`, scrubbing by tag, the classification-tag check extended, and the `pii_in_context` refusal.
- Q-02-T52 (S8): independent AC tests for AC-19 to AC-22.
- T-01 (S17, C19): the `consent(<purpose>)` condition, providers, `tri_consent_verdict`, `require_tri_consent`, `consent_state`, the `consent_7216` reason, the registry and capture routes, and `docs/contracts/c19-consent-gate.md`.
- F-09: counsel's answer to OQ-1 and the consent text.

## Enforcement
- [ ] Test (Q-02 AC-19): a `tri`, `phi` or `pii_kind` flag on a non-Restricted field fails at import; `pii_paths(model, "tin")` finds a nested flagged field; the JSON schema carries the flags.
- [ ] Test (Q-02 AC-20, AC-21): a tagged value never appears in a log line, Sentry event or metric attribute in the scrubbing test.
- [ ] Test (Q-02 AC-22): a context holding an unmasked SSN that passes the validity rules is refused with `pii_in_context` before the network stub is called, audited, and not retried; a masked form passes.
- [ ] Test (C19, T-01): a TRI context without both consents for a joint return is refused with `consent_7216`; the tool-layer read raises `consent_required`.
- [ ] Architecture rule in CI: the classification-tag check accepts the flags only through `classified()`; no consumer reads field names for TRI or PII outside the path helpers.
- [ ] Reviewer agent checklist item: no consent text, recipient name or legal reasoning in code; recipients come from the registers.

## Guidance for agents
Until this ADR is accepted, do not add the flags or the refusal. Q-02-T32 waits. Today, keep tagging identifiers `restricted` and keep them out of model context through P-03's masked material. After acceptance, declare what a field is where it is defined, and let the helpers find it.

**Do**
```python
taxpayer_tin: Annotated[str, classified("restricted", tri=True, pii_kind="tin")]
paths = pii_paths(TaxpayerOut, "tin")          # consumers ask the model, never a list of names
```

**Don't**
```python
taxpayer_tin: Annotated[str, classified("confidential", pii_kind="tin")]   # a flag forces restricted
TRI_FIELDS = {"taxpayer_tin", "agi"}                                        # a private list drifts
consent_text = "I consent to disclosure to ..."                             # counsel's text is database content
```

## Revisit when
- Counsel's answer to OQ-1 differs from the register's party name.
- A provider other than Bedrock is proposed for client data (ADR-113).
- The false-positive refusal rate on staging exceeds what the canary and pilot can absorb.
- A new kind of regulated data (beyond TRI, health data and identifiers) enters scope.

## Related
- P-ID: P-12 (DEC-52, AG-16; conflicts C-01 to C-03). Drafted by Q-02-T25.
- ADRs: ADR-031 (data classification, extended here), ADR-113 (Bedrock for client data), ADR-114 (provider terms register), ADR-115 (data boundary for real firms; its reasons gain `pii_in_context` and, with C19, `consent_7216`), ADR-154 (sub-processor register), ADR-078 (independent tests).
- Specs and contracts: SPEC-036; Q-02 AC-19 to AC-22; C19 (`docs/contracts/README.md`, T-01, freeze S17).
- Docs: `docs/plan/09-decisions-adrs.md` DEC-52 and P-12; `docs/plan/epics/Q-02.md` table 0.1, T25, T32, T52; `docs/plan/epics/T-01.md` §1 item 3 and story 2.2.
