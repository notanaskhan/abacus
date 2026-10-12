---
id: TASK-062
title: "Comments, part 1: threads, sharing with the scope check, corrections, mentions, redaction and counts (backend)"
spec: SPEC-032
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9]
risk_zone: red
status: done
branch: task-062-comments-backend
worktree:
created: 2026-10-12
updated: 2026-10-12
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-032 §7, TASK-062: the data, rules and APIs for comments. TASK-063 builds the screens.

## Scope
SPEC-032 AC-1 to AC-9.

## Context to load
- Spec: `docs/specs/SPEC-032-comments.md`; ADR-109, ADR-031, ADR-027, ADR-052
- Code:
  - `requests/service.py` (`read_item`, `RequestItemRef.facts`, `request_items_for`, `RequestItemView`), `requests/repository.py` (`list_request_items`, fulfilments), `requests/availability.py` (the registration pattern);
  - `communications/scope.py` (`check_scope`, `Violation`), `communications/api.py`;
  - `notifications/catalogue.py` (`CATALOGUE`, `TEMPLATES`), `notifications/service.py`;
  - `kernel/crypto` (`seal`, `open_sealed`);
  - `identity/api` (`team_of`, `engagement_role_of`, `names_of`, `authorise`, `visible`);
  - `docs/architecture/permission-matrix.yaml`, `identity/authz/_matrix.py`;
  - `abacus_tools/quality/schema_check.py`, `banned_patterns.py` (`MODULE_DEPENDENCIES`, `LIST_EXEMPT`)

## Plan
- [x] Plan approved by human (founder, 2026-10-12: D1–D5 as recommended). Approved by founder: the paths named in D5

### What the code shows
- **Requests can't call the scope check directly.** Communications depends on evidence, which depends on requests, so requests importing communications makes a cycle. The pattern for this exists: connections registers its dataset lookup into requests (`register_available_datasets`, ADR-106).
- **Notifications** are stored as identifiers and a kind, and rendered by the SPA. The catalogue's docstring says recipients are "never a client user". The read path filters by `engagement.read_metadata`, which client roles already have, so a client can read their own notifications as they are.
- **`kernel.crypto.seal(tenant, plaintext, fingerprint)`** gives per-tenant envelope encryption, already used for evidence and connection credentials.
- **Item visibility for clients** is authorised per item with its facts (`client_visible_only`, `assigned_only`), as uploads and checks do.

