# Onboarding dry run on the production canary (P-07-T65)

The P-07 screens a pilot firm meets first, walked end to end on the **production canary** (the
synthetic firm in production, `firms.synthetic = true`), so M8 (Fri May 28, 2027) can say the
onboarding kit works in production and M9 (Tue Jun 1) can follow it for the first real firm.
Acceptance: the dry-run record shows every step completed on the canary before Fri May 28, 2027.

Synthetic only: the client list is the committed fictional CCH export, contacts are synthetic
users whose invitations go to the fake mail path (the synthetic sink), and nothing here names a
real firm or person. The procedure the steps follow is `docs/runbooks/pilot-onboarding.md`.

## Inputs
- `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/files/cch-axcess-client-list.csv`
  (212 rows; against the scenario's clients it scores 204 matched, 8 to review, 0 new), the same file
  P-07-T62's `cli-06-intake.spec.ts` uses on staging.
- The canary's synthetic people (firm admin, partner, manager) and its synthetic client contacts.

## Steps

| # | Step | Screen and state | Who | Evidence | Done |
|---|---|---|---|---|---|
| 1 | Upload the CCH export | CLI-06 bulk import, mapping shows `Client Name` mapped | firm admin | the import id; `counts.rows` 212 | — |
| 2 | Decide the 8 rows that wait (merge, keep both, skip) | CLI-06 review table | firm admin | `counts.to_review` 0 | — |
| 3 | Run the import | CLI-06 **g** (the result toast) | firm admin | `imported`, `skipped`, `failed` counts | — |
| 4 | Invite two client contacts to the portal, one limited to delegated requests | CLI-04 invite sheet → **c** (invited) | manager | the invitation ids; each message in the synthetic sink, none delivered outside it | — |
| 5 | A contact accepts the invitation and signs in | the portal sign-in, then POR-02 | synthetic contact | the contact's first sign-in event | — |
| 6 | Acceptance and continuance for a new engagement (G1) | CLI-07 (the human-only gate; the agent proposes nothing it decides) | engagement partner | the G1 decision event, attributed to the partner | — |
| 7 | Independence and conflicts for the team | CLI-08 (human-only confirmations) | each team member | the confirmation events, one per person | — |
| 8 | Record the timings in the onboarding kit | `docs/runbooks/pilot-onboarding.md` § Timings, column "First pilot firm" left for M9 | AY | the commit | — |

Each step's audit event must name the person who did it ("‹person›", never the agent: INV-1,
INV-5), and no step may need a database edit, a seed command or a commit of firm content.

## Runs

| Date | Canary release | Operator | Steps done | Total minutes | Defects filed | Notes |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | not run: the production compute stack and the canary tenant are not provisioned |
