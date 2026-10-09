---
id: SPEC-025
title: "Act 1: the engagement opens"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-026, ADR-050, ADR-052]
related_specs: [SPEC-002, SPEC-008, SPEC-015, SPEC-017, SPEC-018, SPEC-020, SPEC-022, SPEC-024]
created: 2026-10-09
updated: 2026-10-09
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
**Act 1 promise:** a senior or manager opens an engagement in minutes, because Abacus proposes almost everything and they confirm it.

**Story** (Maya, a manager; Halvorsen, a client audited last year; Rachel, its controller: illustrative people, not data):
1. Maya creates the fiscal 2026 engagement for an existing client.
2. Abacus proposes the team, the template and a request list rolled forward from what was actually used last year. A new client starts from the firm's template for that engagement type.
3. Before anyone touches client data, acceptance is recorded, each team member confirms their independence, and the client is checked against ethical walls.
4. The signed engagement letter is recorded (signed in the firm's own tool; Q2).
5. Maya invites Rachel, and the invitation goes out in the firm's name.

**What the standards require:**
- **Acceptance or continuance, every year:** a full investigation for new clients and a reconsideration for continuing ones. The engagement partner takes overall responsibility.
- **Independence:** the partner can show a conclusion on compliance with independence requirements.
- **Agreed terms:** an engagement letter, preferably before the work begins. A continuing engagement doesn't necessarily need a new letter each year.

**The founder's direction:**
- *Record, don't rebuild:* firms already run acceptance, independence and letters in their methodology binder and practice-management tools.
- *Build* engagement creation, staffing, the request list and the client invitation.

## 2. Problem and context
**What exists:**
- creating an engagement (name, client, entity, period, type);
- the team (SPEC-017);
- the request list from the firm's template (SPEC-008) or an Excel import (SPEC-018), with classification (SPEC-022);
- client invitations (SPEC-015);
- ethical walls (SPEC-002), enforced on every request.

**What's missing:**
1. **There's no "existing client".** Every new engagement creates a new client record, even with the same name. That breaks roll-forward, and it **weakens walls**: a wall on last year's Halvorsen doesn't cover a second Halvorsen record. This is a correctness gap regardless of Act 1.
2. **No roll-forward:** no link to last year's engagement, and no proposed team or proposed list from what was used.
3. **No acceptance or continuance record,** and no partner decision.
4. **No independence confirmations.**
5. **No engagement letter record.**
6. **No gate** between "the engagement exists" and "client data flows".
7. **Invitations don't carry the firm's name:** the email says "an audit engagement".

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Manager or senior (the story's Maya) | Creates the engagement, confirms proposals, records the letter, invites the client |
| Engagement partner | Records the acceptance or continuance decision (overall responsibility) |
| Each team member | Confirms their independence for this client |
| Abacus (code) | Proposes the team, template and rolled-forward list; checks walls; asks for confirmations; gates client data |
| Client controller (the story's Rachel) | Is invited once the gate opens; signs the letter (Q2) |

## 4. Goals and non-goals
**Goals**
- **Clients you already have (Q1):**
  - "New engagement" starts by picking a client: search the firm's clients, or "New client";
  - for an existing client, pick an existing entity or add one;
  - a possible duplicate (the same name, ignoring case and punctuation) is flagged before a new client is created.
- **Roll-forward proposals (code, Q3).** When the client and entity had an engagement of the same type for the prior period, Abacus proposes:
  - **team:** last year's staff team with the same roles, minus anyone no longer active or now walled from the client;
  - **template:** the methodology template last year used, at its latest version;
  - **request list:** last year's items that were **actually used**, carried over with their area, tier and client visibility. *Actually used* means **the item has accepted evidence**. Every other item, including those marked not applicable or waived, is listed separately and not ticked. Items the latest template adds are flagged "new in the template".

  Maya reviews each part (tick, untick, change roles) and confirms. Nothing is created until she does. A new client gets the firm's template for that type, as today.
- **Acceptance and continuance record:**
  - per engagement: new client or continuance (pre-filled), decision (`accepted` or `declined`), decided by (must be the engagement partner), when, and where it's documented (a binder reference, plus an optional uploaded file);
  - for a new client, optionally the **predecessor auditor** (firm name) and the **date communicated** with them;
  - recorded, not performed: Abacus doesn't hold the acceptance forms;
  - `engagement.acceptance.record`, partner only (Q5); audited.
- **The engagement partner's independence conclusion:** the partner records their conclusion on compliance with independence requirements for the engagement (with the date and where it's documented). It's audited, and needs fresh MFA.
- **Independence confirmations:**
  - when the team is confirmed (and when anyone joins later), each staff member gets a task: "Confirm your independence for Halvorsen, FY2026";
  - they confirm with a fixed statement, or decline with a note that goes to the partner;
  - the engagement shows who has and hasn't confirmed;
  - walls are checked at the same time: anyone walled from the client is flagged and can't be added (already enforced).
  - Each confirmation is recorded and audited (`independence.confirm`, self only).
- **Engagement letter (Q2):**
  - record the status (`not_started`, `sent`, `signed`, or `not_required_this_year` with a reason), the date, and the signed copy uploaded (stored as evidence-grade, write-once) or a link to where it lives (Ignition, Karbon, the DMS);
  - `engagement.letter.record` (partner, manager); audited.
- **The gates before client data (Q4, as amended):**
  - **The engagement opens** when acceptance is `accepted` and the engagement partner has concluded on independence. Until then, client invitations, connections, retrievals and client uploads are refused for everyone, with the reason.
  - **Each person opens individually:** a team member's own access to client data (evidence content, client uploads, retrievals, the client's request items) opens only when they confirm their independence. Until then, that person sees the engagement's setup but not client data.
  - **Adding someone later restricts that person, not the engagement.**
  - **The letter warns** if missing but doesn't block, since the standards say "preferably". The firm can make it blocking.
- **Invitations in the firm's name (Q6):** the subject and body name the firm ("Whitfield & Lane invites you to their audit of Halvorsen"), the sender's display name is the firm's, and the portal shows the firm's name. Logos stay deferred.
- **Engagement setup screen**, one page per engagement, made of three parts. It's the default tab until the engagement opens.
  - **A narrative summary:** for example, Halvorsen FY2026 audit (continuance): waiting for Dana to record continuance; 3 of 5 have confirmed independence.
  - **A status checklist:** client and period, team, request list, acceptance, the partner's independence conclusion, each member's independence, letter, client contacts. Each step shows its state and who acts next.
  - **A plain reason on every blocked item:** for example, client invitations open once the engagement partner records acceptance.

**Non-goals**
- Performing acceptance, independence or conflicts procedures inside Abacus (recorded only).
- Building e-signature (Q2).
- The AI continuance brief, and AI-proposed request-list changes (add items for known changes, re-tier). Those come later, with an evaluation suite (Q3).
- Integrations with Ignition or Karbon (later).

## 5. User stories and acceptance criteria
- **AC-1** Given an existing client, when someone creates an engagement, then they pick that client and entity, and no duplicate client is created. A likely duplicate is flagged before a new client is made.
- **AC-2** Given a prior-period engagement of the same type for that entity, then Abacus proposes:
  - the team, without inactive or walled people;
  - the template at its latest version;
  - the used items, with unused ones unticked and template additions flagged.

  Nothing is created until a person confirms, and what they confirm is exactly what's created.
- **AC-3** Given a new client, then the proposal is the firm's template for the engagement type, and no team beyond the creator.
- **AC-4** Given an engagement, then only its engagement partner can record acceptance or continuance (decision, where documented, an optional file, and for a new client an optional predecessor auditor and date communicated), and their independence conclusion. Both are audited. A declined engagement stays closed to client data.
- **AC-5** Given a confirmed team, then each member is asked to confirm independence, can confirm or decline (with a note to the partner), and the engagement shows each person's state. Anyone who joins later is asked too.
- **AC-6** Given an engagement letter, then its status, date and signed copy or link are recorded and audited, and "not required this year" needs a reason.
- **AC-7** Given acceptance isn't `accepted` or the partner hasn't concluded on independence, then client invitations, connections, retrievals and client uploads are refused for everyone with a plain reason. Given the engagement is open, a team member who hasn't confirmed independence is refused client data, while confirmed members are not. Adding someone later restricts only them.
- **AC-8** Given a client invitation, then its email and the portal name the firm and the engagement, never "Abacus" alone.
- **AC-10** Given the setup page, then it shows a narrative summary, the status checklist, and a plain reason on every blocked item.
- **AC-9** Given every new screen, then loading, empty, error and not-allowed states exist, and colours come only from tokens.

## 6. Behaviour and flows
1. Maya opens New engagement, picks Halvorsen and its entity, FY2026, audit. Abacus finds FY2025 and shows the proposal: 5 team members (1 removed: left the firm), the template "Audit core v4" (v3 was used last year), 62 of 75 items used, 13 unused (unticked) and 3 new in the template.
2. She confirms. The engagement, team and request list are created, and independence tasks go to the 5.
3. The partner records continuance: accepted, binder reference "PPC 1-200".
4. All 5 confirm independence. The letter is recorded as signed, with the uploaded PDF.
5. The gate opens. Maya invites Rachel; the email comes "from Whitfield & Lane".

## 7. Domain and data changes
- **`engagements.prior_engagement_id`** (nullable, same client entity).
- **`engagement_acceptance`:** engagement, kind (`new_client` or `continuance`), decision, decided by, decided at, documented at (text), file (evidence-grade object, optional), predecessor auditor (optional), date communicated (optional), and the partner's independence conclusion (concluded by, at, documented at). One per engagement; a new decision supersedes the old.
- **`independence_confirmations`:** engagement, user, status (`requested`, `confirmed` or `declined`), statement version, note, at.
- **`engagement_letters`:** engagement, status, date, reason, file or link.
- **`firms.require_letter_before_client_data`:** boolean, default false (Q4).

## 8. Interfaces
- `GET /v1/clients?search=` (the client picker; `engagement.create` roles);
- `POST /v1/engagements/proposal` (the roll-forward or template proposal, nothing stored);
- `POST /v1/engagements` (extended: existing client and entity ids, prior engagement, confirmed team, confirmed items);
- `PUT …/acceptance`;
- `GET`/`POST …/independence` (list; confirm or decline for oneself);
- `PUT …/letter`;
- `GET …/setup` (step states).

## 9. Authorisation and tenancy
New matrix actions:
- `engagement.acceptance.record` (engagement partner, fresh MFA);
- `independence.confirm` (any staff role on the engagement, for themselves only);
- `engagement.letter.record` (partner, manager);
- `client.read` (the picker: `engagement.create` holders).

The gate is enforced server-side, in the services behind each client-data action.

## 10. AI behaviour
None in this spec (Q3). The roll-forward is deterministic code ("last year's team is a copy, not a judgement"; "used" is a fact). Later: a continuance brief, and proposed request-list changes, as model proposals a person approves (ADR-005), with an evaluation suite.

## 11. Integrations
None now. Letters link out to Ignition, Karbon or a DMS by URL. Integrations come later (Q2).

## 12. Edge cases and failure modes
- **Last year's engagement had a different type:** no roll-forward; the template proposal is offered instead.
- **Two prior engagements match:** the latest by period end is proposed, with a choice.
- **A team member leaves after confirming:** their confirmation stays as history.
- **Someone joins later:** a new request; only that person is restricted until they confirm (Q4).
- **Acceptance is declined:** the engagement shows "Declined" and stays closed to client data; it can be archived.
- **A continuance with no letter this year:** `not_required_this_year` with a reason.

## 13. Security and privacy
- **Uploaded files:** acceptance files and signed letters are stored write-once and never rendered in the app (SPEC-021 Q1), and malware scanning applies once it exists.
- **Independence notes:** visible to the partner and manager only.

## 14. Audit trail and evidence integrity
`client.selected`, `engagement.rolled_forward`, `engagement.acceptance_recorded`, `independence.requested`, `independence.confirmed`, `independence.declined`, `engagement.letter_recorded`, and `client_data.gate_refused` (with the action).

## 15. Observability
Time from "New engagement" to the gate opening (the Act 1 promise); how far the proposal was changed before confirming (the share of proposed items kept).

## 16. Performance and scale
A proposal reads one prior engagement (up to 2,000 items) in one request.

## 17. UX
- "New engagement" becomes a short wizard: client, period and type, proposal review, confirm.
- The engagement opens on **Setup** until the gate opens, then on Overview.
- Independence tasks appear in each person's notifications and on a "Your confirmations" card on the engagements page.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 | integration | Picking an existing client; the duplicate flag; walls cover the engagement |
| AC-2, AC-3 | unit and integration | Proposal rules (used vs unused, inactive or walled people, template version) |
| AC-4 to AC-6 | integration | Records, roles, audit |
| AC-7 | integration | Every client-data action refused until the gate opens, then allowed |
| AC-8 | unit | Invitation copy names the firm |
| AC-9 | component (vitest) | Wizard, setup page, independence card, states |

## 19. Rollout
- Migrations in engagements, organisations and identity.
- **Existing engagements:** treated as accepted, with independence confirmed by migration (recorded as "before Act 1"), so nothing in use is suddenly blocked (Q7).

## 20. Open questions
None. Answered by the founder on 2026-10-09: all recommendations, with these amendments:
- **Q4:** independence is gated per person (see §4).
- **Q8:** the order is a, c, d, then b, and b is narrowed.
- **"Actually used":** defined as an item with accepted evidence.
- **Acceptance record:** gains the predecessor auditor fields.
- **Setup page:** a narrative summary, a status checklist and a reason on every blocked item.
- **Q2:** follow the table; no e-signature.

- [x] **Q1: duplicate clients already created.** *Recommendation:* from now on, new engagements pick an existing client. Existing duplicates aren't merged automatically: a "possible duplicate" note shows on the client, and merging comes later.
- [x] **Q2: e-signature. Your story and your table disagree.** The story has Rachel "sign it electronically"; the table says "don't build e-signature; record status and signed copy; integrate with Ignition or Karbon later". *Recommendation:* follow the table. Record the letter's status, date and signed copy or link, and treat "Rachel signs online" as happening in the firm's existing tool. The story's wording would become "the signed letter is recorded". Building e-signature is a regulated product of its own, and firms already have it.
- [x] **Q3: what the "agent" proposes in Act 1.** *Recommendation:* the proposals (team, template, used items) are deterministic code and labelled "Abacus proposes". The AI parts named in your table (continuance brief; add items for known changes; re-tier) come later, each with an evaluation suite. This matches ADR-050 and your own "copy, not a judgement" note.
- [x] **Q4: how hard the gate is.** *Recommendation:*
  - acceptance and every member's independence block client invitations, connections, retrievals and client uploads;
  - the letter only warns (the standards say "preferably"), with a firm setting to make it blocking;
  - a person added later closes the gate for client-data actions until they confirm.
- [x] **Q5: who records acceptance.** *Recommendation:* the engagement partner only (the standards put overall responsibility on them), with fresh MFA. Managers can prepare the record (documented at, file), but only the partner sets the decision.
- [x] **Q6: invitations in the firm's name.** *Recommendation:* the firm's name in the subject, body and sender display name; the sending address stays Abacus's until custom email domains exist (with SES, TASK-014).
- [x] **Q7: engagements created before Act 1.** *Recommendation:* the migration marks them "accepted, before Act 1" and their current team's independence "confirmed, before Act 1", visibly labelled, so live work isn't blocked. New engagements follow the gate.
- [x] **Q8: build order (as amended).** Four tasks, in this order:
  - **(a)** clients you already have, plus invitations in the firm's name (the walls gap first);
  - **(c)** acceptance, the partner's independence conclusion, per-person independence, the letter and the gates;
  - **(d)** the setup screen;
  - **(b)** narrowed to "New engagement offers the firm's template for its type". **Rolling forward from last year's engagement comes after the setup page**, as its own task.
- [x] **Q9: protected paths.** Each task's approval file will be listed up front, including the generated `identity/authz/_matrix.py` for the new matrix actions.

## 21. Future / explicitly deferred
- AI continuance brief; AI request-list changes (with evaluation suites).
- Ignition and Karbon integrations; e-signature if ever.
- Merging duplicate clients; firm logos and custom email domains.
- Conflict checks beyond walls (for example, the same staff doing this client's bookkeeping).
