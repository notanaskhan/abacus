---
id: SPEC-006
title: Output controls and the outbound message scope checker
status: draft
owner: founder
risk_zone: red
related_adrs: [ADR-065, ADR-052, ADR-064, ADR-005, ADR-007, ADR-031]
related_specs: [SPEC-000, SPEC-004]
created: 2026-10-07
updated: 2026-10-07
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Agent output must never leak data (ADR-065). Two controls finish the Trust layer of Phase 1 §5.3:
- **Output controls:** model text is shown as sanitised plain text only, and external links are stripped unless allowlisted.
- **The outbound message scope checker:** every message that leaves the platform passes a guarded send path. That path blocks and flags any client, entity, account or amount outside the engagement's scope.

## 2. Problem and context
Agents already write text that people see: screening rationales, quotes and unverified points. Phase 2 adds messages to clients: drafted follow-ups (increment 8) and invitations (increment 2).
- **What exists:** the SPA renders agent text through `AgentText`, which shows plain text only.
- **What doesn't:** no rule stops someone adding another renderer. Links in model text are kept as text, not stripped, and nothing checks a message's content before it is sent.
- **The risk:** a model that was handed several entities' data, or one that client content steers, could put another client's figures in a message, or a link that exfiltrates data.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Agents | Write text that is shown or drafted; never send (ADR-005) |
| Firm users | See agent text; approve and send messages (later increments) |
| The platform | Sanitises model text; checks scope on every outbound message; blocks and flags |

## 4. Goals and non-goals
**Goals**
- One sanitiser for model text, applied when the text is stored: links stripped unless allowlisted, and markup neutralised.
- A frontend rule: model text renders only through `AgentText`. No `dangerouslySetInnerHTML`, no markdown or HTML renderer.
- A guarded send path, `communications.send(ctx, draft)`, as the only way a message leaves:
  - it runs the scope checker before delivery;
  - it blocks and flags violations;
  - it audits every send and every block.
- **The scope checker:** for an engagement, which clients, entities, accounts and amounts are in scope, and which are mentioned in a draft that are not.

**Non-goals**
- Real delivery (email, the client portal): that comes with increments 2 and 8. Until then, `send` records the message and emits an outbox event with no transport.
- Drafting messages (increment 8), message UI, and client users.
- Model-based leak detection. The checker is deterministic code (ADR-050).

## 5. User stories and acceptance criteria
### Story 1: Model text can't exfiltrate data when shown
- **AC-1** Given model text with a link (`http(s)://…`, a markdown link, or `![](…)`), when it is stored as agent output, then links to hosts outside the allowlist are replaced by `[link removed]`, while allowlisted links stay as plain text. A screening result's rationale, quotes and unverified points all pass through the sanitiser.
- **AC-2** Given model text with HTML or markdown markup, when it is stored, then the markup stays inert text: tags are kept as text and never interpreted. The SPA renders it only through `AgentText`.
- **AC-3** Given the SPA's source, when it uses `dangerouslySetInnerHTML`, a markdown or HTML rendering library, or renders a model-text field outside `AgentText`, then lint fails (OUT-001 in eslint).

### Story 2: Nothing leaves without a scope check
- **AC-4** Given a draft message for an engagement, when `send` is called, then the scope checker runs first. With no violations, the message is recorded, `message.sent` is audited, and an outbox event `message.ready` is emitted.
- **AC-5** Given a draft that names another client, or an entity, account (code or name) or amount not in the engagement's scope, when `send` is called, then nothing is sent. The message is recorded as `blocked` with its violations (identifiers and kinds, never the text), `message.blocked` is audited, and the caller gets 409 `out_of_scope`.
- **AC-6** Given code anywhere except `communications`, when it references an email or SMTP library or a provider SDK for messaging, or emits `message.ready`, then lint fails (COMM-001).
- **AC-7** Given an agent or system context, when it calls `send`, then it is refused (ADR-005: agents draft, people send).

### Story 3: Scope is computed, not guessed
- **AC-8** Given an engagement, then its scope is:
  - its client and client entities;
  - the account codes and names in its ledger snapshots;
  - the amounts in its ledger snapshots and evidence versions (Q2).
- **AC-9** Given a draft, then the checker finds:
  - names of the firm's other clients and entities (matched case-insensitively on word boundaries);
  - account codes and names in the firm's other engagements;
  - monetary amounts not in scope.

  It is deterministic, and a test seeded with out-of-scope values proves each kind is caught.

## 6. Behaviour and flows
1. An agent (later increment) drafts a message. A person approves it and calls `send(ctx, draft)`.
2. `send` authorises the action (Q4), loads the engagement's scope, and checks the draft.
3. **Clean:** in one unit of work, insert the message as `sent`, audit `message.sent`, and emit `message.ready` (no transport yet).
4. **Violations:** insert the message as `blocked` with its violations, audit `message.blocked`, and answer 409.

