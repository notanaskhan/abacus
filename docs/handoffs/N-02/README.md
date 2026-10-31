# N-02 hand-off notes (N-02-T45)

N-02 (envelopes and e-signature) hands over C7 **v1.1, frozen** (`docs/contracts/c7-envelopes.md`,
DEC-1666): record mode, DocuSeal sending behind W7 (ADR-342), the portal signing view, the evidence
package with its retention and nightly re-hash, envelope policies and the handwritten fallback.
Each note says what a consumer epic receives, the seam it plugs into, and what N-02 left to it.
Link the note from the consumer epic's issue; the epic's owner acknowledges it in the table's last
column (the row's acceptance).

| Epic | Note | Seam | Acknowledged |
|---|---|---|---|
| A-07 | [A-07.md](A-07.md) | `rep_letter`, `governance_letter` sources; G7 | — |
| N-04 | [N-04.md](N-04.md) | `notice_response` source; joint signing | — |
| T-01 | [T-01.md](T-01.md) | `consent_set`, `tax_return` (8879 family); supersede; retention | — |
| T-02 | [T-02.md](T-02.md) | `envelope_summaries_for` (TAX-01 signer chips) | — |
| I-01 | [I-01.md](I-01.md) | gate kinds, "Signatures out", activity events | — |
| R-02 | [R-02.md](R-02.md) | signed copies as `signed_copy` deliverables (C10) | — |
| W-01 | [W-01.md](W-01.md) | the DocuSeal `firm_integrations` row for WB-10 | — |
| X-01 | [X-01.md](X-01.md) | `system_description_approval` source | — |

Writing a source: `.claude/skills/backend-module/SKILL.md` "Registering an envelope source and a
gate". Runbook: RB-18. The countersignature session (N-02-T28) and POR-06 part 2 (N-02-T29) are part of v1.1.
