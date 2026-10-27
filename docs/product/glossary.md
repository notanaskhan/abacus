# Glossary

> **Instructions for coding agents**
> - Use exactly these terms in code, database tables, API paths, specs and UI.
> - Never introduce a synonym. If a concept isn't here, stop and propose an addition.
> - "Code name" is the identifier to use in Python, TypeScript and SQL.

## Rules

1. **UI labels follow Accrued; code identifiers follow this glossary.** A screen may say "Binder", "Document", "Reminder", "Activity", "Deadlines", "Approvals" or "Integrations". Python, TypeScript, SQL, API paths and specs use the code names below. This is the addendum §3.3 vocabulary bridge, made binding.
2. **The copy registry is the only place UI words live** (`apps/web/src/screens/<ID>/copy.ts`, keyed by screen ID). Lint rules L1–L11 check it. Firm-editable text (email templates, checklists, methodology) lives in the database.
3. **The "Don't use" columns generate the identifier ban list** in `backend/src/abacus_tools/quality/banned_patterns.py` (rule L12), so the glossary and the linter cannot drift apart. A "Don't use" cell holds backtick-quoted identifiers or words, comma-separated, or "—". Any qualification (a compound that is allowed, a UI exemption) is written in the Meaning cell, never in the ban cell.
4. A concept that is not here means: stop and propose an addition. This repo rule is unchanged.

Every table of terms keeps the column order Term | Meaning | Code name | Don't use. `python3 -I backend/src/abacus_tools/quality/glossary_report.py` prints the term and ban counts per section.

## Organisations and identity

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Abacus | Internal code namespace (packages, modules, database and infrastructure names). Never user-facing: the product is Accrued, and the portal shows the firm's name (ADR-133). | `abacus` | — |
| Firm | An accounting or audit practice using the platform. The tenant. | `firm` (`tenant_id` on records) | `company`, `org`, `account`, `customer` |
| User | A single global human identity with one login. When an agent acted, the actor is not a user. | `user` | `account`, `member`, `person` |
| Membership | A user's belonging to a firm, with roles. Adds `level`, `office_id`, `offshore` and `service_lines`. UI "46 of 46 seats" reads `plan_entitlements.seats`; `seat` stays banned in code. | `membership` | `seat`, `firm_user` |
| Client | A firm's relationship with a business, household, plan sponsor, nonprofit or family (trust) group. It owns entities, contacts and relationships. Walls attach here. | `client` (`clients.kind`) | `customer`, `company`, `account` |
| Client entity | One legal or tax person within a client: individual, joint-filing household unit, C or S corp, LLC, partnership, trust, estate, benefit plan or exempt organisation. Carries a sealed TIN. | `client_entity` (`entity_type`, `tin_sealed`, `tin_last4`) | `subsidiary`, `company`, `org` |
| Contact | A person at a client the firm communicates with. May hold scoped portal access through a client access grant. Kinds: client person, third party, K-1 recipient, TCWG, component auditor, prospect. Use `contact` plus `client_access_grant`, not `client_user`. | `contact` (`contact_kind`) | `client_user`, `rep` |
| Actor | Whoever performs an action: `human`, `agent`, `system`, plus `support` (already in code), `policy` (dormant, P-08) and the reserved `api_client`, `delegated_user`, `link_principal`. Agent work is attributed "‹person› via Agent"; policy work "Policy: ‹name vN›". Never name "Accrued Agent" as the actor of an approval. Never record `user` when an agent acted. | `actor` (`actor.kind`) | `performer` |

## Engagements

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Engagement | The contract for one service and one period: letter, team, budget and gates G1–G3. Holds one or more **work items**. `service_line` + `type` (`fs_audit`, `ebp_audit`, `review`, `compilation`, `preparation`, `agreed_upon_procedures`, `soc1`, `soc2`, `readiness`, `internal_audit`, `tax_compliance`, `cas_monthly_close`, `notice_response`, `advisory`). `audit` is never an entity name or a type value. | `engagement` | `project`, `job`, `audit` |
| Engagement member | A user's role on a specific engagement, plus roles `eqr_reviewer`, `specialist` and `client_service`. The repo role `reviewer` is kept as the read-only QC role (Q-06). Distinct from a **work-item assignment**, which records a function. | `engagement_member` | `team_member`, `assignee` |
| Fiscal period | The span of time an engagement covers. | `fiscal_period` | `year`, `period_range` |
| Audit area | A section of the audit evidence belongs to, e.g. cash, receivables. | `audit_area` | `category`, `section`, `folder` |
| Milestone | A key date in an engagement, e.g. fieldwork start. **Not** a phase and **not** a statutory due date: both are separate terms (see Phase and Deadlines). `deadline` and `phase` stay banned as synonyms of milestone. | `milestone` | — |
| Archived | The engagement's end state: locked after completion, nothing may change. Work items lock separately (`archive_locked_at`; UI "Locked"). `closed` is allowed as a status of binders, notices and review notes, never to mean archived. | `archived` | `finished`, `done` |

## Requests and evidence

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Request list | One or more per work item. UI label **"Binder"** (firm) or "PBC list". Kinds: organizer, PBC, close intake, intake, third party. | `request_list` | `pbc_list`, `checklist` |
| Request item | One thing asked for. UI label "Request" or "PBC request". Status codes follow the status bridge (SPEC-022, §3.3.1). Never a bare `request`. | `request_item` | `pbc_item`, `ask`, `task` |
| Retrievability tier | Classification of a request item, A to E, by whether it can be retrieved or must be requested (SPEC-022): **A** a standard report the connected system produces as is; **B** derivable by code from retrieved ledger data; **C** a document attached to records in the connected system; **D** held by the client, not in the connected system; **E** from third parties or physical records. A to C are *retrievable*. | `retrievability_tier` | `type`, `source_type` |
| Fulfilment | The link between a request item and an evidence item that satisfies it, plus `confidence` and `created_by_kind`. Agent fulfilments stay proposals until a person confirms. May cross engagements within one client (P-40). UI may say "Matched" or "Linked". | `fulfilment` | `match`, `link`, `evidence_mapping`, `request_mapping` |
| Evidence item | The stable concept of a piece of evidence, e.g. "AR aging at 31 Dec". Client-scoped files are allowed (`engagement_id` nullable). UI says **"Document"** in Files and the portal and **"Evidence"** on audit and attest screens. `document` is allowed in code only in compounds (see Reserved words). | `evidence_item` | `document`, `file`, `artifact`, `attachment` |
| Evidence version | One immutable snapshot of an evidence item. | `evidence_version` | `revision`, `copy`, `upload` |
| Provenance | Where an evidence version came from: source, method, time, period, entity, fingerprint. | `provenance` | `metadata`, `origin` |
| Method | How evidence arrived: `retrieved`, `uploaded`, `emailed`. Never a bare `source`. | `provenance.method` | `channel` |
| Fingerprint | SHA-256 hash of a file's content. Never a bare `hash`. | `sha256` | `checksum` |
| Screening result | Output of a mechanical or AI check on an evidence version, with two named checks and file flags (DEC-48). UI label "Evidence screening", never "Evidence check". | `screening_result` | `validation`, `check_result` |
| Review decision | A human's judgement on an evidence version or request item (evidence and requests only). Distinct from `sign_off` (L1–L5 approval of reviewable content) and from `decision` (a role-reserved judgement on a decision card). `approval` and `sign_off` stay banned as synonyms of review decision. | `review_decision` | — |
| Suggestion | One proposed value for one target, created by an agent for a human to accept or reject. UI may say "Agent recommendation" on decision cards and "Recommendations" on INS-03; `recommendation` stays banned in code. | `suggestion` | `recommendation` |
| Follow-up | A message asking a contact for missing or corrected evidence. UI may keep "Remind…", "Reminder" (POR-20 template name) and "Request Chaser" (library agent). In code `reminder` stays banned; the legacy tables are renamed (see Legacy identifiers). | `follow_up` | `reminder`, `chaser`, `nudge` |

