---
id: RB-45
title: K-1 invitation bounce and resend; a mis-released K-1
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-08-27
---
# RB-45 · K-1 invitation bounce and resend; a mis-released K-1

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | Bounce: SEV3. Mis-release (a K-1 visible to the wrong person): SEV2, and SEV1 if it crosses firms (then RB-08) |
| Linked from | TXP-12 B ("Invite email bounced — update address"); the incident register |
| SLO affected | none |
| Kill switches that apply | `tax.k1_release` (per firm) |
| Rehearse by | Fri Aug 27, 2027, on staging with the synthetic test firm, before Flip 2 (RB-44 §5) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

## A. Bounce and resend
1. **Recognise:** TXP-12 B shows the row "Invite email bounced — update address".
2. **Fix the contact:** correct the delivery contact's email on the issuing client (CLI-04). Never
   paste an address from the bounce message; confirm it with the client.
3. **Resend:** TXP-12 › the row › Resend K-1 (`POST /v1/k1-packages/{id}:resend`): the corrected
   contact is recorded and the release workflow sends a new invitation. The old link stays dead.
4. **Verify:** the row leaves the bounced state; the recipient's first read moves it to Viewed.

## B. A mis-released K-1
1. **Within ten seconds:** Undo on the release toast (`POST /v1/k1-releases/{id}:undo`). Nothing
   reached anyone; stop here.
2. **Contain (after the window):** turn `tax.k1_release` off for the firm (RB-44 §5 rollback): the
   portal K-1 routes answer 404 for everyone in that firm at once. Then revoke the wrong person's
   portal access to that client (CLI-04 › Revoke…). A route to revoke one package's
   `k1_recipient` grant alone is not built yet (open T-02 item); until then the client-level
   revoke is the containment.
3. **Preserve:** the package's access events (every read and download is logged per person) and
   the release record. Export them to the incident; never copy the K-1 itself.
4. **Assess:** who read or downloaded what, when (access events), and whether the TIN last four or
   amounts were exposed (amounts need the portal second step).
5. **Register:** open an incident in the incident register (Security center) with the FTC clock
   for the firm; the firm decides on client notification with counsel (text never in git).
6. **Supersede:** import the corrected K-1 set; each released recipient gets a new version naming
   the old (`supersedes_package_id`, "Superseded (amended K-1)"), and a person releases it.
7. **Recover:** flag back on for the firm once the corrected set is released and the wrong grant
   is gone; verify the right recipient sees "Superseded (amended K-1)" on the old package.
8. **Review:** blameless review; typical actions: a release check that names each recipient's
   delivery contact before the grant, and the package-level revoke route.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
