---
id: ADR-230
title: "Structured agent output (AgentBlocks): a closed block schema, numbers by reference, no model markup (amends ADR-065)"
status: proposed
date: 2026-10-28
deciders: ayushkbhatia
risk_zone: red
proposal: P-24
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by F-06-T24 (TASK-1704) in S14. Accept by **Fri May 28, 2027** (end of
S15), before F-06-T15 (S18), I-01 (S22) and K-01-T21 (S23) build on it. If acceptance slips,
F-06-T15 splits: letter and email blocks first (they carry no agent prose while ADR P-25 is off).

## Context
ADR-065 says model output is "rendered as sanitised plain text". That was written before the agent
surfaces needed structure: Workbench answers with tables and figures (WB-*, SHL-13), drafted memos
on the T10 paper (TPL-10, TXP-01), Today and home counts that must equal HOME-01/02, the knowledge
drafts of K-01. Plain text forces one of two bad outcomes: the model writes markdown (an
exfiltration and injection path, which ADR-065 closes) or the model types numbers (which ADR-050
forbids it to compute, and which nobody can check).

DEC-41 (chapter 09) decided P-24: a closed `AgentBlocks` schema, numbers by reference, still no
model markup. Chapter 05 §5.4.5 (AG-05) and §5.3.10 give the rules. The repo already implements a
v1 of the schema for agent runs (P-09-T06: `backend/src/abacus/modules/agents/blocks.py`, the
renderer `packages/ui/src/agent/blocks.tsx`), with the docstring "ADR P-24 owed". This ADR makes
that shape binding, names the one check every surface shares, and adds the two block kinds
F-06's `DocBlocks` needs (heading and bullets) so T15 builds on an accepted schema.

## Decision
1. **Models never emit markup.** Every model output that a person sees is an `AgentBlocks`
   payload: a typed Pydantic schema with a **closed** set of parts. A part kind the schema does
   not list is refused, never rendered as text. Version 2 parts:
   - `h` (heading: level 3 or 4, plain text) and `ul` (bullets: 1–20 items, each a segment list)
     — **new in v2**, for document bodies (F-06 T10 `DocBlocks`);
   - `p` (paragraph: a list of segments);
   - `table` (head and rows of segment cells; a statement table is a `table` whose figure cells
     are `fact` segments and whose total rows are flagged `total: true`);
   - `kv`, `metric`, `file`, `badge`, `cite_list`, `options`, `entity_ref` (v1, unchanged).
   A **segment** is `text`, `cite` (a citation id and its marker number) or `fact` (a fact id).
2. **Numbers by reference.** Every computed figure enters the model's context as a *fact* with an
   id, computed by code (ADR-050). The model may only place `{fact: id}` segments; code renders the
   digits with `format.ts` rules. A **number-provenance check** refuses any other numeric token in
   a `text` segment unless it equals the value of a verified citation in the same payload. The
   gateway repairs once (one re-ask); a second failure marks the value "Unsupported" and the part
   is shown without it.
3. **Citation offsets are per segment.** A citation is a `cite` segment placed after the text it
   supports; the marker number is the payload's, the locator the citation's (ADR-066, citation
   v2). A renderer never parses "[n]" out of text: a "[3]" a model typed is literal text, and the
   copy lint refuses it.
