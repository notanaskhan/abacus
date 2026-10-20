# Vendor, partner and assurance tracker (F-09-T01)

Approvals, not code, set the critical path (chapter 06 §7.6, DEC-17). One row per application; no GitHub issues (decided 2026-10-20). Update the row when you file, hear back or slip. The builder files everything; Claude drafts the text.

Gates: **M1** Fri Oct 30, 2026 (every long-lead application filed) · **M2** Fri Nov 13 (R0 staging) · **M3** Fri Nov 20 (LOIs, first ledger) · **M4** Fri Dec 11 (R1 production) · **M7** Fri Apr 16, 2027 (real-data gate) · **M8** Fri May 28, 2027 (MVP, tax go/no-go) · **M11** Tue Aug 17, 2027 (tax pilot live).

Status words: `to file`, `filed`, `in review`, `approved`, `blocked`, `not needed`. "Vault" is an opaque reference to the item in your document vault (for example `V-012`), never the document itself.

## Never in git

This repository is public. Never put any of these in git, an issue, a pull request or a prompt:
- prices, quotes, budgets, envelope amounts or invoices;
- contract, order-form, DPA or LOI text;
- the name of a design-partner, prospect, auditor or pen-test firm;
- counsel's advice or drafts;
- account IDs, API keys, client secrets, recovery codes.

Record them in the vault and put only the vault reference here.

## Founding and planning (by Fri Oct 23 unless stated)

| Application | Needed for | Start | Needed by | Gate | Fallback if late | Status | Vault |
|---|---|---|---|---|---|---|---|
| Formation documents, founder agreement, IP assignments (F-09-T02) | contracts, vendor accounts | Oct 19 | Oct 23 | M1 | — | to file | |
| Year-one external spend plan: envelope by line, cash, runway (F-09-T03, DEC-03) | budgets, vendor choices | Oct 19 | Oct 23 | M1 | — | to file | |
| Counsel engagement letter, dated scope Nov 13, Nov 27, Dec 4, Dec 11, Jan 29, May 14, Aug 6 (F-09-T04) | MSA, DPA, 7216, Pub 1345, provider terms | Oct 19 | Oct 30 | M1 | — | to file | |
| Counsel-reviewed non-binding LOI template (F-09-T16) | design partners | Oct 26 | Oct 30 | M1 | — | to file | |
| Partner profile; at least 5 named firms per window; at least 6 conversations booked (F-09-T15) | pilots | Oct 19 | Oct 30 | M1 | — | to file | |

## Platform

| Application | Needed for | Start | Needed by | Gate | Fallback if late | Status | Vault |
|---|---|---|---|---|---|---|---|
| AWS Organizations, Control Tower, service quotas (Q-01-T01, SU-19) | everything | Oct 19 | Oct 30 | M1 | — | in progress | |
| Bedrock model access and TPM/RPM quota increases, US Geo profile, pinned models (SU-23) | all agent features; route parity | Oct 19 | Nov 13 | M2 | direct API on synthetic data only | to file | |
| Provider-terms Bedrock entry with counsel as second approver (ADR-114, SU-23) | any real-firm AI | Oct 26 | Dec 11 (draft); current at M7 | M4, M7 | agents off for real firms | entry drafted on a branch | |
| SES production access, platform and neutral domains, DKIM | every invite and email | Oct 26 | Nov 13 | M2 | none (blocks the portal) | to file | |
| WorkOS commercial check and order form (DEC-22) | sign-in | Oct 19 | Nov 13 | M2 | fake OIDC, synthetic staging only | to file | |
| Temporal Cloud account, namespaces, PrivateLink tier | everything | Oct 19 | Nov 6 | M2 | — | to file | |
| Sentry order form and DPA | error reporting | Oct 19 | Nov 13 | M2 | — | to file | |
| Better Stack order form and DPA (status page, paging) | on-call, status page | Oct 19 | Dec 11 | M4 | — | to file | |
| GitHub plan, DPA | the repository | Oct 19 | Oct 30 | M1 | — | to file | |
| Product domain, neutral portal domain (never contains "accrued"), mail domains; registrar MFA; DNS delegated to Route 53 (F-09-T09) | edge, email, portal | Oct 19 | Oct 30 | M1 | — | to file | |

## Ledgers, tax and practice

| Application | Needed for | Start | Needed by | Gate | Fallback if late | Status | Vault |
|---|---|---|---|---|---|---|---|
| Intuit developer account, production-keys assessment, App Partner tier, read-only scopes (F-09-T05) | QBO ledger, closes, CAS | Oct 19 | Jan 29, 2027 | M7 | QBO CSV/GL import (exists) | to file | |
| Wolters Kluwer CCH partner programme (F-09-T06) | tax workspace, CCH Axcess | Oct 19 | Jul 30, 2027 | M11 | CCH file bridge (record mode, P-18) | to file | |
| NetSuite SuiteCloud Developer Network and SuiteApp | group audits | only on discovery evidence | Apr 30, 2027 | M7 | NetSuite CSV import (exists) | not needed yet | |
| Xero app and certification | second ledger | only on discovery evidence | Mar 2027 | M7 | XLSX import (exists) | not needed yet | |
| Sage Intacct Marketplace partner and sender ID | P2 ledger | Jan 4, 2027 | Jun 2027 | M8 | CSV import (exists) | not needed yet | |
| Thomson Reuters partner (GoSystem, UltraTax) | only if design partners use them | after discovery | 2028 | — | file export | not needed yet | |

## Signatures, mail and identity

| Application | Needed for | Start | Needed by | Gate | Fallback if late | Status | Vault |
|---|---|---|---|---|---|---|---|
| Microsoft AI Cloud Partner Program enrolment; publisher verification of the Entra app (F-09-T07) | firm mailbox (Graph) | Oct 19 | Dec 11 | M4 | the firm forwards mail or uploads | to file | |
| DocuSign developer account and dated Go-Live checklist (F-09-T08) | signatures | Nov 2 | Jan 29, 2027 | M7 | record mode | to file | |
| DocuSign ID Verification (KBA) quote, then contract | 8879 family | Jan 4, 2027 | Mar 31, 2027 | M7 | wet signature and record mode | to file (quote now) | |
| Google OAuth verification and CASA Tier 2 | only if a design partner runs Google Workspace (decide by Nov 13) | Nov 16 | Feb 26, 2027 | M7 | manual forwarding | only on discovery evidence | |

## Assurance and insurance

| Application | Needed for | Start | Needed by | Gate | Fallback if late | Status | Vault |
|---|---|---|---|---|---|---|---|
| SOC 2 compliance tool (Drata; compare Vanta, Secureframe) (F-09-T13) | SOC 2 | Oct 26 | Nov 13 | M2 | — | to file | |
| SOC 2 auditor shortlist of 3 (never a design-partner or target firm), then engagement | Type I and II | Nov 2 | Dec 11 | M4 | — | to file | |
| Pen-test firm shortlist of 3, then booking | real-data gate | Dec 1 | Feb 15, 2027 | M7 | — | to file | |
| Cyber and tech E&O insurance | pilots, contracts | Nov 16 | Mar 31, 2027 | M7 | — | to file | |
| Security questionnaires (SU-27) | vendor reviews, partner due diligence | Oct 26 | Oct 30 | M1 | — | to file | |
