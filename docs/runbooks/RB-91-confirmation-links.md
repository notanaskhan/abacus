---
id: RB-91
title: "Confirmation respondent links (A-08): revoke one link, the kill switch, reissue, suspected phishing, OTP spikes, expired bursts, JE scoring duration"
owner: builder
owning_epic: A-08
alarms: [confirm-code-failed-spike, confirm-expired-burst, je-scoring-p95]
last_rehearsed: never
rehearse_by: 2028-08-25
---
# RB-91 · Confirmation respondent links (A-08)

| Field | Value |
|---|---|
| Owner | ayushkbhatia (`audits.confirmations` registry owner) |
| Surface | The public family `/v1/confirm/{token}…` (POR-17), one link principal per confirmation (ADR-146 P-09, the ADR-152 amendment) |
| Kill switch | `confirmation_links` (P-66, ADR-157), per firm or platform-wide; nothing resolves while it is on, and every link answers the uniform expired view |
| Flags | `audits.confirmations` (firm routes), `audits.fieldwork_agents` (reconciliation runs) |
| Alarms | `abacus-staging-confirm-code-failed-spike`, `abacus-staging-confirm-expired-burst`, `abacus-staging-je-scoring-p95` (`infra/envs/staging/confirmation_links.tf`) |
| Edge | WAF rule 0 (chapter 06 rule 6) counts `/v1/confirm/{token}/code` and `/code/verify` with sign-in: 30 per 5 minutes per IP, then 429. The API locks a link for 15 minutes after five wrong codes |
| Pen test | POR-17 and the public family are in the Nov 2028 delta pen-test scope (W-01-T20 / Q-03 lane; DEC-1389 defers pen tests until then) |

Nothing in a log line, alarm or ticket carries a token, a code or an address. Quote the
confirmation number (C1, C2…) and the engagement, never the link.

## 1. Revoke one link
1. On AUD-14 open the confirmation and choose **Revoke link** (a person with
   `confirmation.send`; audited `link_principal.revoked`).
2. The respondent's next request answers the uniform expired view; the page credential stops at
   once (the credential resolves through the same principal).
3. Record why in the confirmation's note (not in the ticket).

## 2. Pause every respondent link (the kill switch)
Target: every link paused in **under 5 minutes** from the decision (the staging drill measures it).
1. Run as the `abacus-ops` one-off task (never from a laptop against a hosted database):

   ```
   python -m abacus_tools.platform_control set --control confirmation_links --scope platform \
       --on --operator <handle> --reason "<incident id>: pause respondent links"
   ```

   For one firm: `--scope firm --tenant <tenant_id>`.
2. Wait for the controls cache (10 seconds), then open any live link on staging: it reads the
   uniform expired view; `POST …/code` still answers 202 after the padded floor and sends nothing.
3. Note the start and end times; the drill's elapsed time is the `set` call to the first expired
   view. Log it in the task file of the drill (Q-04 rehearsal row) with the operator handle.
4. Turn it off the same way with `--off` once the cause is fixed; links resolve again within 10
   seconds. Links that expired meanwhile stay expired (reissue them, §3).

## 3. Reissue
1. A person opens the confirmation on AUD-14 and chooses **Send again** (a new link principal; the
   old one is revoked in the same act). The respondent gets a new email from the firm's template.
2. A response already received is never reopened; reissue only an unanswered confirmation.

## 4. Suspected phishing (a respondent forwards a look-alike email)
1. Pause the firm's links (§2, `--scope firm`).
2. Compare the forwarded sender and link host with the firm's sending domain and portal host
   (ADM-01). A link not on the firm's portal host is not ours: tell the firm, keep links paused.
3. If the email is ours but unexpected, revoke the confirmation's link (§1) and reissue after the
   firm confirms the respondent's address through an address verification (AUD-14).
4. Record the incident (SEV2 if any respondent typed a code into a look-alike page).

## 5. Alarms
- **OTP failure spike** (`confirm-code-failed-spike`, over 25 failures per 5 minutes, two
  periods): read the WAF's `auth-and-code-rate` blocks first. A single IP is guessing (the WAF and
  the five-try lock hold it); many IPs on one firm's links: §4. Pause if codes are being phished.
- **Expired-view burst** (`confirm-expired-burst`, over 100 per 5 minutes): check whether the kill
  switch is on (`platform_control list`); if it is off, someone is enumerating tokens (the views
  are uniform, so no token is learned) or a mailing went out with stale links: reissue.
- **JE scoring p95** (`je-scoring-p95`, over 15 minutes): the scoring workflow is on the
  background class; check the worker queue depth and the population size before scaling.

## 6. Canary flip and rollback (A-08 §1 flag plan)
1. Staging on in S47–S49; canary **Tue Sep 19, 2028** on the synthetic canary (PF-X1, DEC-4100):
   `audits.confirmations` on, one confirmation sent to a synthetic respondent, J04 step 9 walked.
2. Per-firm flips **Tue Oct 24** (firms live on EBP/tax), **Tue Oct 3** for audit-only firms.
   Real respondent links only after the Nov 2028 delta pen test (**Tue Dec 5**).
3. Rollback: the kill switch first (§2), then the flag off for the firm. Nothing is deleted:
   confirmations and responses stay; links resume when the switch is off.
