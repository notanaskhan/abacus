# TPL-16 · Signing ceremony specimen · Form 8879, Dev & Mira Kapoor

| Field | Value |
|---|---|
| Route and params | Gallery only: `/components/specimens/tpl-16?st=a…g&as=mira-kapoor&clock=2026-09-14T09:24:00-05:00`. Production twin POR-06 `/sign/$envelopeId` (N-02) |
| Template and host frame | T16 · `Wave 0 - Templates.dc.html#tpl16`; 390 frame is T7-M |
| Surface | portal (white-labelled; no Accrued name or mark) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-16 Signing ceremony specimen - Form 8879- Dev and Mira Kapoor/` (README.md, spec.md; no revision.md) · HANDOFF_VERSION 2026-10-21 sha256:9308819d |
| Epic and tasks | F-06 · F-06-T01 contract; F-06-T02 seed (envelope E6); F-06-T04 b and d; F-06-T05 a, c, e, f; F-06-T06 g; F-06-T07 AC suite; F-06-T13 lock |
| Manifest status | planned (twin POR-06, N-02) |

Code: specimens `apps/web/src/gallery/specimens/TPL-16/` over `apps/web/src/fixtures/seed/tax/envelopes.ts` (E6). Copy keys: `apps/web/src/gallery/specimens/TPL-16/copy.ts`.

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a · Identity verification | `mira-kapoor` | E0 Mon Sep 14, 2026, 9:24 AM CT | E0 | E6; Mira's signer `sent`, `method: kba`; in production `signingSession` present and the provider frame hosts KBA. **Superseded (DF-12, §11.2 Q2):** the native KBA card ("Question 2 of 4", 2:00) is a Tier C screenshot specimen only | deferred (Tier C screenshot) |
| b · Signing (default) | `mira-kapoor` | E0 | E0 | E6: Dev `signed` Sep 9, 6:12 PM; Mira `verified` 9:21 AM with the spouse PIN and spouse signature open on Form 8879 and TR-579-IT ("2 fields left"); `signedCount 1`, `signerCount 2` | built in F-06-T04 |
| c · Adopt signature | `mira-kapoor` | E0 | E0 | b with the adopt step open. **Superseded (DF-12):** provider-hosted in production; the native 560 dialog (Gelasio italic, consent checkbox) is a Tier C screenshot specimen | deferred (Tier C screenshot) |
| d · Completed | `mira-kapoor` | E0 | E0 | both signers `signed`; envelope `completed`; `evidence` six rows (Signed, Method, Identity, IP address, Login, Documents) | built in F-06-T04 |
| e · Verification failed | `mira-kapoor` | E0 | E0 | Mira's signer `verification_failed`, envelope kind 8879 family. **Superseded (DF-11):** the artboard's "try again tomorrow at 9:24 AM" is replaced by the paper-form text; no retry, no countdown, no other method; Dina Sato named | built in F-06-T05 |
| f · Decline | `mira-kapoor` | E0 | E0 | b with the Decline dialog open (four reasons + note) | built in F-06-T05 |
| g · 390 | `mira-kapoor` | E0 | E0 | b at 390 × 844: header 56, step chips, full-width page, sticky bar 64 | built in F-06-T06 |
| pending confirmation | `mira-kapoor` | E0 | — | return event present, Mira's signer still unsigned on refetch (`?st=pending`) | built in F-06-T05 |
| loading, error, restricted | — | E0 | — | as T16 | F-06-T04 |

## API
As T16: C7 envelope view and signing session (N-02). The kit performs no write; Sign, Decline and Download are callbacks. Human-only: sign and decline, under N-02's signer action.

## Status
`envelope`: `partially_signed` "1 of 2 signed" (amber) → `completed` "Completed" (green); `envelope_signer` and step words from F-06-T03. Document-list chips: "✓ Dev · Sep 9" (green-tint), "○ Mira" (neutral).

## Copy
`TPL-16/copy.ts`, verbatim: title "Form 8879 · TY2025 · Dev & Mira Kapoor" · back "All documents to sign" · "Decline…" · "Documents (2)" · "Form 8879 — IRS e-file Signature Authorization" · "Form TR-579-IT — New York e-file Signature Authorization" · signers "Dev Kapoor — ✓ Signed Sep 9, 6:12 PM · identity verified", "Mira Kapoor (you) — identity verified 9:21 AM · 2 fields left" · steps with sub-lines ("4 of 4 questions · 9:21 AM", "2 documents", "2 fields left on 2 documents") · authorizing text with "$2,296" and "$410" · "Adopt signature & sign…" (Q7 ellipsis) · "Signing records the date, time, your IP address and the verification result." · completion "Signed. Thank you, Mira." and the six evidence labels · "Brightwater Hale will file your returns and message you when they're accepted." · DF-11 failure copy · decline reasons "The amounts look wrong", "I have a question first", "Someone else should sign", "Other".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "All documents to sign" | POR-06 (N-02) | planned |
| Document-list chips | SIG-01 (firm side, N-02) | planned |

## Acceptance
- TPL-16 acceptance: three-column ceremony (240 / page well / 300) with espresso-outlined sign fields and a dark "Sign here" tab.
- TPL-16 acceptance: 8879 Part I foots, 61,200 − 58,904 = 2,296; New York refund 410.
- TPL-16 acceptance: the evidence record lists date and time, method, identity result, IP, login and document hashes.
- TPL-16 acceptance: joint filers sign separately; "1 of 2 signed" until Mira signs.
- TPL-16 acceptance: E6 sent Sep 8, Dev signed Sep 9, due Oct 5; Dina Sato named on failure.
- TPL-16 acceptance: 390 frame with a sticky sign bar.

## Figures
61,200 − 58,904 = 2,296 (federal refund); NY refund 410; AGI 312,640. Proven by `apps/web/src/fixtures/seed/__tests__/tax.foot.test.ts` (F-06-T02).

## AVOID
Gradients, emoji, saturated blue, yellow sign-here flags, heavy shadows, invented colours, lorem ipsum, DocuSign-style branding, any Accrued branding, full SSNs, letting one spouse sign for the other.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| a, c | Native KBA card and Adopt dialog not built; Tier C screenshots | Chapter 01 rules out a native ceremony | DF-12, F-06 §11.2 Q2 |
| e | "You can try again tomorrow at 9:24 AM, or call Dina Sato…" replaced by the paper-form text naming Dina Sato; no retry | IRS FAQ: three failed KBA attempts close remote signing for that form | DF-11 |
| b | "Adopt signature & sign" carries an ellipsis | It opens a step, not an action (ellipsis rule) | F-06 §11.2 Q7, DECISIONS.md |
| g | sticky bar 64 | TPL-16g's own value; TPL-19 frame 9 keeps 72; POR-06 uses 64 | F-06 §11.2 Q4, DECISIONS.md |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a, c | C screenshot + A chrome | not run | identity and adopt region masked |
| b, d, e, f | B frame · A strips · D geometry | not run | provider-frame region masked where present; locked in F-06-T13 |
| g | B · D (390, 44 × 44 targets, 48 primary, bar 64) | not run | F-06-T13 |

## Open gaps
- Q5 (provider-mode CTA label): open, decide by Fri Apr 30, 2027. The specimen keeps the built label.
- DF-11 paper-form sentence: counsel confirms the Pub 1345 text (DF-11); the copy module carries the plan's sentence until then.