4. **One validation, server side.** `validate_blocks` runs in `ai_gateway` as a registered output
   check before anything is stored or shown: closed kinds; no HTML, markdown or unallowlisted
   links (refused, not rewritten); `sanitise_text` on every string (NFC; controls, bidi,
   zero-width and tag characters stripped; length caps); copy lint (no claim of a human act, no
   "memory/trained/learned", no "!", no confidence percentages, no persona names, no status word
   outside the registry); closed references (every fact id registered, every citation in the
   run's set, every badge a stored status of its object).
5. **Renderers render React nodes only.** `AgentBlocks` (and F-06's `DocBlocks` for paper bodies)
   map parts to components; no HTML string, no `dangerouslySetInnerHTML`, no markdown library.
   Agent-provenance segments render through `AgentText` and carry the agent attribution.
6. **Client-facing text stays template-only while ADR P-25 is off** (ADR-111, DEC-79): a payload
   with agent provenance is never rendered in a client- or agency-facing variant unless the
   consumer passes `modelTextToClients` after P-25 is accepted and the firm's flag is on.

This **amends ADR-065**: "sanitised plain text" becomes "a validated `AgentBlocks` payload whose
strings are sanitised plain text". Everything else in ADR-065 stands (links stripped unless
allowlisted, outbound scope checks).

Consumers named: **F-06-T15** (T10 `DocBlocks` over P-24 segments), **I-01** (HOME-01/02 counts
and Today, which must equal the home tiles), **K-01-T21** (knowledge drafts), and the existing
agent-run surfaces (P-09, SHL-13, WB-*).

## Worked examples
**A figure the model typed is refused.** Facts `f12 = 6,200` (tax-exempt interest) and
`f13 = 6,866,200` (Schedule L capital). The model returns
`{kind: "p", segments: [{kind: "text", text: "Tax-exempt interest of 6,200 is missing."}]}`. The
provenance check finds the token `6,200` in a `text` segment, equal to no verified citation value
in the payload: refused with `numeric_token_in_text`. The repair prompt asks for a fact reference;
if the second answer still types the number, the paragraph renders with "Unsupported" in place
of the figure and the run records the failure.

**A fact token renders the code-computed figure.** The repaired answer is
`[{kind: "text", text: "Tax-exempt interest of "}, {kind: "fact", fact_id: "f12"},
{kind: "text", text: " is missing from the rollforward."}, {kind: "cite", citation_id: …, n: 3}]`.
Code renders "Tax-exempt interest of **6,200** is missing from the rollforward. [3]": the digits
come from the fact registry through `format.ts`, the marker from the verified citation.

## Options considered
### Option A: a closed `AgentBlocks` schema with fact references — chosen
- Pros: structure without markup; numbers provably code's; one validator for every surface; the
  v1 implementation already runs.
- Cons: models need fact-aware prompts; every new layout need is a schema change (this ADR's
  version 2 adds two parts).

### Option B: keep plain text (ADR-065 as written)
- Pros: nothing to build.
- Cons: tables and figures arrive as prose or not at all; numbers in prose cannot be checked.
- Why rejected: fails AG-05 and DEC-41, and leaves HOME-01/02 counts unverifiable.

### Option C: sanitised markdown
- Pros: rich formatting for free.
- Cons: images and links are exfiltration paths; sanitiser drift; numbers still free text.
- Why rejected: the risk ADR-065 exists to close.

## Consequences
**Positive**
- One shape for agent output on every surface; T10 paper bodies and Workbench share it.
- Every displayed figure is traceable to code or a verified citation (ADR-050, INV-2).

**Negative / costs accepted**
- Prompts and evals must carry fact registries; a model that types numbers costs one repair.
- Layout needs beyond the closed set wait for a schema version.

**Follow-up work created**
- Add `h` and `ul` parts (and the `total` row flag on `table`) to `blocks.py`, the generated
  client and `packages/ui/src/agent/blocks.tsx` before F-06-T15 (S18).
- Point `blocks.py`'s docstring at this ADR once accepted.
- F-06-T17's acceptance tests assert the no-markup path ("<b>x</b>" and "[3]" render literally).

## Enforcement
- `validate_blocks` is a registered `ai_gateway` output check; nothing reaches storage unvalidated.
- `banned_patterns` bans `dangerouslySetInnerHTML` and markdown renderers in `packages/ui` and
  `apps/web`; ESLint and `check_dependencies` keep markdown libraries out.
- Unit tests in `backend/tests/unit/agents/` for each refusal; F-06-T17 for the renderer.
