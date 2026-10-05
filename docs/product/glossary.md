# Glossary

> **Instructions for coding agents**
> - Use exactly these terms in code, database tables, API paths, specs and UI.
> - Never introduce a synonym. If a concept isn't here, stop and propose an addition.
> - "Code name" is the identifier to use in Python, TypeScript and SQL.

## Organisations and identity

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Firm | An accounting or audit practice using the platform. The tenant. | `firm` (`tenant_id` on records) | company, org, account, customer |
| User | A single global human identity with one login. | `user` | account, member, person |
| Membership | A user's belonging to a firm, with roles. | `membership` | seat, firm_user |
| Client | A firm's relationship with a company it serves. Owned by one firm. | `client` | customer, company, account |
| Client entity | One legal company within a client. | `client_entity` | subsidiary, company, org |
| Contact | A person at a client the firm communicates with. | `contact` | client_user, rep |
| Actor | Whoever performs an action: `human`, `agent` or `system`. | `actor` (`actor.kind`) | user (when an agent acted), performer |

## Engagements

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Engagement | One job for one client and one fiscal period, e.g. the FY2026 audit. Has a type: `audit`, later `tax`, `cas`. | `engagement` | project, job, audit (as an entity name) |
| Engagement member | A user's role on a specific engagement. | `engagement_member` | team_member, assignee |
| Fiscal period | The span of time an engagement covers. | `fiscal_period` | year, period_range |
| Audit area | A section of the audit evidence belongs to, e.g. cash, receivables. | `audit_area` | category, section, folder |
| Milestone | A key date in an engagement, e.g. fieldwork start. | `milestone` | deadline, phase |
| Archived | Locked state after completion; nothing may change. | `archived` | closed, finished, done |

## Requests and evidence

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Request list | The full set of items requested for an engagement. UI may label it "PBC list". | `request_list` | pbc_list, checklist |
| Request item | One thing asked for. UI may label it "PBC request". | `request_item` | pbc_item, ask, task, request (alone) |
| Retrievability tier | Classification of a request item, A to E, by whether it can be retrieved or must be requested. | `retrievability_tier` | type, source_type |
| Fulfilment | The link between a request item and an evidence item that satisfies it. | `fulfilment` | match, link, mapping |
| Evidence item | The stable concept of a piece of evidence, e.g. "AR aging at 31 Dec". | `evidence_item` | document, file, artifact, attachment |
| Evidence version | One immutable snapshot of an evidence item. | `evidence_version` | revision, copy, upload |
| Provenance | Where an evidence version came from: source, method, time, period, entity, fingerprint. | `provenance` | metadata, origin |
| Method | How evidence arrived: `retrieved`, `uploaded`, `emailed`. | `provenance.method` | channel, source (alone) |
| Fingerprint | SHA-256 hash of a file's content. | `sha256` | checksum, hash (alone) |
| Screening result | Output of a mechanical or AI check on an evidence version. | `screening_result` | validation, check_result |
| Review decision | A human's judgement on an evidence version or request item. | `review_decision` | approval, sign_off |
| Suggestion | A proposal created by an agent for a human to accept or reject. | `suggestion` | recommendation, proposal |
| Follow-up | A message asking a contact for missing or corrected evidence. | `follow_up` | reminder, chaser, nudge |

## Connections and ledger

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Connection | A scoped, read-only, expiring link to a client entity's external system. | `connection` | integration, link, sync |
| Sync run | One execution of pulling data through a connection. | `sync_run` | job, import, fetch |
| Ledger snapshot | An immutable record of ledger data as pulled at a point in time. | `ledger_snapshot` | ledger_copy, export |
| Change event | A detected change in ledger data after evidence was accepted. | `change_event` | diff, update |
| Attachment | A file stored against a transaction in the client's ledger. Distinct from evidence. | `ledger_attachment` | document, file |

## Sampling

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Sample set | A selection of items chosen for testing. | `sample_set` | selection, sample_list |
| Sample item | One selected item, usually a transaction. | `sample_item` | selection_row |
| Support match | The result of searching for a sample item's support: `found`, `not_found`, `doubtful`. | `support_match` | match, lookup |

## Agents and platform

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Agent run | One execution of an AI agent on a task, fully logged. | `agent_run` | ai_call, job, invocation |
| Prompt | A versioned instruction template in the prompt registry, referenced as `name@vN`. | `prompt` | template, instruction |
| Autonomy policy | Firm-configurable rules for which agent actions run automatically and which need approval. | `autonomy_policy` | permissions, ai_settings |
| Audit event | An append-only record of an action. | `audit_event` | log, history, activity |
| Domain event | A message announcing a state change to other modules. | `domain_event` | message, signal |
| Outbox | The table where domain events wait to be published. | `outbox` | queue |
| Unit of work | The helper that commits a state change with its audit and domain events atomically. | `uow` | transaction (alone) |
| Kernel | The shared technical foundation every module uses: database sessions, tenant context, unit of work, outbox, encryption, config, logging. Not a module. (ADR-101) | `abacus.kernel` | platform (the twelfth module), core, common, shared, utils |
| Message | A communication sent to or from a contact. | `message` | email, chat |
| Notification | An alert to a user inside the platform. | `notification` | alert, ping |

## Reserved words

- **Task** means a development task in `work/tasks/` only. Never use it for product concepts.
- **Audit** means the type of engagement or the profession. Use **audit event** for logged actions.
- **Document** is not a domain term. Use **evidence item**, **ledger attachment** or **message**.