## Connections and ledger

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Connection | A scoped, read-only, expiring link to a client entity's external system. Client-authorised; several per entity are allowed. Still read-only: firm-installed apps are **integrations** (own term), and writes happen only through declared integration adapters. | `connection` | `link`, `sync` |
| Sync run | One execution of pulling data through a connection. A tax-engine export or import is an `engine_sync_event`, not a sync run. | `sync_run` | `job`, `import`, `fetch` |
| Ledger snapshot | An immutable record of ledger data as pulled at a point in time. | `ledger_snapshot` | `ledger_copy`, `export` |
| Connection consent | The client's write-once record of starting a connection: the consent copy key and version, what the firm will and won't do, the authorization text, the person, the time and a hashed IP. Never updated (A-02-T13). | `connection_consents` | — |
| Reconnect request | A firm person's request that the client reconnect a connection that needs it: one open request per connection, a Reconnect request email from its database template and a portal to-do that clears on reconnect. | `reconnect_requests`, action `connection.reconnect_request` | — |
| Change event | A detected change in ledger data after evidence was accepted. | `change_event` | `diff`, `update` |
| Attachment | A file stored against a transaction in the client's ledger. Distinct from evidence. | `ledger_attachment` | `document`, `file` |

## Sampling

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Sample set | A selection of items chosen for testing. Re-performable: carries `seed` and `algorithm_version` (P-57). | `sample_set` (`sample_sets`, `seed`, `algorithm_version`) | `selection`, `sample_list` |
| Sample item | One selected item, usually a transaction. | `sample_item` | `selection_row` |
| Support match | The result of searching for a sample item's support: `found`, `not_found`, `doubtful`. | `support_match` | `match`, `lookup` |

## Agents and platform

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Agent run | One execution of an AI agent on a task, fully logged. | `agent_run` | `ai_call`, `job`, `invocation` |
| Prompt | A versioned instruction template in the prompt registry, referenced as `name@vN`. A user's saved request text is a **saved prompt**. Compounds such as `engagement_template`, `email_template`, `report_template` and `note_template` are allowed; `template` is banned only as a synonym of prompt. | `prompt` | `instruction` |
| Autonomy policy | Firm-configurable rules for which agent actions run automatically and which need approval. Versioned per engagement type (`autonomy_policy_version`), with Auto mode. UI label "AI policy". | `autonomy_policy` | `permissions`, `ai_settings` |
| Audit event | An append-only record of an action. UI may say "Activity" (tabs) and "Audit log" (ADM-07). In code `activity` stays banned; the legacy `agent_activity` is frozen (see Legacy identifiers). | `audit_event` | `log`, `history`, `activity` |
| Domain event | A message announcing a state change to other modules. | `domain_event` | `message`, `signal` |
| Outbox | The table where domain events wait to be published. | `outbox` | `queue` |
| Unit of work | The helper that commits a state change with its audit and domain events atomically. Never a bare `transaction`. | `uow` | — |
| Kernel | The shared technical foundation every module uses: database sessions, tenant context, unit of work, outbox, encryption, config, logging. Not a module. (ADR-101) Its sibling entry is Abacus, the internal code namespace. Not the `platform` module, which is separate. | `abacus.kernel` | `core`, `common`, `shared`, `utils` |
| Message | A communication sent to a contact (outbound only). Adds `message_thread` (portal thread) and `inbound_message` (firm mailbox). | `message` | `email`, `chat` |
| Notification | An alert to a user inside the platform. | `notification` | `alert`, `ping` |

## New terms: identity

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Level | Eligibility on a membership: partner, manager, senior, staff, seasonal, admin. | `memberships.level` | — |
| IT / Security | Firm role: the Qualified Individual. No client content without a break-glass session. | `security_admin` | — |
| Client service | Engagement role: binders, invitations, envelopes, request status, intake triage (DEC-20). | `client_service` | — |
| EQR reviewer | Engagement role: L5 and G6 only; never L1–L4 on that engagement. | `eqr_reviewer` | — |
| Client access / role / scope | Portal rights. The role union is evaluated per target scope. | `client_access_grants` (`role`, `scope_kind`, `document_classes`) | `client_user` |
| Ethical wall | A barrier that hides a client from named users. Added as a term at last (long-requested). | `ethical_walls` | — |
| Approval grant | Single-use authority for a write after approval. | `approval_grants` | — |
| Policy principal | The dormant actor kind for policy acceptances (P-08). | `actor_kind='policy'` | — |
| Sign-in challenge | One passwordless portal sign-in attempt (POR-01 a, b, f, g): an emailed 6-digit sign-in code that expires after 10 minutes, at most 3 wrong codes per email before a 15-minute lock (DEC-35), resend after 60 s without resetting the tries. The email is kept only as a tenant-keyed fingerprint and the code only as a hash; an unknown email gets the same answer and no row names a person. UI "Sign-in code" for the code itself. | `sign_in_challenges` (`email_fingerprint`, `code_hash`, `attempts`, `locked_until`) | — |
| Trusted device | A browser a portal user chose to trust after two-step verification ("Trust this device for 30 days", POR-01 c): a `__Host-` cookie bound to the user and the tenant, stored as a hash. Lasts 30 days or fewer by firm policy, never more; revoked when access changes or the second factor is reset. | `trusted_devices` (`token_hash`, `expires_at`, `revoked_at`) | — |
| MFA backup code | One of 8 single-use codes shown once at two-step setup (POR-01 c′, DF-17), stored hashed and marked used on first use; global to the user like the factor itself (ADR-002). UI "Use a backup code". | `mfa_backup_codes` (`code_hash`, `used_at`) | — |
| Two-step verification | UI term for portal MFA: a code from an authenticator app after the sign-in code, required for owners, signers and approvers (DEC-34 floor) and for every client user when the firm extends it. | `mfa` (`portal_security_policies`, `register_mfa_requirement`) | — |
| Security policy | A firm's staff sign-in rules (G-02, ADM-06): Require SSO with its enforcement facts, the IdP-MFA attestation, session and idle limits that may only be shorter than the platform's, the one SSO-exempt account and "Allow support session requests". UI "Security". | `security_policies`, actions `security.read` / `security.manage` | — |
| SSO-exempt account | The firm's one emergency staff login that may sign in without SSO when the IdP is down; holds a hardware-key factor and records when it was last tested. UI "Break-glass account" on ADM-06; never the support engineer's break-glass session (`support_sessions`, SPEC-012). | `sso_exempt_account` (`security_policies.sso_exempt_user_id`) | `break_glass` (in code, for this) |

## New terms: organisations

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Office | A filter, never an access boundary (DEC-30). | `offices`, `office_id` | — |
| Team | Firm grouping; offshore teams are allowed. | `teams` | — |
| Relationship | A link between entities: spouse, owner_of %, trustee_of, beneficiary_of, sponsor_of, upper_tier_of, executor_of, gp_of, lp_of, estate_of. `estate_of` links an estate entity to the decedent's entity ("Estate of Walter Thornbury" estate_of Walter Thornbury, under the client "Walter Thornbury"; CLI-06 c, DEC-62). | `entity_relationships` (`kind`) | — |
| TIN | Masked everywhere; reveal is logged. | `tin_sealed`, `tin_last4`, action `tin.reveal` | — |
| Consent (§7216) | One purpose per signed document. Purposes: `use`, `ai_disclosure`, `offshore_disclosure`, `third_party_disclosure`, `other_services_use`, `firm_defined`. | `consents`, `consent_signers` | — |
| Authorization (2848/8821) | UI "On file / Not on file". | `tax_authorizations` | — |
| Client intake | The single new-client or prospect intake (CLI-06 a–f, h, i): a resumable draft committed in one unit of work as a client or an entity under an existing client, sealed TIN, relationships, contacts, a Prospect engagement with work items by service, a conflict-check link and an optional acceptance record. A draft holds identifiers and typed values only and is purged 30 days after discard or commit. | `client_intake_drafts`, action `client.intake` | — |
| Client import | A bulk client and contact import from a CCH Axcess Tax export or a CSV (CLI-06 g): upload, column mapping, one match decision per row (`new`, `merge`, `keep_both`, `skip`), then a batch run that is safe to re-run. The file is kept 30 days. Not a sync run and not an engine sync event; `import` stays banned on its own and is allowed only in this compound. UI "Import…". | `client_imports`, `client_import_rows`, action `client_import.run` | — |
| Conflict check | A deterministic search of names against every client, entity, contact, relationship and engagement counterparty in the firm (CLI-06 a, CLI-08 c), run as a system principal over metadata; walled matches are redacted with no name (DEC-64). Each match carries an assessment (status object `conflict_assessment`) that only a manager or partner clears, with a reason. | `conflict_checks`, `conflict_results`, `conflict_result_events`, actions `conflict.run`, `conflict.clear` | — |
| Screening record | A person's recorded result of a sanctions or adverse-media screening (OFAC SDN, adverse media, restricted-entity list): `no_match`, `match` or `not_applicable`, with an optional evidence link and a sealed note. Insert-only, human-recorded, never an agent result. Not a screening result, which is a check on an evidence version. | `screening_records`, action `screening.record` | — |