## 7. Domain and data changes
- **New table `messages`** (communications, tenant-scoped, forced RLS, insert-only):
  - columns: `id`, `tenant_id`, `engagement_id`, `channel`, `recipient_ref`, `body` (confidential), `status` (`sent` or `blocked`), `violations` (jsonb of kind and identifier), `created_by`, `created_at`.
- **The sanitiser** in `ai_gateway`. Agents apply it to free-text fields before they store output.
- **The link allowlist** is a setting (Q1).

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `ai_gateway.sanitise_text(text) -> str` | Strips links outside the allowlist; markup stays inert |
| `communications.check_scope(ctx, engagement_id, text) -> list[Violation]` | The scope checker |
| `communications.send(ctx: AuthContext, draft) -> MessageView` | The only send path |

No new HTTP route in this spec. Sending gets a route with the increment that drafts messages.

## 9. Authorisation and tenancy
- **Who sends:** `send` needs the matrix action `message.send`, for an engagement partner, manager or senior; agents are denied. It is a protected change, so it needs approval (Q4).
- **Scope:** scope is read through the owning modules' APIs (organisations, ledger, evidence), tenant-scoped. The checker sees only the caller's firm, so it can't detect another firm's names. Firms are isolated anyway (RLS), and a model never sees two firms' data.
- **Walls:** a walled person can't send for the walled client (SPEC-002).

## 10. AI behaviour
No new model calls. Sanitising applies to all stored model free text: the screener's rationale, quotes and unverified points now, and every later agent.

## 11. Integrations
None. Delivery transports come with increments 2 and 8.

## 12. Edge cases and failure modes
- **The engagement's own amounts written differently** (`1,250.00`, `$1250`, `1.25k`): amounts are normalised to cents before comparison. Rounded or abbreviated amounts are matched within the tolerance set by Q2.
- **Common words that are also client names:** names shorter than 4 characters aren't matched (Q3).
- **Checker failure:** fail closed. The message is blocked with violation `checker_error`.
- **A message with no engagement:** refused. Every message belongs to an engagement.

## 13. Security and privacy
- **Classification:** the message body is confidential and never logged. Violations hold kinds and identifiers only.
- **Threats:** exfiltration links in model text (AC-1); a cross-client leak in messages (AC-5); a renderer added later (AC-3); a bypass of the send path (AC-6).

## 14. Audit trail and evidence integrity
`message.sent` and `message.blocked` are audited, with the message ID and engagement. Messages are insert-only.

## 15. Observability
- **Logs:** `message.blocked` (kinds and counts, IDs only).
- **Metric:** blocked messages by kind.

## 16. Performance and scale
The scope is loaded per send from indexed tables. Hundreds of accounts and thousands of amounts per engagement is fine.

## 17. UX
None in this spec, beyond agent text continuing to render through `AgentText`.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1, AC-2 | unit | Sanitiser on links, markdown images and HTML |
| AC-3 | lint test | OUT-001 flags `dangerouslySetInnerHTML` and markdown renderers |
| AC-4, AC-5 | integration | Send clean and blocked; audit; 409 |
| AC-6 | unit | COMM-001 |
| AC-7 | unit | Agent or system context refused |
| AC-8, AC-9 | unit + integration | Scope assembly; each violation kind seeded and caught |

## 19. Rollout
No flag. The migration is additive. The screener's stored text is sanitised from the next result; existing rows stay as they are, since they're rendered as plain text anyway.

## 20. Open questions
- [ ] **Q1: link allowlist.** *Recommendation:* empty by default (every external link removed), with an `output_link_allowlist` setting of host names. Links are never fetched.
- [ ] **Q2: amounts in scope.** *Recommendation:* every amount in the engagement's ledger snapshots plus their column totals, matched exactly in cents. "Rounded" means to the nearest whole currency unit, 1 thousand or 1 million, as written (`1.25k`). Small numbers (under 100) are ignored as amounts, since they are usually counts or days.
- [ ] **Q3: name matching.** *Recommendation:* other clients' and entities' names in the firm, case-insensitive on word boundaries, ignoring names under 4 characters and a short stoplist (Inc, LLC, Group). Account names are matched only if they are at least 8 characters long and don't appear in this engagement's ledger.
- [ ] **Q4: who may send.** *Recommendation:* a new matrix action, `message.send`, for engagement partners, managers and seniors, with agents and system denied. Staff can't send to clients in Phase 1.
- [ ] **Q5: blocked messages.** *Recommendation:* they're stored with their violations, and the sender sees 409 `out_of_scope` with the violation kinds. There's no override in Phase 1: the person edits the draft and sends again.

## 21. Future / explicitly deferred
- Delivery transports: email and the portal (increments 2 and 8).
- Message drafting by the engagement agent (increment 8).
- Model-based leak detection, and checks across engagements beyond names, accounts and amounts.
