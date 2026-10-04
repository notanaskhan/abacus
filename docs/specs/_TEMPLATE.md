<!-- Location in repo: docs/specs/_TEMPLATE.md -->
<!-- Copy to docs/specs/SPEC-XXX-short-name.md -->

---
id: SPEC-XXX
title: <Feature name>
status: draft            # draft | approved | in-progress | done | superseded
owner: <name>
risk_zone: amber         # green | amber | red
related_adrs: []         # e.g. [ADR-004, ADR-007]
related_specs: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
<Two or three sentences: what this feature does and for whom.>

## 2. Problem and context
<Why this exists. Who has the pain. What happens today without it. Link the workflow step it serves.>

## 3. Actors
| Actor | Role in this feature |
|---|---|
| <e.g. Senior associate> | <what they do> |
| <e.g. Client controller> | |
| <e.g. System agent> | |

## 4. Goals and non-goals
**Goals**
- 

**Non-goals** — things a reasonable person might assume are included, but are not
- 

## 5. User stories and acceptance criteria
### Story 1: <As a … I want … so that …>
- **AC-1** Given <context>, when <action>, then <observable result>.
- **AC-2** Given …, when …, then …

### Story 2: …
- **AC-3** …

## 6. Behaviour and flows
**Happy path**
1. 

**Alternate paths**
- 

**State transitions** (if the feature changes an entity's state)
| From | Event | To | Who can trigger |
|---|---|---|---|
| | | | |

## 7. Domain and data changes
- **Entities affected:**
- **New or changed fields:** (name, type, nullable, default)
- **Invariants:** (rules that must always hold)
- **Migrations:** (reversible? backfill needed?)
- **Versioning and immutability:** (what must never be overwritten)
- **Retention:** (how long kept; deletion rules)

## 8. Interfaces
**API endpoints / module interfaces / events**
| Method / event | Path / name | Purpose | Auth required |
|---|---|---|---|
| | | | |

**Request and response schemas**
```
<schema or reference to shared type>
```

## 9. Authorisation and tenancy — REQUIRED (write N/A with reason if truly not applicable)
- **Tenant scoping:** how every read and write is restricted to the right firm
- **Who can do what:** roles and attributes required for each action
- **Engagement-level access:** who on which engagement
- **Ethical walls / independence constraints:**
- **Client-side access:** what a client user can see and do

## 10. AI behaviour — REQUIRED (write N/A if no model calls)
For each model call:
| Field | Value |
|---|---|
| Purpose | |
| Inputs and context sources | |
| Untrusted inputs (e.g. client documents) | |
| Output schema | |
| Model tier | small / medium / large |
| Cost budget | per call and per task |
| Autonomy | automatic / needs human approval |
| Failure and fallback | |
| Eval dataset and pass threshold | |
| Logged for reproducibility | model, prompt version, inputs, output |

## 11. Integrations
- **External systems:**
- **Rate limits and quotas:**
- **Retries and backoff:**
- **Idempotency:** (how duplicate runs are made safe)
- **Failure behaviour:** (what the user sees when the external system is down)

## 12. Edge cases and failure modes
List explicitly. Agents skip what isn't written down.
- 
- 

## 13. Security and privacy — REQUIRED
- **Data classification:** (public / internal / confidential / client financial data)
- **PII involved:**
- **Secrets used and where they live:**
- **Threats considered:** (including prompt injection via uploaded content)
- **Mitigations:**

## 14. Audit trail and evidence integrity — REQUIRED
- **Actions logged:** (who, what, when, source)
- **Provenance captured:**
- **What must be immutable:**

## 15. Observability
- **Logs:** (never log client financial data or PII)
- **Metrics:**
- **Traces:**
- **Alerts:**

## 16. Performance and scale
- **Expected volumes:** (e.g. rows per engagement, documents per request)
- **Latency targets:**
- **Limits and pagination:**

## 17. UX
- **Screens and components:** (from the design system)
- **States:** empty / loading / partial / error / success
- **Copy and messaging:**
- **Accessibility:**

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 | unit / integration / e2e / eval | |
| AC-2 | | |

## 19. Rollout
- **Feature flag:**
- **Migration and backfill plan:**
- **Rollback plan:**

## 20. Open questions
Must be empty before status is `approved`.
- [ ] 

## 21. Future / explicitly deferred
- 
