---
id: ADR-064
title: Living AI threat model; all client-system strings are untrusted
status: accepted
date: 2026-10-04
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Agents read content from clients and their systems and can act. Injection can arrive through uploads, emails, and ordinary ledger fields such as vendor names and journal memos.

## Decision
An AI threat model is maintained at `docs/architecture/ai-threat-model.md` and reviewed whenever an agent, tool or data source is added. Every string originating from a client or client system — uploads, emails, ledger fields, vendor and customer names, memos, descriptions — is treated as untrusted data by context builders.

## Options considered
### Living model, broad untrusted boundary — chosen
- Pros: Catches injection via overlooked channels
- Cons: More wrapping in context builders
- Chosen.

### Only uploads treated as untrusted
- Pros: Less work
- Cons: Ledger fields become an injection channel
- Rejected.

## Consequences
**Positive**
- Injection surface is understood and tracked

**Negative / costs accepted**
- Ongoing maintenance

**Follow-up work**
- Initial threat model document

## Enforcement
- Connector-sourced fields are typed as `Untrusted[str]`; context builders accept them only inside untrusted blocks
- PR checklist requires a threat-model update when adding agents, tools or sources

## Guidance for agents
Pass connector strings through as untrusted values.

**Do**
```python
inputs = {'memo': Untrusted(entry.memo)}
```

**Don't**
```python
prompt += f'Memo: {entry.memo}'
```

## Amendment: link principals on the public confirmation page (accepted 2026-11-15; A-08-T02, DEC-5029, DEC-5052)
**Status of this amendment: accepted** on 2026-11-15 by ayushkbhatia (DEC-5052), with the ADR-152 amendment. POR-17 is the first surface a stranger can call. The repository has no separate threat-model file under `docs/architecture` for principals, so the link-principal threats live here beside the AI threats (A-08 §0.1).

| Threat | How it happens | Controls |
|---|---|---|
| Enumeration | Guessing tokens or probing which links exist, are expired or answered | 256-bit random tokens stored hashed; one definer resolver; identical status, body and padded timing for unknown, expired, revoked and kill-switched tokens (DV-7); WAF rule 6; no token in logs or query strings |
| Phishing | A fake "confirmation" email that copies the firm's | Firm DKIM sender and letterhead (ADR-163); the email and the expired page tell the respondent to call the firm on an independently found number, never the number in the email; no payment language; the link works once |
| Brute force (codes) | Guessing the six-digit email code | 10-minute codes hashed at rest; five wrong codes lock for 15 minutes; 30 code requests per 5 minutes per IP at the edge; padded 202 for any address |
| Hostile upload | A respondent attachment carrying malware, macros or prompt text | Evidence uploads with the scanner failing closed (ADR-153), write-once versions, isolated parse, formulas never evaluated; respondent text and attachments are `respondent_text` untrusted input to `confirmation_reconcile`, whose proposals a manager alone accepts (containment eval 1.0) |
| Scope escape | Using a link to read other customers, the engagement or portal data | `link_scope_only`: one object per link principal; render data for that confirmation only; client principals 404 on every confirmation route (I-CONFIRMATION-ISOLATION) |
| Replay | Resubmitting or changing an answer | Insert-only response; the link is consumed; 409 `already_answered` with the original receipt |

## Revisit when
Never expected to change.

## Related
- ADR-052
- ADR-065