## New terms: engagements

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Service line | One of audit, tax, cas, advisory. UI "Departments" is never used. | `service_line` | `department`, `departments` |
| Work-item function | A function recorded on a work-item assignment: preparer · first_level_reviewer · detail_reviewer · manager_reviewer · signer · eqr · close_preparer · close_reviewer · project_lead · specialist. | `work_item_assignments.function` | — |
| Engagement contact | Facts used by conditions, not roles (approver_of_record, ske_designee, signing_officer, …). | `engagement_contacts` | — |
| Work item | The unit of work under an engagement. Kind: assurance, tax_return, close, notice, advisory_project. | `work_items` | — |
| Project (advisory) | An advisory work item. Never a bare `project` in code. | `advisory_projects` | `project` |
| Gate | Gate providers G1–G9. Computed live, snapshot at transition. | `gates_met(...)` | — |
| Multi-entity scope | Group audits and households (P-63). | `engagement_entities` | — |
| Acceptance record | The acceptance or continuance file for a client or engagement (CLI-07): questionnaire answers by section, manual checks, flags with sources, a risk rating, and one decision by the engagement partner (accept, accept with conditions, decline) with a rationale and fresh MFA. Kinds `new_client`, `new_engagement_existing_client`, `continuance`; status object `acceptance_record`. People prepare it and a person decides; an agent never decides (I-AGENT-NEVER). It replaces the repo's insert-only `engagement_acceptance`, which retires with its adapter (P-07-T59). | `acceptance_records`, `acceptance_answers`, `acceptance_flags`, `acceptance_decisions`; actions `acceptance.prepare`, `acceptance.decide` | — |
| Acceptance condition | A condition attached to an "Accept with conditions" decision, owned by a named person (CLI-07d: three conditions owned by Samuel Ito). Tracked by insert-only events on the acceptance record until P-05 turns it into a to-do. | `acceptance_conditions`, `acceptance_condition_events` | — |
| Independence conclusion | The engagement partner's conclusion on engagement independence once every team member has confirmed (CLI-08 f; SHL-11 "Conclude engagement independence?"): `independent`, `independent_with_safeguards` or `not_independent` (status object `independence_conclusion`), with sealed safeguards and fresh MFA. Insert-only; a later conclusion supersedes an earlier one. Human only. Not a member's independence confirmation. | `independence_conclusions`, action `independence.conclude` | — |
| NAS evaluation | The evaluation of one nonattest service for an attest client under ET 1.295 (CLI-08 b, UI "NAS matrix"): whether it is provided, the evaluation, the SKE designee and safeguards; status object `nas_evaluation`. | `nas_evaluations`, `nas_evaluation_events`, action `nas.evaluate` | — |
| Independence breach | A logged breach of independence and its steps: logged, evaluated, communicated to TCWG, remediated (CLI-08 g "Breach logged — evaluate, communicate to TCWG, remediate"). Insert-only events; nobody concludes independence while a breach is open. | `independence_breaches`, `independence_breach_events`, action `independence.breach_manage` | — |

## New terms: requests

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Binder | One or more per work item (DEC-31). UI label for a request list. | `request_lists` (`kind`, `part`, `work_item_id`) | — |
| Request category | The binder rail grouping. "category" is allowed only in this compound. | `request_categories` | — |
| Delegation | Third-party request scope (POR-14). | `request_delegations` | — |
| Binder recipient | A client contact a binder is visible to (BND-02 rail "Visible to"; `PUT /v1/binders/{id}/recipients`). Binder emails (`binder_published`) go to its recipients. Insert-only: removing a recipient writes a new row with `removed_at`. Not a delegation, which scopes one request item to a third party. | `binder_recipients` (`binder_id`, `contact_id`, `removed_at`) | — |
| Request upload intent | A short-lived note from the portal that a client is uploading n files to one request item, so BND-02 shows "Uploading 2 files…" by polling (DEC-23). UNLOGGED, 90 s TTL, swept every 60 s; never evidence and never a fulfilment. `upload` is allowed in code only in this compound and the legacy `upload_*` tables; it stays banned as a synonym of evidence version. | `request_upload_intents` (`files_expected`, `expires_at`) | — |
| Drop batch | One portal drop of one or more files anywhere on POR-03 (R-01 Story 2.1). The client sends one `X-Drop-Batch` id with every file of the drop and an `Idempotency-Key` per file; each file is stored in the engagement drop zone (`inbox_files.channel = 'portal_drop'`) and sorted by code. `GET /v1/portal/drops/{batch_id}` reports each file's outcome: `rule_linked`, `waiting`, `duplicate_flagged` or `refused`. Never evidence on its own and never a fulfilment. | `drop_batch_id` (`inbox_files.channel`, `dropped_by_contact_id`, `sort_outcome`) | — |
| Rule fulfilment | A fulfilment created by code, not by a person or the agent: a portal drop whose file matched exactly one item the dropper can see, decisively (`evidence/matching.py` `should_match`; DEC-58 a). The request reads uploaded and the client receipt "Suggested — Brightwater Hale will confirm" until a named person accepts the version. Audited with actor `system` and the dropper as `on_behalf_of`. | `fulfilments.created_by_kind = 'rule'` | — |
| Fulfilment void | A person's correction of a wrong rule fulfilment (`reason: wrong_request`): the link is stamped void, never deleted, the request returns to requested if nothing else fulfils it, and the version waits in the engagement drop zone again. Only an unaccepted rule fulfilment can be voided (409 `not_voidable` otherwise). | `fulfilments.voided_at`, `voided_by`, `void_reason`; event `fulfilment.voided` | — |
| Follow-up policy | A firm's reminder rules (DEC-74): cadence in days, the maximum number of follow-ups, the send time in the recipient's time zone on weekdays, stop when the client marks the binder done, notify the assigned preparer after the maximum, and the mode (`draft_for_person`, the default, or `send_on_schedule` behind a flag). One row per firm; P-06's per-binder override wins. UI "Reminders" and "Reminder schedule". | `follow_up_policies` (`cadence_days`, `max_reminders`, `mode`) | — |
| Questionnaire / question / answer | Organizers, POR-05, POR-11. | `questionnaires`, `questions`, `answers`, `transaction_questions` | — |
| Evidence board | The legacy SPEC-022 request-item board (R-07). The component moves from `apps/web/src/screens/Board.tsx` to `apps/web/src/domain/requests/RequestBoard.tsx` (DS-S4); binder surfaces keep the handoff label "Requests". Not the ENG-10 Board (see New terms: workpapers). | `RequestBoard` | — |

