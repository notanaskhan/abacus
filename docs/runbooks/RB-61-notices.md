---
id: RB-61
title: Notices (N-04): the hand-off to a person at the IRS, a missed follow-up, escalation, OCR or the agent off, a re-sent envelope; the Dec 7 flip and its rollback
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-12-03
---
# RB-61 · Notices

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 to SEV2 (SEV1 if a response or a taxpayer ID reached the wrong person: go to RB-08) |
| Linked from | none yet (no notices alarm is wired; the respond-by watch reads the HOME-01 deadline tile) |
| SLO affected | none |
| Kill switches that apply | `notices.responder` per firm (every model call), the agent's stage per firm (`off`), the platform AI pause (ADR-140), OCR's route block and firm flag (RB-47); `notices.workspace` per firm until retired |
| Rehearse by | Fri Dec 3, 2027 (staging, PF-X1) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Notices v1 is frozen (`docs/contracts/notices.md`, snapshot `backend/tests/contracts/notices/v1.json`).
J09 P0 never depends on the agent: the code analysis and manual entry carry a notice from intake
to a sent response with `notices.responder` off. Every scenario below keeps that path open.

## 1. Recognise it

| Scenario | What you see | Confirms it, not a neighbour |
|---|---|---|
| **Hand-off to a person at the agency** (DUT, the IRS's "designated unit" or a named examiner takes the case) | An agency reply on NOT-02 names a person, a fax line or a phone call; the notice's next step isn't a letter | The reply's text on NOT-02 Activity; the notice stays `responded` or `escalated`, not `closed` |
| **Missed follow-up** | A notice past its respond-by on NOT-01 (`?respond_by=7` empty but the HOME-01 deadline row red), or an agency second notice arrives for an open one | `GET /v1/notices?status=` shows it open with `respond_by` in the past; NOT-01's duplicate check names the first notice |
| **Escalation** | A position of `disagree` on a balance over the firm's threshold, or an agency reply rejecting the response | NOT-02's position card decided `disagree`; the agency reply recorded with `escalated_reason` |
| **OCR off or failing** | NOT-01's intake sheet shows the fields empty with "Enter the details from the notice" and no "Agent" origin | RB-47's alarms, or the firm's OCR flag off; manual entry still saves |
| **The agent off or refused** | NOT-02 shows "Agent analysis is off for this firm" or the refusal in words | The firm's `notices.responder` flag, its stage (`agent_stages`), or the gateway's refusal reason in the audit (consent, terms, clearance) |
| **Re-sent envelope** | The response's signature envelope voided, declined or expired; a second envelope wanted | SIG-01 for the envelope; the response stays `in_signature` or returns to `approved` |

## 2. Contain

- **A response or a taxpayer ID went to the wrong person:** stop, go to RB-08. Void the envelope
  (SIG-01, Void) before anything else.
- **The agent says something wrong:** set the firm's stage to `off` (platform staff route,
  `PUT /v1/platform/agent-stages/{firm_id}/notices.responder` with stage `off` and a note), or the flag
  `notices.responder` off for the firm. Recorded answers stay on their runs; nothing already shown
  changes, and the code analysis stands.
- **OCR misreads:** RB-47 §2 (route block or the firm's OCR flag). Intakes fall back to manual
  entry; fields already confirmed by a person stay.
- **A missed respond-by:** nothing to switch off. Call the agency for an extension the same day,
  and record the call as an agency reply on NOT-02 so the respond-by and its trail move together.

## 3. Preserve

Before changing anything: the notice's id, its NOT-02 Activity (audit events), the response's
version and its envelope id, the analysis version and its `inputs_hash`, the agent run id if one
ran. Never copy the notice's text, the taxpayer's name or any ID into a ticket: name the notice by
its id and the firm by its pilot code.

## 4. Assess

- Which firm, which notice, which tax year; whether tax return information left the firm (it never
  should: the portal shows the client only the response and its payment confirmation).
- Whether a deadline is at risk: the agency's respond-by and any penalty date in the notice.
- For an agent answer: was it shown (stage `live`) or only recorded (`shadow`)? Shadow answers
  reach no one.

## 5. Notify

- The firm's notice owner and signer, the same day, for a missed follow-up or an escalation.
- The client, only through the firm, and only from the firm's own words (the response letter and
  the payment confirmation are the only client-facing pieces).
- For firm data reaching the wrong person: RB-27's 72-hour clock.

## 6. Recover

**Hand-off to a person at the agency.** Record the reply (NOT-02, Agency reply) with the person's
role and the channel, never their phone number in a note. Assign the notice's signer as owner. The
next contact is a person's call: the platform drafts nothing for it. Close the notice only when the
agency's closing letter is filed as its evidence.

**Missed follow-up.** Record the extension call as an agency reply with the new respond-by. If a
second notice arrived, attach it to the first (NOT-01 intake, Attach), never create a second
notice for the same matter. Draft the response as usual; the readiness line names the new date.

**Escalation.** The signer decides the position again if the agency's reply changes the facts
(NOT-02 Request decision). A draft made before the new decision reads `position_mismatch` until
regenerated (DEC-2392). If the matter leaves the notice path (an examination, an appeal), record
the reply, close the notice with `escalated_reason`, and open the work where the firm handles it.

**OCR or the agent off.** Nothing to recover in the notice: manual entry and the code analysis
carry it. Turn the agent back on only after the cause is known, and at `shadow` first if the cause
was a wrong answer.

**Re-sent envelope.** Void the old envelope on SIG-01 (if it isn't already voided, declined or
expired), then Send for signature again on NOT-03: a new envelope on the same approved response
version. A changed response needs a new approval first. The client sees only the live envelope.

**Rollback of the flip (Tue Dec 7, 2027, 19:00 CT).** Rollback is the flag off: `notices.workspace`
off for the firm hides the routes (404) and the screens (the C-20 "not turned on" state). Notices,
analyses, responses and envelopes persist; turning it back on shows them as they were. Until the
flags retire (held for the Thu Dec 16 batch), the flip is per firm, in the window, with both
founders' approval recorded in the firm's go-live dossier. After retirement the rollback is the
agent stage and the firm's AI policy for the responder, and a revert of the retirement PR for the
workspace.

## 7. Verify

- The notice reads the right state on NOT-01 and NOT-02, and its Activity names each step.
- For a re-sent envelope: SIG-01 shows one live envelope; the portal shows the client one.
- For the agent: a new analysis on a test notice at PF-X1 records as expected for the stage.

## 8. Review

Open the blameless review. A missed follow-up becomes a check on the HOME-01 deadline tile's
reminder lead time; a wrong agent answer becomes a suite case (`evals/notices_responder`).

## Onboarding a firm's open notices

At each pilot firm's onboarding (N-04 R18), before the Dec 7 flip:

1. The firm lists its open notices (agency, type, tax year, respond-by), no copies by email.
2. Each is uploaded through NOT-01's intake (upload or the firm's inbox), fields confirmed by a
   person, and the notice created against its client and engagement. Nothing is bulk-imported.
3. The dossier records the count loaded and the date; if the firm has none, the first real notice
   in December satisfies M15 and the dossier records that date.

There are no live pilot firms (DEC-1391): PF-X1 (synthetic) carries the Whitley CP2000 from its
seed, which is how the steps are rehearsed.

## Rehearsal log

| Date | Where | Who | Scenarios | Result |
|---|---|---|---|---|
