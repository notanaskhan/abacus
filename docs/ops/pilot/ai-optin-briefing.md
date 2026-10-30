# PW1 firm AI opt-in briefing (F-09-T127; SPEC-036, TASK-076; ADR-114)

Before any shadow run on a firm's real data, AY walks the firm admin through the disclosure the
product itself shows, then the **firm** opts in, in the product. Acceptance: each PW1 firm admin
has seen the disclosure before Tue Jun 1, 2027, and the opt-in itself is recorded in the product by
the firm (never by us, never by the agent: INV-1).

## What the admin is shown (the product's own disclosure)
Open **Settings → AI on your clients' data** as the firm admin (the opt-in panel, SPEC-036). The
disclosure there is generated from the provider terms register (`docs/operations/provider-terms.yaml`,
ADR-114), so the briefing never restates it from memory; walk each part on the screen:

| Part of the panel | What to make sure the admin understands |
|---|---|
| Who runs it | the model provider and region the register names (AWS Bedrock, in our own AWS account, US region); no direct model-vendor access |
| Your clients' data | never used to train or improve models, not kept after each request, except the retention exceptions the panel lists by purpose and days |
| Subprocessors | the parties the panel lists; the full list with roles and DPA status is `docs/operations/sub-processors.md` (send its current version with the briefing) |
| Suggested wording for your engagement letters | the firm decides whether and how to use it; counsel-reviewed §7216 consents are separate (F-09-T125 (c)) |
| Terms reviewed by | the register entry's `review_by`; after that date real-firm calls stop on their own (RB-40) |
| Stages | every assistant starts in **shadow**: it runs and is recorded, nothing is shown to the team; going live is a later decision per assistant, with the firm (`docs/ops/pilot/shadow-briefing.md`) |
| Per-engagement switch | an engagement partner can switch AI off for one engagement |

## Then the firm opts in, in the product
The firm admin (with fresh MFA) turns the opt-in on in the same panel. The product records who and
when against the disclosure version shown; `make go-live-check` reads it as
`ai.client_data_opt_in` (pass only "opted in against the current terms"). If the admin does not opt
in, agents stay off for the firm's real data and PW1 runs without them.

## Record

| Pilot code | Briefed on | Disclosure shown (register entry's `review_by`) | Sub-processor list sent (version) | Opted in, in the product (date) | Go-live check `ai.client_data_opt_in` | Vault |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | none yet: no PW1 firm is signed, and the register has no Bedrock entry current yet (M7) |