## New terms: evidence

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Document classification | What code (or, later, the agent) says a document is: form family and code, tax year, issuer, kind, page count, masked TIN last 4, with confidences and citations. Insert-only; a person confirms. | `document_classifications` (N-01-T17) | — |
| Folder kind | Which Files folder a document sits in under a work item or client: Source documents, Workpapers, Correspondence, Deliverables, Signed authorizations. | `evidence_items.folder_kind` (`source_documents`, `workpapers`, `correspondence`, `deliverables`, `signed_authorizations`) | — |
| Permanent file | A client's documents that belong to no single engagement (client-scoped evidence, ADR-158): read by anyone who can read content on a non-walled engagement of that client. | `evidence_items.scope = 'client'` | `master file` |
| Filed | An inbox attachment a person filed: it is now an evidence version (or version n+1) in a destination. UI word only for inbox items and their Files rows. | `inbox_attachments.status = 'filed'` | — |
| Citation | An insert-only, code-verified pointer from a cited value to its source, of one of ten kinds (`document_text`, `sheet_cell`, `ledger_line`, `workpaper_cell`, `methodology_step`, `policy_rule`, `record_field`, `tax_form_line`, `artifact_cell`, `request_item`). It is verified before display: a failed one is stored `verified=false` with a `verification_reason` and shown "Unverified". No quote text is stored, only `quote_sha256`; the quote is re-read from the masked word layer. Owned by `evidence` (ADR-166). | `citations` (v2), `citation_kind`, `quote_sha256`, `verification_reason` | — |
| Citation event | An insert-only row that changes a citation's computed state: `moved` (its source has a successor version), `broken` (the source was voided, withdrawn or erased) or `relinked` (a person re-verified it on the successor; human only). The state is never stored on the citation (ADR-166). | `citation_events` (`citation_event_kind`), view `citation_current` | — |
| Virtual document | A split of a combined PDF. | `evidence_versions.parent_version_id` + `page_range` | — |
| Document class / classification | OCR and classification outputs. `document` appears in code only in these compounds. | `document_class`, `document_classifications`, `extracted_fields`, `evidence_pages` | — |
| Evidence page / word layer | One page of an evidence version (or inbox file, or unlock derivation) with its geometry, and its word layer: a sealed JSON object of words and boxes in page points, read by code to verify citations, resolve regions and search. Agents and the viewer only ever get its masked projection. | `evidence_pages` (`text_layer_key`, `has_text_layer`, `ocr_used`) | — |
| PII region | A detected taxpayer identifier, bank number or date of birth on a page (`pii_kind`: `ssn`, `itin`, `ein`, `bank_account`, `routing_number`, `dob`). It is burned out of every served page image and shown as a mask token such as `•••-••-6081`; the value is sealed. Detection is code, never a model (P-03 §4.4). | `pii_regions` (`value_sealed`, `last4`), `pii_scan_runs` | — |
| PII reveal | A live, onshore person's logged view of one PII region's value for a short time (30 s in the viewer). It writes a `pii.revealed` audit event without the value. Never an agent, system or client act. Distinct from `tin.reveal` on a client entity's TIN field. | `pii_reveals`, action `pii.reveal` | — |
| Evidence derivation | The anchor for records derived from an evidence version without changing it, such as the extraction, pages, word layer, PII regions and masked previews of a password-unlocked PDF. The evidence object and its fingerprint are untouched (ADR-004). | `evidence_derivations` (`kind`: `password_unlock`), action `evidence.unlock` | — |
| Annotation | SHL-08 viewer marks; the evidence itself is unchanged. | `annotations` | — |
| Withdrawal | P-31 (ADR-162): a client voids an upload the firm has never accepted. The version is hidden at once from firm reads, agents and exports, and crypto-erased after 30 days unless held. Accepted evidence is never withdrawable (409 `evidence_accepted`). UI **"Withdraw"** for the portal control and its DF-15 copy, never "Remove" or "Delete" (see Copy-level bans). | `evidence_withdrawals`, action `evidence.withdraw` | — |
| Evidence object key | The wrapped data key of one detached-key evidence version (client-channel uploads, ADR-162), stored apart from the object so destroying it crypto-erases the file. Acceptance stamps `retained_at`, one-way; only the purge's SECURITY DEFINER path nulls `wrapped_key` and stamps `destroyed_at`. Not the S3 object path (`tenants/<tenant>/v/<version_id>`) and not the tenant key. | `evidence_object_keys` (`version_id`, `wrapped_key`, `retained_at`, `destroyed_at`), `evidence_versions.storage_mode` | — |
| File folder | The Files tree. | `file_folders` | — |
| Archive / addition | Seal manifests; post-lock additions. | `archives`, `archive_additions`, `audit_checkpoints` | — |
| Retention floor | The legal minimum years a record type is kept, per service line (`any` for every line), with its anchor event and authority. Platform content in numbered sets, imported by one staff member and published by another; never a literal in code (DEC-156). | `retention_floors`, `retention_floor_of()` | — |
| Retention policy | A firm's years for a record type and service line, at or above its floor, with a clock-start event, a lock and a basis (DEC-71 / P-14). Destruction batches are Q-05's. | `retention_policies`, `retention_policy_versions`, `destruction_batches` | — |
| Legal hold | A person's preservation order on a client, a client and tax year, an engagement or a work item, with a reason code (IRS examination, litigation, regulatory inquiry, subpoena, other). While any hold covers a stored version, no retention expiry, withdrawal or destruction can erase it, and S3 holds the object (`legal_hold.placed`, `legal_hold.lifted`; human only). Statuses: Applying, Active, Releasing, Released. | `legal_holds`, action `legal_hold.place` / `.lift` / `.read` | — |
| Hold object | One evidence version a legal hold covers: the reference count. The S3 object legal hold comes off only when no unreleased hold object names that stored object. | `hold_objects`, `active_hold_count()`, `holds_covering()` | — |
| Capture session | POR-19 mobile capture. | `capture_sessions` | — |
| Firm export | The firm's whole data, exported on request by a security admin and approved by a different person (a partner or security admin), with fresh MFA; links last 15 minutes within 7 days of approval (DEC-72). | `firm_exports`, actions `firm_export.request` / `.approve` / `.download` / `.read` | — |

## New terms: notifications

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Notification kind | What a notification is about, registered once through the C16 slot. New codes are snake_case with no dot (`client_uploaded`, `mention`); SPEC-013 dotted codes stay valid as legacy. | `kind`, `register_kind` | `notification type` |
| Notification category | The tab a kind falls under: approval, mention, client activity, run, deadline, system, other. | `category` | — |
| Inline action | An action taken on the notification row itself, from a closed set: accept document, return document, open sign-off. | `inline_actions` | `quick action` |
| Notification preference | A person's per-kind choice of In Accrued and Email. | `notification_preferences` | — |
| Notification delivery | One send of a notification on a channel other than in-app (email only). | `notification_deliveries` | — |

