# M8 · Tax-pilot go/no-go memo (Fri May 28, 2027)

Chapter 01's M8: tax **GO** only if (a) S7–S14 throughput is at least 95% of plan; (b) at least one
tax partner is signed for 5–15 extended returns and its CCH Axcess admin validated the file format
in Pilot 0; (c) counsel-approved §7216 consent text naming AWS Bedrock, and the DocuSign ID
Verification contract signed (since ADR-342: DocuSeal KBA accepted for the 8879 family); (d) M10 on track. **NO-GO:** S16–S21 capacity goes to EBP workpapers
and audit completion by Oct 15 (or A-09 for Dec-2027 year-ends if an audit partner commits a group
audit and throughput is at least 110%); tax targets the 2028 extension season.

This memo records criteria **(b)** and **(c)** (F-09-T125). (a) and (d) come from the sprint plan's
calibration and the M10 gate. The memo holds results and vault references only: never a partner's
name, contract or consent text, or counsel's advice (the repository is public).

## Criterion (b): a tax partner and the CCH format

| # | Item | Evidence (where it lives) | Due | State |
|---|---|---|---|---|
| b1 | At least one tax partner signed an addendum for 5–15 extended 1065 and 1040 returns | the signed addendum (vault `V-…`); the pilot code (`PF-T1`) | Fri Apr 30, 2027 (F-09 F5) | — |
| b2 | The partner's CCH Axcess admin named | the vault entry | Fri Jan 22, 2027 | — |
| b3 | The admin imported Accrued's synthetic CCH export and exported diagnostics back; differences logged and closed | the TAX-09a–e session notes (vault); the differences list, each closed | Pilot 0 tax sessions, Apr–May | — |
| b4 | The admin's written sign-off on the file format | the sign-off (vault), F-09-T120 | Fri May 14, 2027 | — |
| **b** | **Met** when b1 and b4 are filed (b2, b3 lead to b4) | — | Fri May 28 | **not recorded** |

## Criterion (c): §7216 text and identity verification (KBA)

| # | Item | Evidence (where it lives) | Due | State |
|---|---|---|---|---|
| c1 | Counsel approved the §7216 consent text: two documents (use; disclosure to AI sub-processors naming AWS Bedrock), one purpose each (Rev. Proc. 2013-14) | counsel's approval (vault); the template keys in the product's database, never in git | Fri May 14, 2027 (F-09 D5) | — |
| c2 | DEC-25's route is the provider (DocuSeal with provider-hosted KBA, ADR-342 and DEC-1275; was DocuSign), decided at its go/no-go | DEC-25's and DEC-1275's rows in `docs/product/decision-log.md` | Fri Dec 4, 2026 | — |
| c3 | DocuSeal KBA accepted for the 8879 family: DocuSeal's written method on file and counsel's Pub 1345 acceptance (F-09-T97; was the DocuSign ID Verification contract) | DocuSeal's written answer and counsel's acceptance (vault) | Wed Mar 31, 2027 (F-09 B3) | — |
| **c** | **Met** when c1 and c3 are filed (and c2 chose the provider route) | — | Fri May 28 | **not recorded** |

## Decision (Fri May 28, 2027)

| Criterion | Met | Recorded by | Note |
|---|---|---|---|
| (a) throughput ≥ 95% of plan (S7–S14) | — | N | from the sprint plan's calibration #3 |
| (b) tax partner and CCH format | — | AY | above |
| (c) §7216 text and ID Verification | — | AY | above |
| (d) M10 on track | — | N | `docs/ops/gates/M10-client-facing.md` |
| **Tax pilot** | **GO / NO-GO** | both founders | a DEC row in `docs/product/decision-log.md` records it the same day |
