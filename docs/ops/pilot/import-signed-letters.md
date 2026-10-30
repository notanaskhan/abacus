# Onboarding note: importing a firm's existing signed letters (record mode)

N-02-T17 (C7 record mode, frozen v1, DEC-820; SIG-01 "Import signed package…"). Before Accrued sends
anything for signature (DocuSign arrives for pilot firms at M11, Tue Aug 17, 2027), every signed
document a firm relies on is **imported**: the completed file and the provider's certificate, with
who signed, when and how. M10 (Tue Jul 13, 2027) needs a pilot firm's engagement letters at least in
record mode. This note is for the firm's admin or engagement partner, walked with AY; it holds no
firm or client names.

## Who and where
- People with `envelope.import_record` (firm admin, engagement partner, manager), in SIG-01 with
  `signatures.envelopes` on for the firm. Agents and the platform cannot import (the matrix denies
  them).
- One package per signed document: SIG-01 → **Import signed package…**.

## What each package needs
| Field (sheet) | What to give | Notes |
|---|---|---|
| Client | the client the document belongs to | the signers must be that client's contacts |
| Type | Engagement letter, §7216 consent or Other | M10's row counts engagement letters |
| Title | the document's own title | |
| Signed in | the tool it was signed in (the firm's e-sign product, or "Wet signature") | free text; never a credential |
| Signers | each signer (a contact of the client), the day they signed, the identity check used | add one row per signer, up to 20 |
| Signed document | the completed PDF | scanned before it is stored; refused closed |
| Certificate | the provider's completion certificate, if it has one | optional for a wet signature |
| Attestation | "I confirm these documents were signed by the people listed, on the dates shown." | required; the import records who attested |

The envelope lands under **Completed** with its evidence (the files, the signer facts and the
attestation), read-only: record-mode envelopes are never resent, reminded or voided as if Accrued
had sent them.

## Order for a pilot firm
1. Before go-live (pilot-onboarding §5 onward): the firm lists the letters in force for the
   engagements entering the pilot (PW1: 1–3 per audit partner).
2. Import each one; check SIG-01 shows it Completed and the drawer's evidence opens.
3. Record the count in the dossier's Content section (`docs/ops/go-live/<pilot-code>.md`): imported
   letters versus engagements in scope. M10's gate row is green when every engagement in scope has
   its letter in record mode (`docs/ops/gates/M10-client-facing.md`).

## When something fails
- "The package wasn't imported": the file was refused (type, size, the scanner) or a signer is not
  a contact of the client. Fix and import again; a failed import leaves nothing behind.
- The e-sign vendor or KBA is down: nothing in record mode depends on it; see RB-18.