## New terms: communications

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Inbox (firm mailbox) | Distinct from the engagement drop zone `inbox_files`, which is kept. | `mailboxes`, `inbox_threads`, `inbound_messages`, `inbox_attachments`, `triage_decisions` | — |
| Inbox thread | One conversation of firm intake (INB-01 rail row): a portal upload batch, a staff-logged batch or an email thread, matched to a client or unmatched (ADR-210). Unmatched threads are visible only to the intake scope, by sender and subject. | `inbox_threads` (`source_kind`, `match_method`) | `mail thread` |
| Inbound message | One received message on an inbox thread, whatever its channel (`email`, `portal_upload`, `staff_logged`). Insert-only; its body is sealed and read only with `inbox.read_content`. | `inbound_messages` (`channel`, `received_via`) | — |
| Inbox attachment | One file received on an inbound message, before and after triage. Its status moves only through `communications/transitions.py` (New, Waiting, Filed, Ignored, held, withdrawn). Never evidence until a person files it. | `inbox_attachments` | `intake file` |
| Triage decision | A person's insert-only decision on one inbox attachment: file, ignore or hold (INB-02). Never an agent's (`actor_kind = 'human'`). | `triage_decisions` (`decision`) | `auto-file` |
| Sender rule | "Remember sender": a matched sender address (stored as an HMAC and a sealed copy) mapped to a client, so later items from it match by themselves. Revocable. | `inbox_sender_rules` | `whitelist` |
| Intake scope | The firm-level right of an intake-team member to read inbound messages and attachments until they are filed and to file them into the matched client's non-walled destinations (DEC-20, DEC-701). | `intake_scope` (matrix condition) | — |
| Intake team | A team of kind `intake`; its members hold the intake scope. Managed in the teams settings. | `teams.kind = 'intake'` | — |
| Log received documents | Staff-logged intake (INB-01 rail menu, O3 sheet): files received by email, mail, fax, in person or otherwise, recorded with who they came from and when. | `POST /v1/inbox/intake`, `inbound_messages.channel = 'staff_logged'` | `manual upload` |
| Portal thread | POR-07. | `message_threads` | — |
| Secure link | A single-use, 14-day link in a client email (reminder, invitation, signature request, deliverable ready, reconnect), stored as a token hash. An expired link can be renewed only to the address it was sent to (POR-01 e). The token travels in the URL fragment, never a query string. A secure link is not a fulfilment; `link` stays banned on its own and is allowed only in this compound. | `secure_links` (`purpose`, `token_hash`, `expires_at`, `renewed_from_id`) | — |
| Email template | A registered, firm-editable email key (`invitation`, `reminder`, `signature_request`, `deliverable_ready`, `confirmation_request`, `reconnect_request`, and keys other epics register through `register_email_template`) with its audience, whitelisted variables and call-to-action targets. `tenant_id` NULL is the platform default; a firm row overrides it from its first edit or import. Firm content: it loads through POR-20, ADM-10 or the import route, never a constant or a migration. | `email_templates` | — |
| Email template version | One immutable, published content of a template, numbered per template (UI "Published · v3"). Amended by R-01: a version carries `subject`, `preheader`, typed `blocks`, one `cta_label` and `cta_target`, its `source` (`handoff_seed`, `editor`, `import`), `content_sha256` and `published_by/at`. Publishing inserts version n+1 and never edits an earlier one; a sent message keeps the `template_version_id` it was rendered from. | `email_template_versions` | — |
| Email template draft | A firm's unpublished changes to one template (UI "Draft changes · v4"), at most one per firm and template, saved with `expected_version` (409 on a stale draft) and discarded or published by a firm admin. Never sent. | `email_template_drafts` (`base_version_id`, `draft_version`) | — |
| Sending domain | A firm's own domain verified for client mail through SES Easy DKIM and a custom MAIL FROM (ADM-10 d). Statuses `pending_dns`, `verified`, `failed`, `revoked`; until it is verified, client mail goes from the neutral sender with the firm's display name and Reply-To (DEC-59). UI **"Sender domain"**. | `sending_domains` (`dkim_records`, `mail_from_domain`, `status`) | — |
| Email suppression | An address a firm's mail must not reach again after a bounce or complaint, stored as an address hash, never the address. A send to it is recorded `blocked` with reason `suppressed`. | `email_suppressions` (`address_hash`, `reason`) | — |
| Firm mail policy | The platform control (the client-mail gate) that keeps a real firm's client, third-party and respondent email closed until both founders open it for that firm; staff mail is unaffected and synthetic firms always deliver to the sink. A blocked send is recorded with reason `firm_not_client_facing`. Writable only by the platform role. | `firm_mail_policies` (`client_mail_enabled`) | — |

## New terms: portal

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Client portal | UI term for the white-labelled surface clients use, at the origin root of the firm's portal host (ADR-163). It shows the firm's name and people and never "Accrued". The code module and session surface are `portal`; `client` alone never names the surface. | `portal` (`auth_sessions.surface = 'portal'`) | — |
| Portal branding | A firm's branding slots for the portal and client email: display and portal name, logo, address line, help, privacy and terms links, support contact, the "Secured by Accrued" footer (off by default) and a maintenance banner. Public-classified except the support contact's user id. Slots only: the accent stays espresso (ADR-155). | `portal_branding` | — |
| Portal domain | A host that serves a firm's portal: the default `<slug>.<neutral-portal-domain>` or a custom domain (P1; ADM-10 "Pending DNS → Verified"). The host is a branding hint only and is read without a tenant only through `portal_resolve_host` (ADR-163). | `portal_domains` (`kind`, `status`) | — |
| Portal preferences | A portal user's per-scope settings, today whether the POR-02 welcome card was dismissed; versioned, 409 on mismatch. | `portal_preferences` (`welcome_dismissed_at`) | — |
| Portal settings version | One immutable, published set of a firm's portal settings (brand, client experience, reminder fields), numbered per firm. Publishing (ADM-10, fresh MFA) inserts version n+1 and applies it in one unit of work; the editable draft is one row per firm, saved with `expected_version`. | `portal_settings_versions`, `portal_settings_drafts` | — |
| Portal client experience | A firm's portal toggles read by the portal read models: allow "Upload something else", phone capture, the team card, progress per work item, and the support contact. | `portal_client_experience` | — |
| Third-party room | UI term for POR-14: the reduced portal a third party (a named person at a recordkeeper, custodian, bank or engineer) uses to see and upload to only the request items delegated to them. Composed in code as `ScopedRequestRoom` (A-09 reuses it for POR-23). | `room` (`GET /v1/portal/room`; `third_party` grants with `delegated_only`) | — |
| Mark as Done | UI term for a client telling the firm a binder is finished (POR-03 e): the binder becomes `complete` with `marked_done_by_contact` and `marked_done_at`; the firm reads "Marked done by ‹contact›". Undo writes the compensating `binder.mark_done_undone` until the firm acts. | `binder.mark_done` (`marked_done_by_contact_id`) | — |
| Ignore | UI term for a client saying a request does not apply, with one of three reasons and an optional note (POR-03 f, POR-04 b). The request stays requested with `client_ignored_at`; the client word is "Ignored". Distinct from the firm's waive (`not_applicable`). Undo writes `request_item.ignore_undone` until the firm acts (DEC-24). The note is a shared comment with origin `ignore_note`. | `request_item.ignore` (`client_ignored_at`, `client_ignore_reason`) | — |
| Reminder | UI only: the POR-20 template name ("Reminder") and the ADM-10 "Reminders" fieldset. In code it is always a follow-up (`follow_up`, `follow_up_policies`); `reminder` stays banned as an identifier. | `follow_up` | — |

## New terms: signatures

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Envelope / signer | Provider `docusign` or `record`. | `envelopes`, `envelope_documents`, `envelope_signers`, `envelope_events`, `signature_evidence`, `envelope_policies` | — |
| Envelope | One package of documents sent for signature, or imported already signed (record mode, ADR-149), with its signers, fields and events. Firm-numbered ("E18"). Status words in `envelope`. | `envelopes` (`provider`: `docusign`, `record`, `fake`) | `signature request` (for the record) |
| Signer | One person who signs an envelope (client contact or firm user), with an identity method: KBA, email code, in-person ID or firm SSO; never SMS for the 8879 family. | `envelope_signers` | — |
| Signature evidence | The insert-only proof of one signer's signature: time, sealed and masked IP, identity result, method, document hashes and the package in the records bucket. | `signature_evidence` | — |
| Envelope policy | A firm's rules for one envelope family: allowed identity methods, KBA attempts, failure path, reminders, expiry, countersign, retention. Data, not code; a firm may only tighten the floor. | `envelope_policies` | — |
| Signing session | One short-lived, one-time handoff of a named signer to the provider's embedded view, confirmed by a server-checked return. | `signing_sessions` | — |
| ERSD | The electronic record and signature disclosure a signer accepts before signing (ESIGN). Its text is database content approved by counsel. | `esign_disclosures`, `esign_acceptances` | — |
| Record mode | Importing a package the firm had signed in its own tool, with the signer facts and the importer's attestation; Accrued keeps the evidence and runs no ceremony. | `envelopes.provider = 'record'` | — |