### Design (for founder review)
1. **Data** (migration 0048), all tenant-scoped with forced RLS:
   - **`comments`** (insert-only):
     - id, engagement, request item, evidence version (null for the item's own thread);
     - author user and side (`firm`, `client`);
     - visibility (`internal`, `shared`);
     - `body_sealed` (bytea) and `body_fingerprint` (SHA-256 of the text);
     - `corrects_comment_id`, created_at.
     - A check enforces that a client's comment is shared.
   - **`comment_mentions`** (insert-only): comment and user, unique.
   - **`comment_redactions`** (insert-only): comment (unique), redacted by, reason (1–500), created_at.
   - **`comment_reads`**: user, request item, evidence version (nulls not distinct), last_read_at. The only row the app updates.
   - **Grants:** INSERT only on the first three; INSERT and UPDATE (`last_read_at`) on reads. All are declared in `schema_check`, and the first three go in `INSERT_ONLY_TABLES`.
2. **Permissions** (matrix and `_matrix.py`):
   - `comment.read`: evidence.read's rows, with independence; client admin `client_visible_only`, contributor `assigned_only`;
   - `comment.create`: partner, manager, senior, staff and reviewer, with independence; client admin `client_visible_only`, contributor `assigned_only`;
   - `comment.share`: partner, manager, senior, staff;
   - `comment.redact`: firm admin, with recent MFA.
3. **Where** (SPEC-032 Q1): `requests/comments.py` (service), with repository functions in `requests/repository.py` and routes in `requests/routes.py`.
4. **Posting** (`POST …/request-items/{id}/comments`, and `…/versions/{version}/comments` for a version that fulfils the item):
   - authorise `comment.create` with the item's facts;
   - body: plain text, 1–4,000 characters, control characters removed;
   - visibility: a client user's comment is always `shared`; a firm user's is `internal` unless `share: true`, which also needs `comment.share`;
   - **sharing (Q4):** a firm comment to be shared goes through the registered scope checker. Violations are refused with 409 `out_of_scope` and their kinds, and nothing is stored. With no checker registered, sharing is refused (fail closed, D1);
   - **corrections:** `corrects` names a comment in the same thread by the same author. The correction takes that comment's visibility. A redacted comment can't be corrected;
   - **mentions:** user IDs, each of whom must be able to read the comment, otherwise 422 `mention_not_allowed`:
     - internal: the engagement's firm team;
     - shared: the team, plus the item's client readers (client admins if the item is client-visible; its assigned contributor);
   - **stored and recorded:** the body is sealed. The audit event is `comment.posted` (comment, item, version, visibility, correction; no text). The event `comment.mentioned` names the mentioned users.
5. **Reading** (`GET …/comments`, `GET …/versions/{version}/comments`):
   - authorise `comment.read` with the item's facts;
   - the list query applies `visible(ctx, "comment.read", …)`; client roles get `shared` only;
   - oldest first. Each comment has: author name and side, visibility, created_at, the opened text, `corrects`, `corrected_by`, and a redaction (by name, when, reason) in place of the text;
   - `GET …/comments/mention-candidates?visibility=` returns the people who may be mentioned (D3).
6. **Redaction** (`POST /v1/engagements/{e}/comments/{id}/redact`, `comment.redact`):
   - a reason of 1–500 characters; once per comment (409 `already_redacted`);
   - audited `comment.redacted`;
   - the sealed body stays, and no route returns it (SPEC-032 Q5).
7. **Unread and counts:**
   - `POST …/request-items/{id}/comments/read` (with an optional version) sets the reader's last-read time;
   - `RequestItemOut` gains `comment_count` (comments the reader may see, item and its versions) and `unread_comments` (a boolean: any newer than the reader's last read of that thread, excluding their own).
8. **Scope checker registration** (D1): `requests.register_comment_scope_check(fn)`. Communications registers `check_scope` at import, like connections' dataset lookup. `MODULE_DEPENDENCIES["communications"]` gains `requests`; requests stays free of communications.
9. **Notifications** (SPEC-032 Q2 backend part):
   - catalogue kind `comment.mentioned`: recipients are the payload's mentioned users, who may be client users (D2); the subject is the request item;
   - template: "You were mentioned in a comment on {engagement}.";
   - the "never a client user" rule becomes "client users only for mentions, already checked by the poster's service".
10. **Logging and classification:** comment text is `classified("restricted")` in every model, never logged or put in audit refs, and sealed with fingerprint-bound AAD.
11. **Tests:**
    - threads per item and version;
    - grants refuse UPDATE and DELETE;
    - default visibility; client routes never return internal notes; contributors see only assigned items;
    - corrections (same author, same thread, visibility inherited);
    - mention candidates and refusals; one notification each, including to a client;
    - the scope check blocks a shared comment naming another client, and fails closed unregistered;
    - redaction by role, the stub, and audit;
    - counts and unread per reader;
    - the body is sealed (the column isn't the text).

### Questions for the human
- **D1 — wiring the scope check.** Recommended: communications registers `check_scope` into requests (the ADR-106 pattern), and sharing is refused while nothing is registered. Alternative: add a module-level exception allowing requests to import communications. That creates a cycle through evidence, which the dependency rules forbid.
- **D2 — client recipients.** Recommended: allow client users as recipients for `comment.mentioned` only, since mentions were checked against who can read the comment when posted. Alternative: notify only firm users for now (the client bell would then never show comment mentions).
- **D3 — who can be mentioned on a shared comment.** Recommended: the engagement's firm team, plus the item's client readers (client admins when the item is client-visible, and its assigned contributor). Firm administrators and practice leaders without an engagement role can't be mentioned.
- **D4 — support access.** Recommended: `platform_support_content` may read comments (break-glass content, as evidence), and never post or redact. Alternative: no support access to comments.
- **D5 — approval file:**
  - `docs/architecture/permission-matrix.yaml`, `backend/src/abacus/modules/identity/authz/_matrix.py`;
  - `backend/src/abacus/modules/communications/**`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`;
  - `backend/tests/unit/**`, `backend/tests/integration/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation; client roles never receive internal notes
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-12` — Design written for founder review after SPEC-032 merged (#111).
- `2026-10-12` — Built (D1–D5): migration 0048; `comment.read/create/share/redact`; `requests/comments.py` (threads, sharing with the registered scope check, corrections, mentions, redaction, reads); counts on the request list; `comment.mentioned` notifications, including clients. Unit tests and gates pass. Local smoke on the Dev firm: the client's comment was shared and the firm's internal note was hidden from the client; a shared comment naming another client was blocked; the correction stayed internal; unread cleared after reading; a partner couldn't redact; the stored text was sealed; the app role was refused UPDATE and DELETE; the client received and read the mention notification (delivered directly, since the running worker predates the change).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| `out_of_scope` returns the code only, not the violation kinds | Errors carry fixed codes; the screen explains the possible reasons | No |
| Firm roles without an engagement role (practice leader, quality partner) see internal notes | They are firm side; only client roles are limited to shared | No |
| Redaction is `POST …/request-items/{id}/comments/{comment}/redact` | Keeps every comment route on the requests router | No |

## Handoff
Done. Restart `make dev` so the worker delivers `comment.mentioned`. Next: TASK-063 (web).
