# Discovery interview guide (F-09-T14)

For the wave-1 and wave-2 discovery interviews (at least 15 by M3, Fri Nov 20, 2026) and the December follow-ups with letter-of-intent firms. The guide produces the inputs to **DEC-70** (first live ledger), **DEC-49** (tax-engine route), **DEC-25** (e-signature strategy), **DEC-75** (firm intake mailbox) and **proposed DEC-100** (pricing and founding-partner terms), plus the W1 to W3 readings in [`thresholds.md`](thresholds.md). It also gathers what two later programmes need: protected-health-information exposure (the business-associate posture) and quality-management needs (the SQMS 1 Technology Resource Pack).

## Anonymisation rules (AC-27, DEC-05)

These rules come first because they bind everything else. The repository is public until F-01-T01 closes.

1. **No client data is collected. Ever, in discovery.** Do not ask for, accept, open or paste a client's name, an engagement, a trial balance, a ledger export, a return, a plan or participant record, a tax identification number, or any document from a firm's client work. If an interviewee starts to share one, stop them, do not write it down, and record only "client data offered, declined".
2. **Firm codes only.** Each firm gets a code: `DP-A1`, `DP-A2` for audit and employee-benefit-plan firms; `DP-T1` for extension-season tax; `DP-C1` for client accounting services; the next free number within each letter. Each person gets a role code within the firm: `P1` partner, `M1` manager, `S1` senior, `C1` audited-company controller.
3. **The key from code to name stays in the document vault**, never in git, an issue, a pull request or a prompt. The vault reference is opaque (for example `V-0nn`).
4. **Describe the firm only by:** size band (under 20, 20 to 49, 50 to 150, over 150 people), window, primary ledger mix, tax engine, mailbox suite, and the signals below. No city, state, founding year, specialty niche, client type, or any distinctive detail that would let someone who knows the market name the firm.
5. **No prices, quotes, contract or letter-of-intent text, counsel advice, or auditor or partner names.** If an amount is volunteered, write it only in the vault under the firm code; the note says "amount given, vault".
6. **Quotes:** none that identify a person or firm. Paraphrase.
7. **Request lists** (the lists of items an auditor asks a client for) are committed only after anonymising: remove the client and entity names, the period-specific dates, the amounts and any account names that are not generic. Keep the item wording in generic form, the count, and the retrievability tag (A to E). Store under `docs/product/discovery/request-lists/<code>-<n>.md`.
8. **While the repository is public, commit only the structured tally block** of each note (the "Record" section below). Keep narrative in the vault under the firm code. Commit narrative only after the repository is private. Run `cd backend && uv run python -m abacus_tools.quality.secrets_scan` before every commit of discovery files.
9. **Re-identification check before commit:** could someone who knows this market guess the firm from this note? If yes, remove detail until the answer is no.
10. **Do not put call recordings, transcripts or raw notes in git or in a prompt.** Draft the anonymised note from your own notes by the end of the next working day.

## Before the call

- Choose the firm's window (audit and employee-benefit-plan, extension-season tax, or client accounting services) and who you are speaking to.
- Open the note file `docs/product/discovery/interviews/<code>-<date>.md` and the [`thresholds.md`](thresholds.md) counting rules.
- Remember what the product is at this stage: a design-partner programme. **Synthetic data only until the real-data gate (Fri Apr 16, 2027)**, shadow no earlier than Tue Jun 1, 2027, client-facing no earlier than Tue Jul 13, 2027.

## What not to promise

- No autonomous agent decisions: a named person decides everything.
- No model-written text sent to a firm's clients.
- No group audit before December 2028 year-ends.
- No quality-management screens for 2026.
- No fees before the first client-facing month.
- No dates earlier than those above.

## Structure (45 to 60 minutes)

| Min | Block | Goal |
|---|---|---|
| 0 to 5 | Opening | Purpose, the anonymity rules above, no client data, permission to take notes |
| 5 to 15 | Today's workflow | How a request list is run now: who builds it, how clients answer, where it goes wrong |
| 15 to 40 | Topic blocks | Pick the blocks that fit the role; every partner call covers PBC, evidence acceptance, and at least three more |
| 40 to 50 | Portal and agent reaction | W1 and W2 questions |
| 50 to 60 | Close | Who else to talk to (by role, not name); what would make them stop; thank you |

## Core questions: W1, W2, W3

**Portal (W1).** Walk me through the last time a client was late on the document request list. If the client answered through a branded portal on your own address, with a clear list and reminders, would you run at least one engagement that way this year? What would stop you? Who would need to agree?

**Evidence acceptance (W2).** If software read an uploaded document, said what it appears to be, quoted the page or cell it relied on, and flagged problems, with a named person on your team deciding whether to accept it, would you rely on that for at least one engagement? What would the quote need to show for you to trust it? What would you still check by hand?

**Retrievability (W3).** Ask if the firm will share an anonymised copy of one recent request list, with client and entity names removed and no amounts. If not, ask them to read item types aloud and tag each as you go (tiers A to E: a standard system report, derivable from system data, a document attached in the system, held by the client outside the system, from a third party or on paper). Tally only; do not write client details.

**Controller access (context for W3b).** Where the client has an accounting system, would its controller be willing to give read-only access for the audit? What would they want in writing? Who at the client decides?

## Topic blocks and what each one feeds

### 1. Ledger (feeds DEC-70)

- Which accounting systems do your audit and compilation clients run, and roughly what share of clients each: QuickBooks Online, QuickBooks Desktop, NetSuite, Xero, Sage Intacct, other?
- Which systems matter most for next season's clients and which ones are growing?
- How do you get the trial balance and general ledger today: access to the system, an export from the client, a package from the client's accountant?
- Have clients refused access? On what grounds?
- Which one system, if we connected it first, would help the most clients on your list?