## New terms: review

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Sign-off (L1–L5) | Approval of reviewable content. Insert-only; staleness computed. Distinct from `review_decision`. | `sign_offs` (`level`, `content_hash`) | — |
| Review note | Blocks L2+; a comment never does. Status `open`, `responded`, `cleared`, `closed` or `withdrawn`; only a person clears. The plan's `review_notes` and `review_note_events` are the existing `reviewable_*` tables, extended in place (DEC-134). | `reviewable_notes`, `reviewable_note_events` | — |
| Issue | One service for tax, close, audit and attest. | `issues`, `issue_events`, `issue_links` | — |
| Decision card / decision | Reserved roles; rationale required; agents raise cards (X-13). | `decision_cards`, `decisions` | — |
| Checkpoint | Returns and workbooks. | `checkpoints`, `checkpoint_diffs`, `checkpoint_decisions` | — |
| Field history | SHL-09 provenance. | `field_value_versions` | — |
| Approvals (Home queue) | A projection; "Approvals" is a UI label only. | `human_gates` (projection; `kind`) | — |
| Waiting on you | The open human gates assigned to the viewer, directly or by role on the engagement, not snoozed by them (I-01, C13). Every surface reads one count source. | `human_gates` (open, assigned to the viewer) | — |
| Snooze | A person hides one gate from their own queue and counts until a time on or before its due date; it reappears by itself (I-01 OQ-4). Insert-only, per viewer. | `human_gate_snoozes` (I-01-T04) | — |
| Client activity | HOME-01's timeline of allowlisted client events, as codes, ids and counts. A rebuildable projection, not a record: the audit trail is. | `home_activity_items` (I-01-T12) | — |
| Home count | One HOME-01 tile or pill (audits, binders, agents running), counted by its owner under `visible()` and registered with the platform slot. | `register_home_count`, `HomeCount` | — |
| Sign-off kind and level | `kind` is `ladder`, `field_tick` or `final_approval`. `level` is 1 to 5: L1 preparer, L2 reviewer, L3 manager, L4 partner, L5 EQR (stored as a number, DEC-134). Level names are fixed; which levels a target needs comes from firm standards (ADR-160). | `sign_offs.kind`, `sign_offs.level` | — |
| Field tick | A sign-off on one field at L1 or L2 (SHL-09 "✓ KO"). Not a separate table. | `sign_offs` (`kind = 'field_tick'`) | — |
| Final approval | The signer's approval of a tax return (SHL-12 h). It is a sign-off, and open issues block it. | `sign_offs` (`kind = 'final_approval'`) | — |
| Sign-off slot | One level on a target's ladder, or one field tick, shown as signed or stale (DF-31). Stale means the sign-off's `content_hash` differs from the target's current hash. It is computed and never stored; re-signing writes a new row. UI "Changed after sign-off". | `sign_off_slot` (status registry, derived) | — |
| Reviewable | A target that can be signed off. Its owner registers it with a content hash, a version, its preparers and the levels it requires. | `register_reviewable`, `Reviewable` (ADR-160 `ReviewableFacts`) | — |
| Field flag | A review note anchored to one field (SHL-09 "⚑ SI"). Not a comment and not an issue. | `reviewable_notes` (`anchor_ref`) | — |
| Fix instructions / fix runner | A person's instructions on an issue, and the registered capability that turns them into a proposal. There is no direct-edit mode (DEC-53). | `issue_events.fix_instructions_sealed`, `register_fix_runner` | — |
| Checkpoint restore | Restoring creates a new checkpoint as a copy of an older one. Nothing is deleted. | `checkpoints.restored_from_id` | — |
| Suggestion decision | A person's insert-only, human-only act on a suggestion: `adopted`, `edited`, `dismissed` or `undone` (ADR-161; owned by `agents`). A decision card's agent recommendation is a suggestion; the compound column `recommendation_suggestion_id` is allowed, while a bare `recommendation` stays banned. | `suggestion_decisions` | — |
| Proposal decision | A person's insert-only, human-only act on a proposal: `approved`, `approved_with_edits`, `rejected`, `routed`, `follow_up` or `undone` (ADR-161; owned by `agents`). | `proposal_decisions` | — |
| Undo | A compensating `undone` row written by the same person within 10 seconds, which voids the decision's approval grant. Never a delete and never a browser-side delay. | `undone` (decision value), `undoes_decision_id` | — |
| Effect hold | The wait between a decision and the effect it allows. A grant holds any effect that leaves the firm until `not_before`, and the effect runs only when `consume_grant` succeeds. | `effect_hold` (workflow), `approval_grants.not_before` | — |

## New terms: collaboration

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Comment / mention / thread | Append-only (P-42). Polymorphic anchors; thread events `resolved` and `reopened`. | `comments`, `comment_mentions` | — |
| Presence | P-15. UNLOGGED table. | `presence_heartbeats` | — |
| To-do | Assignable work. Never "task"; never assigned to the agent; never client-visible. PRJ-01 "Tasks" becomes "To-dos" (DF-22). | `todos` | `task` |

## New terms: workpapers

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Board | The ENG-10 view (T19). A read model over `procedures`, `control_tests` and `close_procedures`; nothing new is stored. The SPEC-022 evidence board is a different concept (see Evidence board). | `board` | — |
| Workpaper | Cell keys such as `EBP-04!C14` are stable citation targets. | `workpapers`, `workpaper_sections`, `workpaper_versions`, `workpaper_cells` | — |
| Sheet / column / row / cell / view | 11 column types. | `sheets`, `sheet_columns`, `sheet_rows`, `sheet_cells`, `sheet_views` | — |
| Agent column | Cells hold suggestions until adopted. | `agent_columns`, `agent_column_runs` | — |
| Tie-out check | A person's check that a trial balance figure agrees to a cited source: `balanced` (debits equal credits), `tie` (one figure to an expected value) or `rollforward` (components to a total). Results (tie · off n · Pending, registry `tie_out_tally`) are computed on read in exact `Decimal`, never stored; an expected value needs a citation. | `tie_out_checks`, action `tie_out_check.define` | — |

## New terms: methodology

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Engagement template / template version | Replaces the set-once methodology pin. | `engagement_templates`, `template_versions`, `engagement_template_links`, `template_rollouts` | — |
| Program / step / procedure | A step is template content; a procedure is the engagement instance. | `programs`, `program_steps`, `procedures` | — |
| Scoping rule | Evaluated by code. | `scoping_rules` | — |
| Framework / criterion / control / mapping | Paraphrase unless licensed. | `frameworks`, `criteria`, `control_sets`, `controls`, `control_mappings`, `control_tests` | — |
| Firm standard / threshold policy | Database content (BH-TAX-02, BH AJE thresholds v2). | `firm_standards`, `threshold_policies` (+ versions) | — |
| Skill | Firm-written; eval-gated. | `agent_skills` | — |

## New terms: adjustments

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Proposed entry (AJE, RJE, PAJE, TJE, elimination) | `client_declined` added (DEC-83). | `proposed_entries`, `proposed_entry_lines`, `proposed_entry_decisions` | — |
| Approval batch | "Approved by RM under BH AJE thresholds v2". | `approval_batches` | — |
| Posting batch | The first true external write. | `posting_batches`, `posting_results` | — |

