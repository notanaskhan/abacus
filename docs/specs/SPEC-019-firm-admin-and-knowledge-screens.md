---
id: SPEC-019
title: Knowledge, budget, support access and walls screens
status: draft
owner: founder
risk_zone: amber
related_adrs: [ADR-011, ADR-028, ADR-026, ADR-069, ADR-053]
related_specs: [SPEC-002, SPEC-007, SPEC-009, SPEC-012, SPEC-016]
created: 2026-10-08
updated: 2026-10-08
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
This adds the remaining Phase 1 screens on APIs that already exist, in the SPEC-016 style (direction C, tokens only):
- **Knowledge:** search for every staff member, and the firm's documents for admins.
- **Budget and spend:** the firm's monthly budget against spend, setting it, and metering by engagement and agent.
- **Support access:** break-glass sessions, with approve, revoke and acknowledge.
- **Ethical walls:** list, create and remove.

## 2. Problem and context
The backend for SPEC-002, SPEC-007, SPEC-009 and SPEC-012 is built, but firms can only reach it through the API. SPEC-016 deferred these screens.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Firm staff | Search knowledge |
| Firm admins and practice leaders | Knowledge documents; budget (read; admins set it) |
| Firm admins | Support access and walls |

## 4. Goals and non-goals
**Goals**
- **Rail and navigation (Q1):**
  - the rail gains **Knowledge** for all staff;
  - **Firm admin** becomes a section with its own tabs: Methodology · Knowledge documents · Budget · Support access · Walls;
  - each tab shows only for roles the matrix allows, and the API stays the authority.
- **Knowledge search** (`/knowledge`):
  - a search box with results showing the document title, the section path, the passage and its score;
  - an empty state for "no documents yet";
  - passages are firm methodology rendered as plain text (not model output, so no AI tag).
- **Knowledge documents** (`/admin/knowledge`):
  - a list with status (pending, ready, failed, stale, withdrawn) and chunk counts;
  - Add document (a title, the source kind `firm_own` or `public`, and text pasted or loaded from a `.txt` or `.md` file in the browser, sent as text);
  - Withdraw, with confirmation;
  - pending documents refresh until ready;
  - the fresh-MFA prompt where required.
- **Budget and spend** (`/admin/budget`):
  - this month's spend against the soft and hard limits as a bar with numbers;
  - "Set budget" (firm admin, fresh MFA; the plan limit shown);
  - metering by engagement and agent for the day or month, in a sortable table with currency figures and the engagement's name where the user can see it, else "Engagement" plus a short ID (Q2).
- **Support access** (`/admin/support`):
  - requested, active and past sessions, showing the staff member, reason, scope, window, approvals, request count, and an emergency flag;
  - Approve (fresh MFA), Revoke and Acknowledge (for emergencies), each confirmed;
  - an unacknowledged emergency shows as a banner on every admin page (Q3).
- **Walls** (`/admin/walls`):
  - opening the page needs fresh MFA (`wall.list` requires it), so the prompt appears first;
  - list walls (person and client);
  - Create (a person picker and a client picker) and Remove (confirmed; your own walls can't be removed, as the API refuses).

**Non-goals**
- Charts beyond a simple progress bar.
- Knowledge PDF and Word uploads (SPEC-009 Q3).
- A staff-side support console.
- Dark mode.

## 5. User stories and acceptance criteria
- **AC-1** Given any staff member, when they search knowledge, then results show title, section, passage and score from the firm's ready documents, and an empty query or no documents shows a helpful empty state.
- **AC-2** Given a firm admin or practice leader, when they add a document, then it appears as pending and becomes ready without a reload. Withdraw asks for confirmation and the document leaves search.
- **AC-3** Given the budget page, then spend against the soft and hard limits is shown as numbers and a bar (never colour alone). A firm admin can set the budget within the plan limit, with fresh MFA. Practice leaders see it read-only.
- **AC-4** Given metering, then rows show engagement, agent and cost for the chosen day or month, sortable, with totals.
- **AC-5** Given support sessions, then a firm admin sees every session with its details, and can approve (fresh MFA), revoke and acknowledge, each confirmed. An unacknowledged emergency shows a banner on admin pages until acknowledged.
- **AC-6** Given walls, then opening the page prompts for fresh MFA when needed. Walls can be created and removed with confirmation, and API refusals (an own wall, a duplicate) show plain messages.
- **AC-7** Given every new screen, then loading, empty, error and not-allowed states exist, and colours come only from tokens (the SPEC-016 lint).

## 6. Behaviour and flows
Each screen fetches with the generated client. Mutations invalidate their lists. A 403 on an MFA action opens the "Confirm it's you" dialog (SPEC-016).

## 7. Domain and data changes
None.

## 8. Interfaces
Existing APIs only:
- `/v1/knowledge/*`;
- `/v1/budget` and `/v1/metering`;
- `/v1/support-sessions*`;
- `/v1/walls*`;
- `/v1/engagements` for names.

Gap: wall creation needs a person picker and a client picker. If no endpoint lists firm members and clients for admins, the spec adds two read routes (Q4).

## 9. Authorisation and tenancy
Unchanged. The UI hides what the matrix refuses, and the API remains the authority.

## 10. AI behaviour
None. Knowledge passages are firm documents, not model output.

## 11. Integrations
None.

## 12. Edge cases and failure modes
- **A failed knowledge document** shows its failure code in plain words, with a Withdraw button.
- **Metering for an engagement the admin can't see** shows the engagement's ID only.
- **Concurrent approval of a support session:** a 409 shows "already handled", and the list refreshes.

## 13. Security and privacy
- **Reasons:** support session reasons are shown only to firm admins (the API enforces this).
- **Fresh MFA** prompts are reused.
- **Plain text only:** no HTML rendering anywhere (OUT-001).

## 14. Audit trail and evidence integrity
None new. The APIs audit.

## 15. Observability
Unchanged.

## 16. Performance and scale
Small lists. Metering at month level means fewer than 1,000 rows.

## 17. UX
As in §4, in the SPEC-016 shell. Admin pages share a tabbed admin header.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-6 | component (vitest) | Each screen with a mocked client: lists, actions, confirmations, MFA prompt |
| AC-7 | lint plus component | Tokens only; empty and error states |

## 19. Rollout
No migration and no flag.

## 20. Open questions
- [ ] **Q1: navigation.** *Recommendation:* the rail gains Knowledge for everyone. Firm admin becomes one section with tabs (Methodology · Knowledge documents · Budget · Support access · Walls), each shown by role.
- [ ] **Q2: names in metering.** *Recommendation:* show the engagement's name where the admin can see it (from the engagements list), else "Engagement" plus a short ID. No new API.
- [ ] **Q3: emergency support sessions.** *Recommendation:* a persistent banner on all Firm admin pages until a firm admin acknowledges it, besides the notification.
- [ ] **Q4: pickers for walls.** *Recommendation:* add two small read routes:
  - `GET /v1/firm/members` (`wall.create`): staff names;
  - `GET /v1/firm/clients` (`wall.create`): client names.

  The alternative is typing IDs, which isn't usable.

## 21. Future / explicitly deferred
- Charts and trends for spend.
- Knowledge file uploads beyond text and Markdown.
- Dark mode.