Record: primary ledger mix as counts by system; how data arrives (access, export, package); one-system preference. Default if the evidence is thin: QuickBooks Online (DEC-70).

### 2. Tax engine (feeds DEC-49)

- Which tax engine do you use for 1040, 1041 and 1065, and who administers it?
- How does return data move in and out today: an import or export file, an API, re-keying?
- Is there a person at the firm who can validate an export file format with us, using synthetic returns only?
- What happens at the extension deadlines that you would pay to fix?

Record: engine by return type; movement method; whether an administrator is available. Tax-engine API versus file bridge depends on this; the plan's default is the file bridge (DEC-49).

### 3. E-signature (feeds DEC-25)

- How do you collect engagement letters, representation letters and e-file authorisations today? Which provider?
- For individual e-file authorisation, how do you handle identity verification and the fallback when verification fails?
- Would you accept importing the provider's evidence package instead of signing inside our product (record mode first)? Would a built-in embedded flow with identity checks change your answer?

Record: provider by document type; identity-verification method; accept record mode (yes, no, conditional). Default: record mode, then an embedded provider flow (DEC-25).

### 4. Mailbox (feeds DEC-75)

- Do you have a shared intake mailbox for client documents? Which address style?
- Would the firm give us its own mailbox for reading and sending on its behalf, with what safeguards? Or would you rather forward to an address we provide?
- Who at the firm approves a mailbox integration?

Record: intake mailbox exists; own mailbox versus forwarding preference; approver role.

### 5. Google Workspace or Microsoft 365 (feeds DEC-75; the Google review only if needed)

- Which suite does the firm run? Does any part use the other?
- Are there policies that block third-party apps from mail or files? Who grants an exception and how long does it take?

Record: suite; policy blockers. A Google integration is filed only when a design partner actually runs Google Workspace.

### 6. Protected health information (feeds the business-associate posture)

- Do your audits include employee benefit plans whose files contain participant or health-plan data?
- What have plans or your counsel required of vendors that touch that data? Is a business-associate agreement a requirement for you?
- Would you exclude those engagements from any AI processing at first?

Record: whether plan audits carry health data; whether an agreement is required; preference to exclude. Do not record plan names or participant details.

### 7. Quality management (feeds the SQMS 1 Technology Resource Pack)

- Is the firm evaluating its quality-management system under SQMS 1? When is the evaluation date?
- What do you ask a software vendor for, as documentation or assurance, when it supports an engagement? Who asks?
- Would a standard technology-resource document from us (controls, testing, how the AI is supervised) shorten that work?

Record: evaluation date band; documents requested; who owns the request.

### 8. Pricing (feeds proposed DEC-100)

Use the packaging hypothesis in chapter 01 §1.6.7. Do not quote prices to the interviewee and do not write any amount in git.

- How does the firm buy software today: per seat, per firm, per engagement, per return?
- How would you want to buy this? Does a per-firm platform charge plus per-seat charges for staff make sense? Would an included pool of agent time with metered extras be understandable?
- Compared with what you spend on comparable tools, would this be well under, about the same, or well over what you expected?
- What would need to be true for you to pay before the first client-facing month? (The plan charges nothing before then.)

Record: preferred purchase unit; whether the structure is acceptable (yes, no, conditional); relative reaction (well under, about the same, well over, no view). Any amount: vault only.

## Record: the note file

File: `docs/product/discovery/interviews/<code>-<date>.md`. Commit this block only (see rule 8).

```markdown
# <code> · <date>

| Field | Value |
|---|---|
| Firm code | DP-?? |
| Window | audit and EBP / extension-season tax / client accounting |
| Size band | under 20 / 20 to 49 / 50 to 150 / over 150 |
| Respondents (role codes) | P1, M1 ... |
| Wave | 1 / 2 / December follow-up |
| Client data offered and declined | yes / no |

## Signals
| Signal | Answer | Condition (generic, no names) |
|---|---|---|
| W1 willing to run PBC on a portal this year | yes / no / unclear | |
| W2 accepts AI-screened cited evidence | yes / no / unclear | |
| W3 request list tagged | yes (n items; tiers A to E counts) / no | |
| Controllers willing to give read-only ledger access | yes / no / unclear | |

## Tallies
| Topic | Tally |
|---|---|
| Ledger mix | counts by system; how data arrives; one-system preference |
| Tax engine | by return type; movement method; administrator available |
| E-signature | provider by document type; identity method; record mode acceptable |
| Mailbox and suite | intake mailbox; own mailbox or forwarding; suite; blockers |
| Health data | present / not present; agreement required; exclude at first |
| Quality management | evaluation date band; documents requested; owner role |
| Pricing | purchase unit; structure acceptable; relative reaction; amount in vault (yes/no) |

## Follow-ups (by role, no names)
```

## After each call

1. Write the anonymised note by the end of the next working day; run the secrets scan; commit.
2. Update the running tallies for each topic (ledger, tax engine, e-signature, mailbox).
3. Tag any shared request list and commit it under `request-lists/`.
4. At the M3 read (Fri Nov 20, 2026), count against [`thresholds.md`](thresholds.md) and record the reading in its log; write the ledger table and the DEC-70 recommendation in `ledger-choice.md`. The synthesis in `summary-2026.md` (by Fri Jan 22, 2027) feeds DEC-25, DEC-49, DEC-70 and DEC-75; DEC-100 is decided at M4 (Fri Dec 11, 2026).