## New terms: assurance

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Audit (record) | Work-item kind `assurance`. | `assurance_work_items` | — |
| Phase | Planning · Fieldwork · In review · Completion. Not a milestone. | `assurance_work_items.phase` | — |
| Materiality | A decision card reserved to the EP. | `materiality_versions` | — |
| Finding / misstatement / deficiency | One root, two children (DEC-83). | `findings`, `misstatements`, `deficiencies` | — |
| Confirmation | Link-principal responses (POR-17). | `confirmations` | — |
| Component / component auditor | POR-23. | `components`, `component_auditors`, `component_instructions`, `component_deliverables` | — |
| Report / representation letter / governance communication | G7 and G8. | `audit_reports`, `report_releases`, `representation_letters`, `governance_communications` | — |
| Audit section | One row of the audit cockpit rail (AUD-02, AUD-03): a band (`overview`, `planning`, `group`, `fieldwork`, `completion`, `reporting`), a title, a state from the registry's `audit_section` words and a route. A row renders only when its owner registered it with `register_audit_section`; an unregistered section is hidden, never shown with a made-up state (A-01 DV-1). UI is the section's own title ("Trial Balance", "Source Documents"). | `audit_section`, `register_audit_section` | `workflow_step`, `rail_item` |
| Assurance phase event | One move of an assurance work item's phase, insert-only: `recorded` by a named person while the phase's gate has no registered provider (record mode), or `derived` by the system from the gate's `gate.met`. Backward and skipped moves are refused; an agent never records one (INV-1). | `assurance_phase_events`, action `assurance.record_phase` | `stage_event` |
| Record mode | How an assurance phase moves while Accrued computes no gate for it: a named person records it and the record says so (`phase_source = recorded`). It ends for a phase as soon as that phase's gate provider is registered (A-01 DV-4). | `phase_source` | `manual_mode` |
| External release | The engagement partner's record that the report was released outside Accrued, with its date (interim G8 for firms whose `assurance_release_mode` is `external`); starts the 60-day archive clock. Not an in-app release. | `assurance_external_releases`, action `assurance.record_release` | — |
| External archive | A manager's or partner's record that the audit file now lives in the firm's own tool, against a ready final binder export, with the firm-tool reference (interim G9). Not A-07's sealed archive: `archive_locked_at` stays NULL. UI "Archived in the firm's tool · ‹reference›". | `assurance_external_archives`, action `assurance.record_archive` | — |
| Engagement export | The ADR-036 open package of one work item's binder (evidence, index, provenance, audit trail) built after fresh MFA and a 10-s Undo window, downloaded through the API and expired after 7 days. Kinds `binder` and `final_binder`. Status words: the registry's `engagement_export`. UI "Export binder…". Not the firm export (`firm_exports`). | `engagement_exports`, actions `export.create`, `export.read`, `export.download` | `binder_download`, `zip_export` |
| Export manifest | The versioned `manifest.json` of an engagement export (`format: accrued.binder-export`, `format_version`), with SHA-256 checksums of every entry; the base of A-07's seal manifest. | `export_manifest` | — |

## New terms: ledger

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Consolidation / elimination | Q-15. Eliminations are `proposed_entries(kind='elimination')`. | `consolidations`, `consolidation_entities` | — |
| Grouping set | A firm's FS taxonomy, versioned: imported as a draft, published once by a person (A-03). Firm content, never seeded. | `grouping_set`, `grouping_set_versions` | `taxonomy` |
| Grouping | A heading of the statements (Cash and equivalents) with its class: assets, liabilities, equity, revenue or expenses. | `grouping` | — |
| FS line | A line of the statements under a grouping, with its normal balance; account-number ranges map accounts to it. | `fs_line`, `fs_line_range_rules` | `caption` |
| Mapping set | One trial balance of record's mapping to a published grouping set: rules from the ranges, people's edits on top (`mapping_set_edits`). "Mapping" names only this; request ↔ evidence links are fulfilments. | `mapping_set`, `mapping_set_edits` | `account_map` |
| Trial balance of record | The one trial balance an audit work item uses for a client entity, label and period end: a named person adopts an immutable ledger snapshot as version 1, and a newer snapshot becomes the next version with a reason; nothing earlier changes (ADR-004). Only a human adopts (INV-1). UI "Trial balance" (AUD-06). | `trial_balances`, `trial_balance_versions`, actions `trial_balance.*` | — |
| TB label | Which trial balance a snapshot or a trial balance of record is: Standard, Interim, Prior, Budget or Preliminary (registry `trial_balance_label`). Configurable labels wait for ADM-13 (G-03). UI chip "TB: Interim · 8/31/2026". | `label` (`trial_balances.label`, `ledger_snapshots.label`) | — |
| Layer | A column set of the trial balance: Unadjusted, AJE, RJE or Final (registry `trial_balance_layer`). Code computes every layer; AJE, RJE and Final exist only once an adjustment source is registered, and answer `layer_unavailable` before. | `layer`, `register_adjustment_source` | — |
| Leadsheet | One audit area's rollup of the trial balance: PY · CY · Δ · Δ%, in statement grammar, computed by code; accounts with no area appear under "Unassigned". | `leadsheet` | — |

## New terms: reporting

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Statement document / line item / linked value | Linked values are TB-linked · Formula · Override · Stale override. | `statement_documents`, `statement_versions`, `line_items`, `linked_values`, `tracked_changes` | — |

## New terms: tax

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Return | `return` is a Python keyword. | `tax_returns` | — |
| Return worksheet / field | Field-level provenance. | `return_worksheets`, `return_fields` | — |
| Document approval (tax) | Distinct from `review_decision` (Q-09). Allowed `document` compound. | `document_approvals` | — |
| K-1 package / activity | Drafts never reach the portal. | `k1_packages`, `k1_activities`, `k1_treatments` | — |
| Transmission record | A human record; Accrued never transmits. | `transmissions`, `efile_acks` | — |

## New terms: closes

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Close | A period close (`period` 'YYYY-MM'). Never "closed" for archived. | `closes` | — |
| Close task (UI) | The UI label "task" is allowed only on close-run surfaces (CLS-02, CLS-09 "Task groups"). The code name is `close_procedures`; the component is `RunStepRow`. | `close_procedures` | `task` |
| Close plan | Industry templates are database content. | `close_plans` (+ versions, rows) | — |
| Reconciliation | Two-sided bank reconciliation. | `reconciliations`, `reconciling_items` | — |

## New terms: notices

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Notice | Distinct from `notification`. | `notices` | — |

## New terms: practice

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Deadlines | Statutory due dates; rules are platform reference data (DEC-76). Not a milestone. | `filing_deadlines`, `due_date_rules` | — |
| Fee proposal (ENG-09) | Never a bare `proposal` (X-14): a bare `proposal` is the agent change set (`proposals`, see New terms: agents), so it is not in the L12 ban list. | `fee_proposals` | — |
| Insight | Metadata and counts only (R9). | `insight_metrics` | — |

## New terms: attest

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Attest exception / management response | ATT-06. | `attest_exceptions`, `management_responses` | — |
| Action plan / IA issue | Overdue is derived. | `action_plans`, `ia_issues`, `auditable_units`, `ia_plans` | — |

## New terms: integrations

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Integration (firm, personal) | A firm-installed app. May write only through a declared capability. Distinct from a connection. | `integration_catalog`, `firm_integrations`, `user_integrations`, `integration_events`, `integration_interest` | — |
| Write capability | A protected registry entry (P-17). | `write-capabilities.yaml` entry | — |
| Engine sync | Sync-chip states. Not a sync run. | `engine_sync_events` | — |

## New terms: platform

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Pilot enrolment | One work item's pilot: its window, its mode (shadow, live, system of record, exited) and the baseline days the firm agreed. System of record needs a named confirming person (Q-04-T007). | `pilot_enrolments` (`mode`) | — |
| Pilot metric snapshot | One computed pilot metric for an enrolment, metric key, optional subject and period; insert-only, one per key. | `pilot_metric_snapshots` | — |
| Reference set | Platform-published calendars (P-62). | `reference_sets` (+ versions) | — |
| Agent-minute | Metering unit (P-28). | `agent_minute`; `plan_entitlements` | — |
| Security incident | A firm's or Accrued's recorded security event, with its discovery time and the FTC clock (notify by discovery + 30 calendar days in the firm's time zone when 500 or more consumers' unencrypted data is involved). An Accrued-side incident is propagated into each affected firm's register. | `security_incidents`, action `incident.manage` | — |

## New terms: kernel

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| TRI | Tax return information. Data-class tag, plus `phi` and `pii_kind`. Gated by `consent_7216`. | `tri` | — |
| Access event | One read of client data (who, what, for whom), in the insert-only, partitioned read log kept apart from audit events (R-30). | `access_events`, `kernel.access.record_reads` | — |
| Audit checkpoint | A sealed range of a firm's audit events with its Merkle root and chain hash; an anchor publishes one to the records bucket. | `audit_checkpoints`, `audit_anchors` | — |
| Audit request context | The IP, user-agent family, device label ("Chrome · macOS"), staff session, sign-in method and MFA time a person's request carried, captured on that request's audit events (G-02-T06, DEC-60). Null for agent and system events. IP and device label are personal data (Confidential). | `audit_events.ip`, `.user_agent_family`, `.device_label`, `.session_id`, `.auth_method`, `.mfa_at`; `kernel.request_context` | — |
| Audit event label | A rebuildable search projection of one audit event: actor and target labels and keywords, never Restricted text. UI "Audit log" search (ADM-07). | `audit_event_labels` | — |

## New terms: agents

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Agent (capability) | Code-declared agent spec (ADR-047). | `modules/agents/specs/*.yaml` | — |
| Agent stage | Per firm and per agent: `off`, `shadow` (runs, nothing shown) or `live` (SPEC-036). | `agent_stages`, `agent_stage_events` | — |
| AI opt-in | A firm administrator's opt-in, with fresh MFA, to the agent reading clients' data, against the disclosure version shown (SPEC-036). | `firms.ai_client_data_at`, action `firm.ai_client_data` | — |
| AI exclusion | An engagement partner's exclusion of one engagement from the agent, with a reason. | `engagements.ai_excluded_at`, action `engagement.ai_exclude` | — |
| Run record | The insert-only record of a completed specialist run: versions, model, route, inputs' hashes, records read, citations and outcome, kept for the engagement's retention after traces expire. | `agent_run_records` | — |
| Run step | One step of an agent run. Never "task". | `agent_run_steps` | `task` |
| Plan / question / artifact / event | P-47. | `agent_plans`, `agent_questions`, `run_artifacts`, `run_events` | — |
| Proposal (agent change set) | Groups suggestions (X-14). | `proposals`, `proposal_rows` | — |
| Learned context | UI label; no "memory", "trained" or "learned" in copy. | `memory_items`, `corrections`, `agent_feedback` | — |
| Review package | SHL-19. | `review_packages` | — |
| Screening feedback | A person's thumbs up or down on an evidence screening aggregate (SHL-20f; a `request_batch` screening result). Thumbs down needs a reason code (`wrong_request_match`, `wrong_period`, `unclear_file`, `other`); the note is sealed. Insert-only. It never changes a verdict or a request status, and any learned context it feeds stays a proposal (ADR-068). Distinct from `agent_feedback`. | `screening_feedback` (`thumb`, `reason_code`, `note_sealed`) | — |
| Today | UI "Today". | `daily_briefings` | — |

## New terms: workbench

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Library agent | Platform rows, published through PLT-01. | `library_agents`, `agent_installs` | — |
| Agent (firm-made) | Only narrows a capability. | `agent_definitions` (+ versions) | — |
| Session | A workbench session. Distinct from `support_session`. | `workbench_sessions`, `session_items` | — |
| Saved prompt | A user's saved request text. Never a bare `prompt`. | `saved_prompts` | — |
| Schedule / trigger | P-50, P-51. | `agent_schedules`, `triggers` | — |

## Legacy identifiers: rename or freeze

| Identifier | Problem | Action | When |
|---|---|---|---|
| `reminders`, `reminder_items` (migration 0040), `/reminders` routes, `reminders.py` | Violate the glossary's own `follow_up` rule | Renamed to `follow_up_schedules` and `follow_up_items` (migration 0087); routes are `/follow-ups`; modules `follow_ups.py` | Done (F-03-T16, 2026-10-22) |
| `request_items.status` codes | The `received` inversion | Migrate (status code bridge, §9.5.6) | P-44 (S1) |
| `engagements.type = 'audit'` | Collides with the reserved word and the new taxonomy | Rewrite to `fs_audit`, with no alias | P-04 migration (S1) |
| `agent_runs.status` (`running`, `completed`, `escalated`, `failed`) | Four states vs 14 canonical ones | Migrate per §9.5.6 | P-47 (S1–S2) |
| `connections.status` (`active`, `needs_attention`, `revoked`) | Display words differ | Keep the codes; map them in the registry (§9.5.6) | S2 |
| `agent_activity` table, `activity.read` action | Use "activity" in code | **Freeze**: no new uses; a later rename to `run_events` | When P-47 lands |
| `apps/web/src/screens/Board.tsx` (the SPEC-022 evidence board) | Collides with the ENG-10 Board | Move to `apps/web/src/domain/requests/RequestBoard.tsx`; UI label "Requests" | DS-S4 |
| `RollForwardProposal*` classes | "proposal" | Leave as they are (internal); rename to `RollForwardPlan*` when next touched | Opportunistic |
| `connections.provider` CHECK (`'fake','import'`), `sync_runs.dataset` CHECK (`'trial_balance'`), `sync_runs.request_item_id NOT NULL`, the `connections_one_live` index | Block real connectors, scheduled syncs and OneWorld | Widen the CHECKs; make `request_item_id` nullable; make the index unique per (entity, provider, external company) | P-17/P-63 (S2) |
| Repo `reviewer` engagement role | Semantics undocumented | Keep as the read-only QC role; document it (Q-06) | Glossary PR |
| `inbox_files` | Two different "inboxes" | Keep: the engagement drop zone. The firm mailbox uses `inbox_threads` | Glossary PR |

## Copy-level bans (UI strings)

Lint rules L1–L12 check these against the copy registry.

| Never write | Instead | Rule |
|---|---|---|
| "Accrual" (as the product), "Arc", "ACME", "Accrual Agent", "Published by Accrual" | "Accrued". Exception: "Accrual" as an accounting method or close term, via the constant `ACCOUNTING_METHOD` | L1 |
| "Approved by Accrued Agent", or any approval, sign-off, release, send or post attributed to the agent | "‹person› via Agent" for agent-authored work; "Policy: ‹name vN›" for policy acceptances | L5/L6 |
| Persona names for the agent; Fieldguide terms (Field Board, AI Actions/✦, Prompt Library, Agent Knowledge, Today's Focus, Field Financials, Request Analysis, Tax Export, Departments) | Board, Agent column / Draft with agent, Saved prompts, Learned context, Today, Statements studio, Evidence screening, Hand off to tax, Service lines | D7, guardrails ch. 5 |
| "task" for assignable work | "To-do" (hyphenated) | R6, L2 |
| "memory", "trained", "learned" for learned context; "overwrite" for template updates; sparkle or wand glyphs | "Learned context"; "Update"; the atom glyph | AVOID lists |
| "Evidence check" | "Evidence screening" | decision record naming map |
| "Remove" or "Delete" on a client's unaccepted upload | "Withdraw" ("Withdraw this file? Brightwater Hale's team won't use it. It's kept securely for 30 days, then erased.", with the firm's name) | DF-15, ADR-162 |
| "n hidden by an ethical wall" | nothing (404 semantics) | DEC-43 |
| "Accrued" in the portal or client emails (except the optional footer) | The firm's name | L7 white-label crawler |
| "password", "task" or "Accrued" in portal copy (POR-*), sign-in and invitation emails, or portal error messages | "Sign-in code" and "Two-step verification" (there is no password); "to-do"; the firm's name | L2, L7 (P-08-T04) |
| "agent", "AI", "confidence", "task", "issue", a match percentage or a firm status word ("Uploaded – needs review", "Received ✓", "In review") in portal copy (POR-*) or a client email | The client words ("To do", "Done", "Ignored", "Returned"), "Suggested — ‹firm› will confirm" for a rule fulfilment, "to-do" | L2, L7 (R-01-T04) |
| Emoji, "!" in agent or product voice, "..." | "…" (U+2026) on dialog openers | L2/L3 |
| Font weights 600/700 outside document renderers; blue; zebra rows | Geist 400/500; tokens only | L8 |

## Reserved words

- **Task** means a development task in `work/tasks/` only. Unchanged in code. The UI label "task" is allowed only on close-run surfaces (CLS-02, CLS-09 "Task groups", "3 tasks running at once"). The code names are `close_procedures` and `agent_run_steps`; the component is `RunStepRow`. Assignable work is a **to-do** (`todo`). PRJ-01 "Tasks" becomes "To-dos" (DF-22).
- **Audit** means the type of engagement or the profession. Unchanged. Engagement types are `fs_audit` and `ebp_audit`; the work-item kind is `assurance`; the table is `assurance_work_items`. Use **audit event** for logged actions. The "Audits" nav item is unaffected.
- **Document** is a UI label in Files and the portal. In code it may appear **only in compounds**: `document_class`, `document_classifications`, `document_approvals` (tax, Q-09), `statement_documents`, `generated_document`. Never as a bare `document` entity; use **evidence item**, **ledger attachment** or **message**.
